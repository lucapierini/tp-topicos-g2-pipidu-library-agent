"""Clasificador estructurado (T6.2; R-2.1, R-2.7, D3, D50)."""
from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent.classifier import (
    ClassificationError,
    GeminiClassifier,
    LiteLLMClassifier,
    build_classifier,
    parse_classification,
)
from agent.config import load_config
from agent.contracts import CLASSIFICATIONS
from tests.fakes import FakeGenaiClient


def payload(**fields) -> str:
    return json.dumps({"classification": "sql", "language": "es", "rationale": "x", **fields})


@pytest.mark.parametrize("label", sorted(CLASSIFICATIONS))
def test_every_label_of_the_vocabulary_parses(label: str) -> None:
    assert parse_classification(payload(classification=label)).label == label


@pytest.mark.parametrize("raw", ["SQL", " Rag ", "HYBRID", "None"])
def test_the_label_is_case_insensitive(raw: str) -> None:
    # El enum del modelo es case-sensitive pero puede responder `"SQL"`.
    assert parse_classification(payload(classification=raw)).label == raw.strip().lower()


@pytest.mark.parametrize("raw", ["sql+rag", "database", "", "ambos"])
def test_labels_outside_the_vocabulary_are_rejected(raw: str) -> None:
    with pytest.raises(ClassificationError):
        parse_classification(payload(classification=raw))


@pytest.mark.parametrize("raw", ["", "no es json", "[1, 2]", "null"])
def test_malformed_output_is_rejected(raw: str) -> None:
    with pytest.raises(ClassificationError):
        parse_classification(raw)


def test_language_defaults_to_spanish_when_missing_or_unknown() -> None:
    assert parse_classification(payload(language="fr")).language == "es"
    assert parse_classification(json.dumps({"classification": "rag"})).language == "es"
    assert parse_classification(payload(language="EN")).language == "en"


def test_gemini_classifier_sends_the_prompt_temperature_zero_and_the_enum() -> None:
    client = FakeGenaiClient(text=payload(classification="hybrid", language="en"))
    result = GeminiClassifier(load_config(), client=client).classify("Is a fine due?")

    call = client.calls[0]
    assert call["model"] == load_config().model
    assert call["contents"] == "Is a fine due?"
    config = call["config"]
    assert config.temperature == 0
    assert config.response_mime_type == "application/json"
    assert set(config.response_schema.properties["classification"].enum) == CLASSIFICATIONS
    assert "hybrid" in config.system_instruction and "none" in config.system_instruction
    assert (result.label, result.language) == ("hybrid", "en")


class FakeCompletion:
    """Reemplaza `litellm.completion`: registra los kwargs y devuelve un contenido fijo."""

    def __init__(self, content, error: Exception | None = None):
        self.content, self.error, self.calls = content, error, []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def local_config(**overrides):
    return replace(load_config(), llm_model="openai/qwen-local", llm_api_base="http://127.0.0.1:8080/v1",
                   **overrides)


def test_litellm_classifier_sends_the_local_endpoint_and_a_token_budget_for_reasoning() -> None:
    completion = FakeCompletion(payload(classification="rag"))
    result = LiteLLMClassifier(local_config(), completion=completion).classify("¿Cuál es el horario?")

    call = completion.calls[0]
    assert call["model"] == "openai/qwen-local"
    assert call["api_base"] == "http://127.0.0.1:8080/v1"
    assert call["temperature"] == 0
    assert call["max_tokens"] >= 2048, "con 1024 un modelo que razona dejó el JSON incompleto (G12)"
    assert call["messages"][0]["role"] == "system" and call["messages"][1]["content"] == "¿Cuál es el horario?"
    assert result.label == "rag"


@pytest.mark.parametrize(
    "content",
    ['```json\n{"classification": "hybrid", "language": "es"}\n```',
     'Pienso que necesita ambas.\n{"classification": "hybrid", "language": "es"}'],
)
def test_litellm_classifier_extracts_json_from_wrapped_output(content: str) -> None:
    result = LiteLLMClassifier(local_config(), completion=FakeCompletion(content)).classify("q")
    assert result.label == "hybrid"


@pytest.mark.parametrize("content", [None, "", "no sé", '{"classification": "sql+rag"}'])
def test_litellm_classifier_rejects_unusable_output(content) -> None:
    with pytest.raises(ClassificationError):
        LiteLLMClassifier(local_config(), completion=FakeCompletion(content)).classify("q")


def test_litellm_classifier_wraps_transport_errors() -> None:
    completion = FakeCompletion(None, error=ConnectionError("servidor local caído"))
    with pytest.raises(ClassificationError, match="ConnectionError"):
        LiteLLMClassifier(local_config(), completion=completion).classify("q")


def test_the_underlying_reason_is_not_hidden_behind_the_exception_class() -> None:
    # Con solo el nombre de la clase, un `finish_reason=length` parecía una clasificación inválida.
    completion = FakeCompletion(None, error=RuntimeError("structured output was incomplete (finish_reason=length)"))
    with pytest.raises(ClassificationError, match="finish_reason=length"):
        LiteLLMClassifier(local_config(), completion=completion).classify("q")


def test_build_classifier_picks_the_provider_from_configuration() -> None:
    assert isinstance(build_classifier(replace(load_config(), llm_model="gemini/gemini-3-flash-preview",
                                               llm_api_base="")), GeminiClassifier)
    assert isinstance(build_classifier(local_config()), LiteLLMClassifier)
    # Un base URL propio implica servidor propio, aunque el id empiece con `gemini/`.
    assert isinstance(build_classifier(replace(load_config(), llm_model="gemini/x",
                                               llm_api_base="http://localhost:1")), LiteLLMClassifier)


def test_default_provider_is_gemini_with_the_configured_model() -> None:
    cfg = load_config()
    assert cfg.llm_model == f"gemini/{cfg.model}" and cfg.llm_api_base == ""


def test_an_empty_llm_model_in_the_env_file_means_the_default(monkeypatch) -> None:
    # `.env.example` trae `LLM_MODEL=` vacío: no debe pisar el default con "".
    monkeypatch.setenv("LLM_MODEL", "")
    assert load_config().llm_model.startswith("gemini/")


def test_gemini_classifier_wraps_transport_errors() -> None:
    client = FakeGenaiClient(error=TimeoutError("30s"))
    with pytest.raises(ClassificationError, match="TimeoutError"):
        GeminiClassifier(load_config(), client=client).classify("¿hola?")


def test_gemini_classifier_requires_the_key_from_the_environment(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ClassificationError, match="GEMINI_API_KEY"):
        GeminiClassifier(load_config()).classify("¿hola?")
