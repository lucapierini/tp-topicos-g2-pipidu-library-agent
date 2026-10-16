"""Herramienta de recuperación documental (T5.1; R-4.2, R-4.4, R-4.6, R-4.7, R-4.8).

La recuperación depende de dos piezas que se inyectan como protocolos:

- `Embedder`: texto -> vector. En producción `GeminiEmbedder`; en los tests, un fake sin red.
- `VectorStore`: vector -> top-k fragmentos con su similitud de coseno. En producción
  `PgVectorStore`; en los tests, `InMemoryVectorStore`.

Así el umbral, el top-k, la ausencia de resultados y la referencia de origen se prueban sin
base ni API (Art. 6). La ingesta (`rag/ingest.py`) escribe `documentos` y `documentos_chunks`;
esta herramienta solo los lee.

Contrato con la ingesta:
- `documentos(id, nombre_archivo, tipo, sha256, ...)` y
  `documentos_chunks(id, documento_id, chunk_index, contenido, embedding vector(768), metadata jsonb)`;
- la ubicación de un fragmento (R-4.7) se lee de `metadata`: `seccion`, `ubicacion` o `pagina`. Si la
  ingesta no la guarda, la cita queda como "fragmento N" y se pierde "Art. 12" / "p. 3";
- índice HNSW con `vector_cosine_ops` (D13): sin operador explícito pgvector usa L2 y la consulta por
  coseno no lo aprovecha;
- los documentos se embeben con `task_type=RETRIEVAL_DOCUMENT` y la consulta con `RETRIEVAL_QUERY`;
- el rol `agent_ro` necesita `GRANT SELECT` sobre la tabla (la whitelist de la herramienta SQL la
  excluye a propósito: D99; esta herramienta la lee por una vía distinta).
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import replace
from typing import Protocol

from agent.config import Config, load_config
from agent.contracts import Chunk, RagResult
from agent.errors import NO_RELEVANT_RESULTS, RETRIEVAL_ERROR
from agent.retry import call_with_retry

CHUNKS_TABLE = "documentos_chunks"
DOCUMENTS_TABLE = "documentos"


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    def search(self, vector: list[float], top_k: int) -> list[Chunk]:
        """Los `top_k` fragmentos más cercanos, con `similarity` = coseno, de mayor a menor."""
        ...


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _normalize(vector: list[float]) -> list[float]:
    """`gemini-embedding-001` con `output_dimensionality` < 3072 no devuelve vectores unitarios."""
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


# --------------------------------------------------------------------------- backends


class GeminiEmbedder:
    """Embedding de consulta con la API de Gemini (D5: 768 dimensiones)."""

    def __init__(self, config: Config | None = None, client=None) -> None:
        self.cfg = config or load_config()
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("GEMINI_API_KEY no está definida (Art. 9: se lee del entorno)")
            self._client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(timeout=self.cfg.api_timeout_s * 1000),
            )
        return self._client

    def embed_query(self, text: str) -> list[float]:
        from google.genai import types

        client = self._get_client()  # en una variable: encadenarlo cierra el httpx (D37)
        config = types.EmbedContentConfig(
            output_dimensionality=self.cfg.embedding_dim,
            task_type="RETRIEVAL_QUERY",
        )
        response = call_with_retry(
            lambda: client.models.embed_content(
                model=self.cfg.embedding_model, contents=text, config=config
            ),
            retries=self.cfg.api_max_retries,
        )
        return _normalize(list(response.embeddings[0].values))


class InMemoryVectorStore:
    """Store en memoria: tests y calibración sin base. Cada entrada es (chunk, vector)."""

    def __init__(self, items: list[tuple[Chunk, list[float]]]) -> None:
        self._items = items

    def search(self, vector: list[float], top_k: int) -> list[Chunk]:
        scored = [replace(chunk, similarity=cosine(vector, v)) for chunk, v in self._items]
        return sorted(scored, key=lambda c: c.similarity, reverse=True)[:top_k]


class PgVectorStore:
    """Búsqueda por distancia de coseno sobre `documentos_chunks` (pgvector, D13, D66)."""

    def __init__(self, config: Config | None = None, conn=None) -> None:
        self.cfg = config or load_config()
        self._conn = conn
        self._owns_conn = conn is None

    def _connection(self):
        if self._conn is None or getattr(self._conn, "closed", 0):
            import psycopg2  # diferido: los tests offline no requieren el paquete

            from agent.tools.sql_tool import connection_options

            self._conn = psycopg2.connect(
                dbname=self.cfg.db_name,
                user=self.cfg.db_user,
                host=self.cfg.db_host,
                port=self.cfg.db_port,
                password=os.environ.get("POSTGRES_PASSWORD"),  # Art. 9
                options=connection_options(self.cfg),
                sslmode=self.cfg.db_sslmode or None,
                connect_timeout=self.cfg.api_timeout_s,
            )
            self._conn.set_session(readonly=True)
            self._owns_conn = True
        return self._conn

    def close(self) -> None:
        if self._conn is not None and self._owns_conn:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def search(self, vector: list[float], top_k: int) -> list[Chunk]:
        literal = "[" + ",".join(repr(float(x)) for x in vector) + "]"
        # `<=>` es la distancia de coseno: similitud = 1 - distancia. El ORDER BY usa el índice HNSW.
        # El esquema no tiene columna de ubicación: sale de `metadata` (sección, ubicación o página) y,
        # si no hay nada, del número de fragmento. `content_hash` es el sha256 del documento + el índice
        # del fragmento: estable entre corridas y único por fragmento.
        sql = (
            "SELECT c.id, d.nombre_archivo, "
            "COALESCE(c.metadata->>'seccion', c.metadata->>'ubicacion', "
            "'p. ' || (c.metadata->>'pagina'), 'fragmento ' || c.chunk_index::text), "
            "c.contenido, COALESCE(d.sha256, d.nombre_archivo) || ':' || c.chunk_index::text, "
            "1 - (c.embedding <=> %s::vector) AS similarity "
            f"FROM {CHUNKS_TABLE} c JOIN {DOCUMENTS_TABLE} d ON d.id = c.documento_id "
            "ORDER BY c.embedding <=> %s::vector LIMIT %s"
        )
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (literal, literal, int(top_k)))
                rows = cur.fetchall()
        finally:
            conn.rollback()
        return [
            Chunk(id=r[0], document=r[1], location=r[2], text=r[3], content_hash=r[4], similarity=float(r[5]))
            for r in rows
        ]


# --------------------------------------------------------------------------- retriever


class RagRetriever:
    """Top-k por coseno con umbral mínimo; sin resultados relevantes lo reporta (R-4.4, R-4.6)."""

    def __init__(self, embedder: Embedder, store: VectorStore, config: Config | None = None) -> None:
        self.embedder = embedder
        self.store = store
        self.cfg = config or load_config()

    def _candidates(self, query: str) -> list[Chunk]:
        vector = self.embedder.embed_query(query)
        return sorted(self.store.search(vector, self.cfg.top_k), key=lambda c: c.similarity, reverse=True)

    def retrieve(self, query: str) -> RagResult:
        started = time.perf_counter()

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started) * 1000)

        if not query.strip():
            return RagResult(chunks=[], error=RETRIEVAL_ERROR, latency_ms=0)
        try:
            candidates = self._candidates(query)
        except Exception:  # noqa: BLE001 - R-5.7: el error se reporta, no se responde sin datos
            return RagResult(chunks=[], error=RETRIEVAL_ERROR, latency_ms=elapsed_ms())

        relevant = [c for c in candidates if c.similarity >= self.cfg.similarity_threshold][: self.cfg.top_k]
        if not relevant:
            return RagResult(chunks=[], error=NO_RELEVANT_RESULTS, latency_ms=elapsed_ms())
        return RagResult(chunks=relevant, error=None, latency_ms=elapsed_ms())

    def scores(self, query: str) -> list[float]:
        """Similitudes del top-k **sin** aplicar el umbral. Insumo de la calibración (R-4.8)."""
        return [c.similarity for c in self._candidates(query)]
