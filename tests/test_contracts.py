"""Reglas de los contratos (T4.5, T5.2, T7.1, Art. 4)."""
from __future__ import annotations

from agent.contracts import AgentAnswer, Chunk, RagResult, SqlResult


def test_sql_result_reports_error_without_executing() -> None:
    r = SqlResult(
        sql="DELETE FROM prestamos WHERE socio_id = 1",
        rows=[],
        error="SQL_NOT_READONLY",
        executed=False,
        attempts=1,
        latency_ms=3,
    )
    assert r.executed is False
    assert r.error is not None
    assert r.attempts >= 1


def test_attempts_regenera_hasta_el_limite() -> None:
    # D8 / R-3.10: primer intento rechazado, segundo válido.
    r = SqlResult(
        sql="SELECT * FROM libros",
        rows=[{"id": 1}],
        error=None,
        executed=True,
        attempts=2,
        latency_ms=40,
    )
    assert r.executed and r.attempts == 2


def test_chunk_conserva_origen_y_hash() -> None:
    c = Chunk(
        id=1,
        document="reglamento_biblioteca.pdf",
        location="Art. 12",
        text="El plazo de devolución es de 15 días.",
        content_hash="abc123",
        similarity=0.61,
    )
    assert c.document and c.location
    assert c.content_hash


def test_answer_declara_fuente_y_evidencia() -> None:
    a = AgentAnswer(
        question="¿Cuántos días tengo para devolver un libro?",
        classification="rag",
        sources=["rag"],
        answer="El plazo es de 15 días según el reglamento.",
        evidence={"chunks": [{"document": "reglamento_biblioteca.pdf", "location": "Art. 12"}]},
    )
    assert a.is_valid(), a.violations()


def test_answer_sin_fuente_debe_declarar_ausencia() -> None:
    bad = AgentAnswer(
        question="¿Cuál es el precio del libro X?",
        classification="none",
        sources=[],
        answer="El libro X cuesta 20 dólares.",
    )
    assert not bad.is_valid()
    assert any("ausencia" in v for v in bad.violations())

    good = AgentAnswer(
        question="¿Cuál es el precio del libro X?",
        classification="none",
        sources=[],
        answer="No dispongo de información suficiente para responder.",
    )
    assert good.is_valid(), good.violations()


def test_fuente_declarada_debe_coincidir_con_la_invocada() -> None:
    # R-2.7: la fuente de la respuesta es la efectivamente invocada.
    bad = AgentAnswer(
        question="¿Qué libros tiene Juan Pérez?",
        classification="sql",
        sources=["rag"],
        answer="Tiene 3 libros.",
        evidence={"chunks": []},
    )
    assert not bad.is_valid()
    assert any("no coincide" in v for v in bad.violations())
