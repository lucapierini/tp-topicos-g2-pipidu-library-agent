"""Herramienta de recuperación (T5.1; R-4.4, R-4.6, R-4.7, R-4.8).

Sin PDFs, sin base y sin API: el embedder y el store son dobles. Lo que se verifica es la
política (top-k, umbral, ausencia de resultados, referencia de origen), no la calidad semántica,
que se calibra con los documentos reales (R-4.8, `scripts/calibrate_threshold.py`).
"""
from __future__ import annotations

import math
from dataclasses import replace

import pytest

from agent.config import load_config
from agent.errors import NO_RELEVANT_RESULTS, RETRIEVAL_ERROR
from agent.tools.rag_tool import (
    GeminiEmbedder,
    InMemoryVectorStore,
    PgVectorStore,
    RagRetriever,
    cosine,
)
from tests.fakes import FakeEmbedder, FakeGenaiClient, make_chunk

PLAZO = [1.0, 0.0, 0.0]
HORARIO = [0.0, 1.0, 0.0]
RESENA = [0.0, 0.0, 1.0]


def corpus():
    return InMemoryVectorStore([
        (make_chunk("reglamento_biblioteca.pdf", "Art. 12", "plazo de 15 días", chunk_id=1), PLAZO),
        (make_chunk("reglamento_biblioteca.pdf", "Art. 3", "horario de 9 a 20", chunk_id=2), HORARIO),
        (make_chunk("resenas_libro_1.pdf", "p. 1", "sinopsis", chunk_id=3), RESENA),
    ])


def retriever(embedder=None, store=None, **overrides):
    cfg = replace(load_config(), **overrides)
    return RagRetriever(embedder or FakeEmbedder({"plazo": PLAZO}), store or corpus(), cfg)


def test_cosine_basics() -> None:
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([1, 1], [2, 2]) == pytest.approx(1.0)
    assert cosine([0, 0], [1, 0]) == 0.0


def test_returns_the_most_similar_chunk_from_the_right_document() -> None:
    # R-4.4: la pregunta normativa devuelve la cláusula de plazo del reglamento.
    result = retriever().retrieve("¿cuál es el plazo de devolución?")
    assert result.error is None
    assert result.chunks[0].document == "reglamento_biblioteca.pdf"
    assert result.chunks[0].location == "Art. 12"
    assert result.chunks[0].similarity == pytest.approx(1.0)


def test_each_chunk_keeps_its_origin_for_citation() -> None:
    # R-4.7
    for chunk in retriever().retrieve("plazo").chunks:
        assert chunk.document and chunk.location and chunk.text and chunk.content_hash


def test_chunks_below_the_threshold_are_dropped() -> None:
    result = retriever().retrieve("plazo")
    assert [c.id for c in result.chunks] == [1], "los ortogonales (coseno 0) quedan bajo 0.35"


def test_no_relevant_results_is_reported_not_fabricated() -> None:
    # R-4.6: ninguna similitud alcanza el umbral.
    embedder = FakeEmbedder(default=[0.6, 0.6, 0.6])
    store = InMemoryVectorStore([(make_chunk(chunk_id=1), PLAZO)])
    result = retriever(embedder, store, similarity_threshold=0.9).retrieve("precio del libro")
    assert result.chunks == [] and result.error == NO_RELEVANT_RESULTS


def test_top_k_comes_from_config() -> None:
    vectors = [(make_chunk(chunk_id=i, text=f"c{i}"), [1.0, 0.1 * i, 0.0]) for i in range(1, 8)]
    result = retriever(store=InMemoryVectorStore(vectors), top_k=3, similarity_threshold=0.0).retrieve("plazo")
    assert len(result.chunks) == 3
    assert [c.similarity for c in result.chunks] == sorted((c.similarity for c in result.chunks), reverse=True)


def test_threshold_comes_from_config() -> None:
    loose = retriever(similarity_threshold=-1.0, top_k=3).retrieve("plazo")
    strict = retriever(similarity_threshold=0.99, top_k=3).retrieve("plazo")
    assert len(loose.chunks) == 3
    assert len(strict.chunks) == 1


def test_an_embedder_failure_is_an_error_not_an_empty_result() -> None:
    # R-5.7: "falló" y "no hay nada relevante" son cosas distintas.
    result = retriever(FakeEmbedder(error=TimeoutError("30s"))).retrieve("plazo")
    assert result.error == RETRIEVAL_ERROR


def test_a_store_failure_is_an_error() -> None:
    class Broken:
        def search(self, vector, top_k):
            raise ConnectionError("base caída")

    assert retriever(store=Broken()).retrieve("plazo").error == RETRIEVAL_ERROR


def test_blank_query_is_not_embedded() -> None:
    embedder = FakeEmbedder()
    result = retriever(embedder).retrieve("   ")
    assert result.error == RETRIEVAL_ERROR and embedder.calls == []


def test_scores_expose_similarities_without_the_threshold() -> None:
    # R-4.8: la calibración necesita ver también lo que el umbral descartaría.
    scores = retriever().scores("plazo")
    assert len(scores) == load_config().top_k or len(scores) == 3
    assert scores[0] == pytest.approx(1.0) and scores[-1] == pytest.approx(0.0)


# --- backends ---


def test_gemini_embedder_asks_for_the_configured_dimensions_and_normalizes() -> None:
    client = FakeGenaiClient()
    vector = GeminiEmbedder(load_config(), client=client).embed_query("plazo")

    call = client.embed_calls[0]
    assert call["model"] == load_config().embedding_model
    assert call["config"].output_dimensionality == load_config().embedding_dim
    assert call["config"].task_type == "RETRIEVAL_QUERY"
    assert math.sqrt(sum(x * x for x in vector)) == pytest.approx(1.0)
    assert vector == pytest.approx([0.6, 0.8])


def test_gemini_embedder_requires_the_key_from_the_environment(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiEmbedder(load_config()).embed_query("x")


class _PgCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.queries.append((sql, params))

    def fetchall(self):
        return self.conn.rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _PgConn:
    def __init__(self, rows):
        self.rows, self.queries, self.rollbacks, self.closed = rows, [], 0, 0

    def cursor(self):
        return _PgCursor(self)

    def rollback(self):
        self.rollbacks += 1


def test_pgvector_store_orders_by_cosine_distance_and_maps_rows() -> None:
    conn = _PgConn([(7, "reglamento_biblioteca.pdf", "Art. 12", "plazo", "h7", 0.82)])
    store = PgVectorStore(load_config(), conn=conn)
    chunks = store.search([0.1, 0.2, 0.3], 5)

    sql, params = conn.queries[0]
    assert "<=>" in sql and "documentos_chunks" in sql and "JOIN documentos" in sql and "ORDER BY" in sql
    # La ubicación sale de `metadata` y la tabla de chunks no se confunde con la SQL del agente (D66).
    assert "metadata" in sql and "nombre_archivo" in sql
    assert params == ("[0.1,0.2,0.3]", "[0.1,0.2,0.3]", 5)
    assert chunks[0].document == "reglamento_biblioteca.pdf" and chunks[0].similarity == pytest.approx(0.82)
    assert conn.rollbacks == 1, "la lectura no deja una transacción abierta"


def test_pgvector_store_uses_only_read_statements() -> None:
    conn = _PgConn([])
    PgVectorStore(load_config(), conn=conn).search([0.0], 1)
    assert conn.queries[0][0].lstrip().upper().startswith("SELECT")
