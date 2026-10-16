"""Recuperación con re-ranking (R-4.11, D100): el modelo juzga si cada fragmento contesta. Sin red ni base."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent.config import load_config
from agent.contracts import Chunk
from agent.errors import NO_RELEVANT_RESULTS
from agent.tools.rag_tool import InMemoryVectorStore, RagRetriever
from agent.tools.reranker import (
    DENSE_WEIGHT,
    GeminiReranker,
    build_prompt,
    combined_score,
    normalize_dense,
    parse_relevance,
    rerank_score,
)


def chunk(i: int, similarity: float = 0.0, doc: str = "reglamento.pdf", text: str = "texto") -> Chunk:
    return Chunk(id=i, document=doc, location=f"Art. {i}", text=text, content_hash=f"h{i}", similarity=similarity)


# --------------------------------------------------------------------------- puntaje


def test_defaults_enable_rerank_with_the_validated_threshold() -> None:
    cfg = load_config()
    assert cfg.rag_strategy == "rerank" and cfg.rerank_threshold == 0.40


def test_the_score_is_dominated_by_the_relevance_and_the_similarity_breaks_ties() -> None:
    assert combined_score([3, 0], 0.85) == pytest.approx(1.0)
    assert combined_score([0, 0], 0.50) == 0.0
    assert combined_score([3], 0.70) > combined_score([3], 0.60)
    # una relevancia 2/3 (parte de la respuesta) supera a una 0 aunque el coseno sea altísimo
    assert combined_score([2], 0.50) > combined_score([0], 0.85)
    assert DENSE_WEIGHT == 0.3


def test_normalize_dense_clamps_to_the_unit_interval() -> None:
    assert normalize_dense(0.2) == 0.0 and normalize_dense(0.99) == 1.0
    assert normalize_dense(0.675) == pytest.approx(0.5)


def test_parse_relevance_rejects_a_malformed_output() -> None:
    assert parse_relevance('{"scores": [3, 0, 9]}', 3) == [3, 0, 3]
    for raw in (None, "", "no es json", '{"scores": [1]}', '{"x": 1}', '{"scores": ["a"]}'):
        with pytest.raises(ValueError):
            parse_relevance(raw, 2)
    assert rerank_score([]) == 0.0


def test_the_prompt_lists_each_chunk_with_its_source() -> None:
    prompt = build_prompt("¿Hay wifi?", [("reglamento.pdf", "Art. 8", "Horarios"), ("politicas.pdf", "4", "Silencio")])
    assert "[0] (reglamento.pdf, Art. 8)" in prompt and "[1] (politicas.pdf, 4)" in prompt


# --------------------------------------------------------------------------- recuperador


class ScriptedReranker:
    def __init__(self, relevances=None, error: Exception | None = None):
        self.relevances_to_return, self.error, self.calls = relevances, error, []

    def relevances(self, question, items):
        self.calls.append((question, items))
        if self.error:
            raise self.error
        return self.relevances_to_return(items) if callable(self.relevances_to_return) else self.relevances_to_return


class FakeEmbedder:
    def embed_query(self, text):
        return [1.0, 0.0]


def retriever(chunks_with_vectors, reranker, **cfg_changes) -> RagRetriever:
    cfg = replace(load_config(), **cfg_changes)
    return RagRetriever(FakeEmbedder(), InMemoryVectorStore(chunks_with_vectors), cfg, reranker)


def store_items(*sims: float) -> list[tuple[Chunk, list[float]]]:
    """Vectores tales que el coseno con [1, 0] es exactamente cada similitud."""
    import math

    return [(chunk(i + 1), [s, math.sqrt(1 - s * s)]) for i, s in enumerate(sims)]


def test_it_returns_the_chunks_that_contain_the_answer_ordered_by_relevance() -> None:
    reranker = ScriptedReranker([1, 3, 0])
    r = retriever(store_items(0.80, 0.70, 0.60), reranker).retrieve("¿cuánto es la multa?")
    assert r.error is None
    assert [c.id for c in r.chunks] == [2, 1]  # 3 y luego 1; el 0 no entra
    assert reranker.calls[0][0] == "¿cuánto es la multa?" and len(reranker.calls[0][1]) == 3


def test_the_chunk_keeps_its_cosine_similarity_as_evidence() -> None:
    r = retriever(store_items(0.80), ScriptedReranker([3])).retrieve("q")
    assert r.chunks[0].similarity == pytest.approx(0.80)


def test_a_high_cosine_does_not_pass_if_the_model_says_nothing_answers() -> None:
    """El caso que motivó el cambio: «wifi con legajo» tiene coseno 0.70 y ningún documento lo contesta."""
    r = retriever(store_items(0.704, 0.66), ScriptedReranker([0, 0])).retrieve("¿me conecto al wifi con mi legajo?")
    assert r.chunks == [] and r.error == NO_RELEVANT_RESULTS


def test_same_topic_without_the_answer_is_not_enough_at_a_normal_cosine() -> None:
    r = retriever(store_items(0.66), ScriptedReranker([1])).retrieve("q")
    assert r.error == NO_RELEVANT_RESULTS  # 0.7 * 1/3 + 0.3 * 0.46 = 0.37 < 0.40


def test_a_low_cosine_passes_when_the_model_finds_the_answer() -> None:
    """Los positivos que el coseno rechazaba (R15 con 0.646) entran si el modelo ve la respuesta."""
    r = retriever(store_items(0.55), ScriptedReranker([3])).retrieve("q")
    assert [c.id for c in r.chunks] == [1]


def test_the_threshold_is_configurable() -> None:
    items = store_items(0.70)
    assert retriever(items, ScriptedReranker([2]), rerank_threshold=0.30).retrieve("q").chunks
    assert retriever(items, ScriptedReranker([2]), rerank_threshold=0.95).retrieve("q").error == NO_RELEVANT_RESULTS


def test_top_k_limits_the_returned_chunks() -> None:
    r = retriever(store_items(0.8, 0.79, 0.78, 0.77), ScriptedReranker([3, 3, 3, 3]), top_k=2).retrieve("q")
    assert len(r.chunks) == 2


def test_if_the_reranker_fails_the_query_falls_back_to_the_cosine_threshold() -> None:
    failing = ScriptedReranker(error=RuntimeError("429 RESOURCE_EXHAUSTED"))
    ok = retriever(store_items(0.80), failing).retrieve("q")
    assert [c.id for c in ok.chunks] == [1] and ok.error is None  # 0.80 >= 0.64
    no = retriever(store_items(0.60), failing).retrieve("q")
    assert no.error == NO_RELEVANT_RESULTS                       # 0.60 < 0.64


def test_a_wrong_number_of_scores_falls_back_to_the_cosine() -> None:
    r = retriever(store_items(0.80, 0.70), ScriptedReranker([3])).retrieve("q")
    assert [c.id for c in r.chunks] == [1, 2]


def test_dense_strategy_never_calls_the_reranker() -> None:
    reranker = ScriptedReranker([3])
    r = retriever(store_items(0.80, 0.50), reranker, rag_strategy="dense").retrieve("q")
    assert reranker.calls == [] and [c.id for c in r.chunks] == [1]


def test_without_a_reranker_it_behaves_like_before() -> None:
    r = retriever(store_items(0.80, 0.50), None).retrieve("q")
    assert [c.id for c in r.chunks] == [1]


def test_an_empty_store_does_not_call_the_reranker() -> None:
    reranker = ScriptedReranker([])
    r = retriever([], reranker).retrieve("q")
    assert r.error == NO_RELEVANT_RESULTS and reranker.calls == []


def test_a_blank_query_is_still_an_error_without_a_model_call() -> None:
    reranker = ScriptedReranker([3])
    assert retriever(store_items(0.8), reranker).retrieve("   ").error is not None and reranker.calls == []


# --------------------------------------------------------------------------- modelo (cliente simulado)


class FakeClient:
    def __init__(self, text: str):
        self.text, self.calls, self.kwargs = text, 0, []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kw):
        self.calls += 1
        self.kwargs.append(kw)
        return SimpleNamespace(text=self.text)


def test_the_model_is_called_once_with_temperature_zero_and_structured_output() -> None:
    client = FakeClient('{"scores": [3, 1]}')
    reranker = GeminiReranker(load_config(), client=client)
    assert reranker.relevances("pregunta", [("d", "l", "uno"), ("d", "l", "dos")]) == [3, 1]
    assert client.calls == 1
    config = client.kwargs[0]["config"]
    assert config.temperature == 0 and config.response_mime_type == "application/json"


def test_a_malformed_model_output_is_an_error() -> None:
    with pytest.raises(ValueError):
        GeminiReranker(load_config(), client=FakeClient("no es json")).relevances("q", [("d", "l", "t")])


def test_a_transient_server_error_is_retried(monkeypatch) -> None:
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)

    class Flaky(FakeClient):
        def _generate(self, **kw):
            self.calls += 1
            if self.calls < 3:
                err = RuntimeError("503")
                err.code = 503
                raise err
            return SimpleNamespace(text=self.text)

    client = Flaky('{"scores": [2]}')
    assert GeminiReranker(load_config(), client=client).relevances("q", [("d", "l", "t")]) == [2]
    assert client.calls == 3


def test_a_client_error_is_not_retried(monkeypatch) -> None:
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)

    class Bad(FakeClient):
        def _generate(self, **kw):
            self.calls += 1
            err = RuntimeError("400")
            err.code = 400
            raise err

    client = Bad("")
    with pytest.raises(RuntimeError):
        GeminiReranker(load_config(), client=client).relevances("q", [("d", "l", "t")])
    assert client.calls == 1
