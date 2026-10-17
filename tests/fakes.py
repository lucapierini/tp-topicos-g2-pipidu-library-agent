"""Dobles de prueba compartidos: sin base, sin API y sin red (Art. 6)."""
from __future__ import annotations

from types import SimpleNamespace

from agent.classifier import Classification, ClassificationError
from agent.config import load_config
from agent.contracts import Chunk, RagResult, ToolSpec
from agent.tools.sql_tool import SqlExecutor

# --------------------------------------------------------------------------- base de datos


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.fetched_limit = None

    @property
    def description(self):
        return [(col,) for col in self.conn.columns]

    def execute(self, sql):
        if self.conn.exc is not None and not sql.startswith("SET LOCAL"):
            raise self.conn.exc
        self.conn.executed.append(sql)

    def fetchmany(self, n):
        self.fetched_limit = n
        return self.conn.rows[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, rows=None, columns=None, exc=None):
        self.rows = rows if rows is not None else [(1,), (2,)]
        self.columns = columns if columns is not None else ["id"]
        self.exc = exc
        self.executed: list[str] = []
        self.rollbacks = 0
        self.closed = 0

    def cursor(self):
        return FakeCursor(self)

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1


def sql_backend(rows=None, columns=None, exc=None) -> SqlExecutor:
    """El executor **real** (validador incluido) sobre una conexión falsa."""
    return SqlExecutor(load_config(), FakeConn(rows=rows, columns=columns, exc=exc))


# --------------------------------------------------------------------------- recuperación


def make_chunk(document="reglamento_biblioteca.pdf", location="Art. 12", text="El plazo es de 15 días.",
               similarity=0.8, chunk_id=1) -> Chunk:
    return Chunk(id=chunk_id, document=document, location=location, text=text,
                 content_hash=f"hash-{chunk_id}", similarity=similarity)


class FakeRetriever:
    def __init__(self, result: RagResult | None = None):
        self.result = result or RagResult(chunks=[make_chunk()], error=None, latency_ms=1)
        self.queries: list[str] = []

    def retrieve(self, query: str) -> RagResult:
        self.queries.append(query)
        return self.result


class FakeEmbedder:
    """Vectores por palabra clave: determinista y sin red."""

    def __init__(self, vectors: dict[str, list[float]] | None = None, default=None, error=None):
        self.vectors = vectors or {}
        self.default = default or [0.0, 0.0, 1.0]
        self.error = error
        self.calls: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.error:
            raise self.error
        for keyword, vector in self.vectors.items():
            if keyword in text:
                return vector
        return self.default


# --------------------------------------------------------------------------- clasificador


class FakeClassifier:
    def __init__(
        self, label="sql", language="es", error: Exception | None = None, write_request=False, greeting=False,
    ):
        self.label, self.language, self.error, self.write_request = label, language, error, write_request
        self.greeting = greeting
        self.questions: list[str] = []

    def classify(self, question: str) -> Classification:
        self.questions.append(question)
        if self.error:
            raise self.error
        return Classification(label=self.label, language=self.language, rationale="fake",
                              write_request=self.write_request, greeting=self.greeting)


class FakeGenaiClient:
    """Reemplaza `genai.Client`: registra los parámetros de `generate_content`."""

    def __init__(self, text: str = "", error: Exception | None = None):
        self.calls: list[dict] = []
        self._text, self._error = text, error
        self.models = SimpleNamespace(generate_content=self._generate, embed_content=self._embed)
        self.embed_calls: list[dict] = []
        self.embedding_values: list[float] = [3.0, 4.0]

    def _generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(text=self._text)

    def _embed(self, **kwargs):
        self.embed_calls.append(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=self.embedding_values)])


# --------------------------------------------------------------------------- runner


class ScriptedRunner:
    """Hace lo que haría el modelo: invoca las tools indicadas, en orden, y devuelve un texto.

    `steps` es una lista de `(tool_name, argumento)`. Una tool que no se le ofreció al modelo
    no se puede invocar: se levanta `KeyError`, igual que en el agente real.
    """

    def __init__(self, steps=(), text="Respuesta.", error: Exception | None = None):
        self.steps, self.text, self.error = list(steps), text, error
        self.offered: list[str] = []
        self.system_prompt = ""
        self.observations: list[str] = []
        self.max_steps = None
        self.calls = 0

    def run(self, *, question: str, system_prompt: str, tools: list[ToolSpec], max_steps: int,
            on_event=None, cancel=None) -> str:
        self.calls += 1
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.offered = [t.name for t in tools]
        if self.error:
            raise self.error
        by_name = {t.name: t for t in tools}
        for name, argument in self.steps:
            self.observations.append(by_name[name].fn(argument))
        return self.text


__all__ = [
    "ClassificationError", "FakeClassifier", "FakeConn", "FakeCursor", "FakeEmbedder",
    "FakeGenaiClient", "FakeRetriever", "ScriptedRunner", "make_chunk", "sql_backend",
]
