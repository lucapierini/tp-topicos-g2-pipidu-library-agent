"""Evaluación de búsqueda híbrida y re-ranking (R-4.10, D98): puro y con dobles, sin red ni base."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts.calibrate_threshold import Case
from scripts.evaluate_retrieval import (
    GeminiReranker,
    build_idf,
    coverage,
    evaluate,
    hybrid,
    normalize_dense,
    parse_relevance,
    rerank_plus_dense,
    rerank_prompt,
    rerank_score,
    summarize,
    tokenize,
    unknown_idf,
)

# --------------------------------------------------------------------------- léxico


def test_tokenize_drops_accents_stopwords_and_keeps_a_stem() -> None:
    assert tokenize("¿Cuántos préstamos puede tener un alumno?") == ["presta", "tener", "alumno"]
    assert tokenize("Préstamo") == tokenize("PRESTAMOS")


def test_tokenize_keeps_amounts_and_drops_english_stopwords() -> None:
    assert "$200" in tokenize("La multa es de $200 por día")
    assert tokenize("What is the late fee?") == ["late", "fee"]


def test_coverage_is_the_idf_weight_of_the_query_found_in_the_chunk() -> None:
    chunks = [{"multa", "atraso"}, {"horario", "sabado"}, {"multa"}]
    idf = build_idf(chunks)
    unknown = unknown_idf(len(chunks))
    assert coverage(["multa", "atraso"], {"multa", "atraso"}, idf, unknown) == pytest.approx(1.0)
    partial = coverage(["multa", "atraso"], {"multa"}, idf, unknown)
    assert 0 < partial < 1
    assert coverage(["horario"], {"multa"}, idf, unknown) == 0.0


def test_a_term_missing_from_the_corpus_lowers_the_coverage() -> None:
    chunks = [{"sala", "lectura"}, {"multa"}]
    idf, unknown = build_idf(chunks), unknown_idf(2)
    with_wifi = coverage(["wifi", "sala"], {"sala", "lectura"}, idf, unknown)
    without_wifi = coverage(["sala"], {"sala", "lectura"}, idf, unknown)
    assert without_wifi == pytest.approx(1.0) and with_wifi < 0.6


def test_coverage_of_an_empty_query_is_zero() -> None:
    assert coverage([], {"a"}, {}, 1.0) == 0.0


# --------------------------------------------------------------------------- puntajes


def test_dense_is_normalized_to_the_unit_interval() -> None:
    assert normalize_dense(0.40) == 0.0 and normalize_dense(0.95) == 1.0
    assert normalize_dense(0.675) == pytest.approx(0.5)


def test_hybrid_is_a_linear_combination() -> None:
    assert hybrid(0.85, 1.0, 0.7) == pytest.approx(1.0)
    assert hybrid(0.50, 0.0, 0.7) == 0.0
    assert hybrid(0.675, 1.0, 0.5) == pytest.approx(0.75)


def test_parse_relevance_validates_count_and_range() -> None:
    assert parse_relevance('{"scores": [0, 3, 2]}', 3) == [0, 3, 2]
    assert parse_relevance('{"scores": [9, -1]}', 2) == [3, 0]  # se acota a 0..3
    for raw in ("", "no es json", '{"x": 1}', '{"scores": [1]}', '{"scores": ["a", "b"]}', None):
        with pytest.raises(ValueError):
            parse_relevance(raw, 2)


def test_rerank_score_is_the_best_chunk_on_a_unit_scale() -> None:
    assert rerank_score([0, 1, 3]) == 1.0 and rerank_score([1, 2]) == pytest.approx(2 / 3)
    assert rerank_score([]) == 0.0


def test_rerank_plus_dense_breaks_ties_with_the_similarity() -> None:
    assert rerank_plus_dense(1.0, 0.80) > rerank_plus_dense(1.0, 0.60)
    # una relevancia 2/3 (contiene parte de la respuesta) gana a una 0 por alta que sea la similitud
    assert rerank_plus_dense(0.0, 0.85) < rerank_plus_dense(2 / 3, 0.50)


def test_rerank_prompt_numbers_the_chunks_and_names_their_source() -> None:
    prompt = rerank_prompt("¿Hay wifi?", [{"document": "reglamento.pdf", "location": "Art. 8", "text": "Horarios"}])
    assert "¿Hay wifi?" in prompt and "[0] (reglamento.pdf, Art. 8)" in prompt and "Horarios" in prompt


# --------------------------------------------------------------------------- resumen


def test_summarize_reports_auc_and_the_document_accuracy() -> None:
    rows = [
        {"covered": True, "score": 0.9, "doc": "a.pdf", "expected_document": "a", "group": "g"},
        {"covered": True, "score": 0.8, "doc": "b.pdf", "expected_document": "a", "group": "g"},
        {"covered": False, "score": 0.3, "doc": "a.pdf", "expected_document": None, "group": "n"},
    ]
    s = summarize("x", rows, "score", "doc")
    assert s["auc"] == 1.0 and s["top1_document_accuracy"] == 0.5
    assert s["best_f1"]["f1"] == 1.0


# --------------------------------------------------------------------------- re-ranker con cliente simulado


class FakeClient:
    def __init__(self, text: str):
        self.text, self.calls = text, 0
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **_):
        self.calls += 1
        return SimpleNamespace(text=self.text)


def _cfg():
    return SimpleNamespace(model="m", api_timeout_s=5, api_max_retries=0)


def test_reranker_calls_the_model_once_per_candidate_set_and_caches(tmp_path) -> None:
    client = FakeClient('{"scores": [3, 0]}')
    cache = tmp_path / "cache.json"
    reranker = GeminiReranker(_cfg(), cache, client=client)
    chunks = [{"id": 1, "document": "d", "location": "l", "text": "t"}, {"id": 2, "document": "d", "location": "l", "text": "t"}]
    assert reranker.relevances("pregunta", chunks) == [3, 0]
    assert reranker.relevances("pregunta", chunks) == [3, 0]
    assert client.calls == 1
    assert json.loads(cache.read_text(encoding="utf-8"))  # persistido
    again = GeminiReranker(_cfg(), cache, client=FakeClient("no se usa"))
    assert again.relevances("pregunta", chunks) == [3, 0]


# --------------------------------------------------------------------------- extremo a extremo con dobles


class FakeEmbedder:
    def embed_query(self, text: str):
        return text


class FakeStore:
    """Cada consulta mira una tabla {consulta: similitud por fragmento}."""

    def __init__(self, chunks, sims):
        self.chunks, self.sims = chunks, sims

    def search(self, vector, top_k):
        return [SimpleNamespace(id=c["id"], document=c["document"], location=c["location"], text=c["text"],
                                similarity=self.sims[vector][c["id"]]) for c in self.chunks][:top_k]


class FakeReranker:
    def relevances(self, question, chunks):
        return [3 if "multa" in c["text"] and "multa" in question else 0 for c in chunks]


def test_evaluate_scores_every_strategy_and_lexical_separates_what_dense_cannot() -> None:
    chunks = [
        {"id": 1, "document": "reglamento.pdf", "location": "Art. 5", "text": "La multa es de $200 por día de atraso"},
        {"id": 2, "document": "reglamento.pdf", "location": "Art. 8", "text": "Horarios de la biblioteca y la sala de lectura"},
    ]
    cases = [
        Case("P1", "¿Cuánto es la multa por atraso?", True, "reglamento", "reglamento"),
        Case("P2", "¿Cuál es el horario de la sala de lectura?", True, "reglamento", "reglamento"),
        Case("N1", "¿Hay wifi en la sala de lectura?", False, "dominio_dificil"),
    ]
    # El coseno del negativo es tan alto como el del positivo: el puntaje denso no los separa
    sims = {cases[0].question: {1: 0.75, 2: 0.60}, cases[1].question: {1: 0.60, 2: 0.74},
            cases[2].question: {1: 0.58, 2: 0.76}}
    rows, summary = evaluate(cases, FakeEmbedder(), FakeStore(chunks, sims), FakeReranker(), _cfg())
    by_name = {s["strategy"]: s for s in summary}
    assert {"denso (actual)", "léxico", "re-ranking (top-5 denso)"} <= set(by_name)
    assert by_name["denso (actual)"]["auc"] < 1.0           # 0.76 del negativo supera al 0.74 de un positivo
    assert by_name["léxico"]["auc"] == 1.0                  # «wifi» no existe en el corpus
    assert all(0.0 <= r["lexico"] <= 1.0 and "_dense_top" not in r for r in rows)
    assert rows[0]["denso_doc"] == "reglamento.pdf"


def test_evaluate_without_a_reranker_skips_the_model_strategies() -> None:
    chunks = [{"id": 1, "document": "d.pdf", "location": "l", "text": "texto uno"}]
    cases = [Case("P1", "texto", True, "g", "d"), Case("N1", "otra cosa", False, "n")]
    sims = {"texto": {1: 0.8}, "otra cosa": {1: 0.5}}
    _, summary = evaluate(cases, FakeEmbedder(), FakeStore(chunks, sims), None, _cfg())
    assert not any("re-ranking" in s["strategy"] for s in summary)


def test_reranker_retries_a_transient_server_error(monkeypatch) -> None:
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda _s: None)

    class Flaky(FakeClient):
        def _generate(self, **kw):
            self.calls += 1
            if self.calls < 3:
                err = RuntimeError("503 UNAVAILABLE")
                err.code = 503
                raise err
            return SimpleNamespace(text=self.text)

    client = Flaky('{"scores": [2]}')
    reranker = GeminiReranker(_cfg(), None, client=client)
    assert reranker.relevances("q", [{"id": 1, "document": "d", "location": "l", "text": "t"}]) == [2]
    assert client.calls == 3


def test_reranker_does_not_retry_a_client_error(monkeypatch) -> None:
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda _s: None)

    class Bad(FakeClient):
        def _generate(self, **kw):
            self.calls += 1
            err = RuntimeError("400 INVALID")
            err.code = 400
            raise err

    client = Bad("")
    with pytest.raises(RuntimeError):
        GeminiReranker(_cfg(), None, client=client).relevances(
            "q", [{"id": 1, "document": "d", "location": "l", "text": "t"}])
    assert client.calls == 1
