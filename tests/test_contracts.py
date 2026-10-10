"""Reglas de los contratos (T4.5, T5.2, T7.1, Art. 4)."""
from __future__ import annotations

from agent.contracts import AgentAnswer, Chunk, SqlResult, normalize_classification


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


def test_none_declara_ausencia_de_forma_estructural() -> None:
    # D52: el campo estructural no depende de que la prosa matchee una regex.
    a = AgentAnswer(
        question="¿Cuál es el precio del libro Rayuela?",
        classification="none",
        sources=[],
        answer="Ese dato no figura en los registros de la biblioteca.",
        answer_kind="no_coverage",
    )
    assert a.is_valid(), a.violations()


def test_none_sin_marcador_ni_frase_de_ausencia_es_invalido() -> None:
    a = AgentAnswer(
        question="¿Precio?", classification="none", sources=[], answer="Cuesta 20 dólares."
    )
    assert not a.is_valid()


def test_hibrido_exige_evidencia_de_las_dos_fuentes() -> None:
    # R-2.4: declarar `sql` y `rag` con la evidencia de una sola no prueba que se invocaron ambas.
    solo_sql = AgentAnswer(
        question="¿Le corresponde multa?",
        classification="hybrid",
        sources=["sql", "rag"],
        answer="Sí.",
        evidence={"sql": "SELECT 1", "rows": [{"dias": 20}]},
    )
    assert not solo_sql.is_valid()
    assert any("rag" in v for v in solo_sql.violations())

    completa = AgentAnswer(
        question="¿Le corresponde multa?",
        classification="hybrid",
        sources=["sql", "rag"],
        answer="Sí, según el Art. 12.",
        evidence={
            "sql": "SELECT 1",
            "rows": [{"dias": 20}],
            "chunks": [{"document": "reglamento_biblioteca.pdf", "location": "Art. 12"}],
        },
    )
    assert completa.is_valid(), completa.violations()


def test_sql_exige_la_sentencia_ejecutada_en_la_evidencia() -> None:
    a = AgentAnswer(
        question="¿Cuántos libros hay?",
        classification="sql",
        sources=["sql"],
        answer="Hay 40.",
        evidence={"rows": [{"count": 40}]},
    )
    assert not a.is_valid()


def test_clasificacion_sql_mas_rag_no_es_parte_del_vocabulario() -> None:
    # D50: el vocabulario es el de la spec (`hybrid`). `sql+rag` no es una clasificación válida.
    a = AgentAnswer(question="q", classification="sql+rag", sources=["sql", "rag"], answer="a", evidence={"x": 1})
    assert any("inválida" in v for v in a.violations())


def test_normalize_classification_tolera_mayusculas_y_espacios() -> None:
    assert normalize_classification(" SQL ") == "sql"
    assert normalize_classification("Hybrid") == "hybrid"


def test_la_clasificacion_se_emite_antes_de_las_tools() -> None:
    ok = AgentAnswer(question="q", classification="none", sources=[], answer="No hay datos.",
                     trace=["classification"])
    tarde = AgentAnswer(question="q", classification="sql", sources=["sql"], answer="a",
                        trace=["execute_sql", "classification"])
    assert ok.classified_before_tools
    assert not tarde.classified_before_tools
    assert not AgentAnswer(question="q", classification="none", sources=[], answer="a").classified_before_tools


def test_as_outcome_expone_clasificacion_sql_filas_y_chunks() -> None:
    a = AgentAnswer(
        question="q",
        classification="hybrid",
        sources=["sql", "rag"],
        answer="a",
        evidence={"sql": "SELECT 1", "rows": [{"n": 1}], "chunks": [{"document": "r.pdf"}]},
        trace=["classification", "execute_sql", "retrieve"],
    )
    out = a.as_outcome()
    assert out["rows"] == [{"n": 1}] and out["chunks"] == [{"document": "r.pdf"}]
    assert out["sql"] == "SELECT 1"
    assert out["classification_emitted_before_tools"] is True


def test_sql_result_declara_truncado_y_motivo() -> None:
    r = SqlResult(sql=None, rows=[], error="COLUMN_NOT_ALLOWED", executed=False, attempts=1,
                  latency_ms=0, detail="columna no permitida: secreto")
    assert r.detail and r.truncated is False


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
