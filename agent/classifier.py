"""Clasificación de la consulta en salida estructurada (T6.2; R-2.1, R-2.7, D3).

Es una llamada **separada y previa** al `ToolCallingAgent`: el orquestador sabe qué fuente
corresponde antes de que exista cualquier invocación a una herramienta, y expone solo las tools
de esa fuente. Con el modelo clasificando dentro del mismo loop, que la clasificación preceda a
las tools dependería de que el modelo respete un orden; acá lo garantiza el control de flujo.

El cliente de `google-genai` se mantiene en una variable y no se encadena (D37).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

from agent.config import Config, load_config
from agent.contracts import CLASSIFICATIONS, normalize_classification
from agent.prompts import render_classifier_prompt
from agent.retry import call_with_retry

LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "es"


@dataclass(frozen=True)
class Classification:
    label: str       # sql | rag | hybrid | none
    language: str    # es | en: idioma de la consulta, para responder en el mismo (R-5.1)
    rationale: str = ""


class ClassificationError(Exception):
    """El modelo no devolvió una clasificación válida o la llamada falló."""


class Classifier(Protocol):
    def classify(self, question: str) -> Classification: ...


def parse_classification(raw: str) -> Classification:
    """Valida la salida estructurada. El enum es case-sensitive: `"SQL"` se normaliza (D50)."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ClassificationError(f"la salida no es JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ClassificationError("la salida estructurada no es un objeto")

    label = normalize_classification(data.get("classification", ""))
    if label not in CLASSIFICATIONS:
        raise ClassificationError(f"clasificación inválida: {data.get('classification')!r}")

    language = normalize_classification(data.get("language", DEFAULT_LANGUAGE))
    if language not in LANGUAGES:
        language = DEFAULT_LANGUAGE
    return Classification(label=label, language=language, rationale=str(data.get("rationale", ""))[:300])


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str | None) -> str:
    """Un modelo local puede envolver el JSON en ```json … ``` o anteponer su razonamiento."""
    if not text or not text.strip():
        raise ClassificationError("el modelo no devolvió contenido")
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ClassificationError("la salida no contiene un objeto JSON")
    return match.group(0)


class LiteLLMClassifier:
    """Clasificador independiente del proveedor (LiteLLM): servidores locales OpenAI-compatibles.

    No usa el `response_schema` de Gemini: pide `json_object` y valida el resultado con
    `parse_classification`, que rechaza cualquier etiqueta fuera del vocabulario.
    """

    # Los modelos que razonan antes de contestar gastan tokens en eso: con un tope bajo devuelven
    # `content: None` (observado con Strata y `max_tokens=16`) o `finish_reason=length` con el JSON
    # incompleto (G12 con `max_tokens=1024`, 3 de 3 intentos). Con 2048 completó la misma consulta.
    MAX_TOKENS = 4096

    def __init__(self, config: Config | None = None, completion=None) -> None:
        self.cfg = config or load_config()
        self._completion = completion

    def _get_completion(self):
        if self._completion is None:
            import litellm

            litellm.suppress_debug_info = True
            self._completion = litellm.completion
        return self._completion

    def classify(self, question: str) -> Classification:
        kwargs = {
            "model": self.cfg.llm_model,
            "messages": [
                {"role": "system", "content": render_classifier_prompt()},
                {"role": "user", "content": question},
            ],
            "temperature": self.cfg.temperature,  # Art. 7
            "max_tokens": self.MAX_TOKENS,
            "timeout": self.cfg.api_timeout_s,
            "response_format": {"type": "json_object"},
        }
        if self.cfg.llm_api_base:
            kwargs["api_base"] = self.cfg.llm_api_base
            kwargs["api_key"] = os.environ.get("LLM_API_KEY") or "not-needed"
        try:
            completion = self._get_completion()
            response = call_with_retry(lambda: completion(**kwargs), retries=self.cfg.api_max_retries)
            content = response.choices[0].message.content
        except ClassificationError:
            raise
        except Exception as exc:  # noqa: BLE001
            # El motivo se conserva: "ClassificationError" a secas escondió un `finish_reason=length`.
            raise ClassificationError(
                f"falló la llamada de clasificación: {type(exc).__name__}: {str(exc)[:200]}"
            ) from exc
        return parse_classification(extract_json(content))


def build_classifier(config: Config | None = None) -> Classifier:
    """Gemini nativo (salida estructurada con enum) o LiteLLM para cualquier otro proveedor."""
    cfg = config or load_config()
    if cfg.llm_model.startswith("gemini/") and not cfg.llm_api_base:
        return GeminiClassifier(cfg)
    return LiteLLMClassifier(cfg)


class GeminiClassifier:
    def __init__(self, config: Config | None = None, client=None) -> None:
        self.cfg = config or load_config()
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise ClassificationError("GEMINI_API_KEY no está definida (Art. 9)")
            self._client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(timeout=self.cfg.api_timeout_s * 1000),
            )
        return self._client

    @staticmethod
    def _schema():
        from google.genai import types

        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "classification": types.Schema(type=types.Type.STRING, enum=sorted(CLASSIFICATIONS)),
                "language": types.Schema(type=types.Type.STRING, enum=list(LANGUAGES)),
                "rationale": types.Schema(type=types.Type.STRING),
            },
            required=["classification", "language"],
        )

    def classify(self, question: str) -> Classification:
        from google.genai import types

        try:
            client = self._get_client()
            config = types.GenerateContentConfig(
                system_instruction=render_classifier_prompt(),
                temperature=self.cfg.temperature,  # Art. 7
                response_mime_type="application/json",
                response_schema=self._schema(),
            )
            response = call_with_retry(
                lambda: client.models.generate_content(
                    model=self.cfg.model, contents=question, config=config
                ),
                retries=self.cfg.api_max_retries,
            )
        except ClassificationError:
            raise
        except Exception as exc:  # noqa: BLE001
            # El motivo se conserva (igual que en LiteLLM): `ClientError` a secas escondió una cuota agotada.
            raise ClassificationError(
                f"falló la llamada de clasificación: {type(exc).__name__}: {str(exc)[:200]}"
            ) from exc
        return parse_classification(response.text)
