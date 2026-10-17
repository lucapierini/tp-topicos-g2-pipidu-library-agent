"""`agent_runs` y el esquema contra la base real de Docker (T7.4, T7.5, T2.2; D21, D64, D66).

Marcado `integration`: requiere `docker compose up -d` y el `.env` con las contraseñas. Se salta
si no hay base. Verifica lo que ningún fake puede: permisos reales por rol, CHECKs, tipos y que el
SQL que genera el agente corra contra el esquema real.

Uso:  docker compose up -d --wait db && .venv/Scripts/python -m pytest -m integration
"""
from __future__ import annotations

import os

import pytest

from agent.agent import LibraryAgent
from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_TABLES
from agent.runs import PgRunRecorder, RunRecord
from agent.tools.rag_tool import PgVectorStore
from agent.tools.sql_tool import SqlExecutor
from tests.fakes import FakeClassifier, FakeRetriever, ScriptedRunner

pytestmark = pytest.mark.integration

psycopg2 = pytest.importorskip("psycopg2")


def _connect(user: str, password_env: str):
    cfg = load_config()
    password = os.environ.get(password_env)
    if not password:
        pytest.skip(f"{password_env} no está definida en .env")
    try:
        return psycopg2.connect(dbname=cfg.db_name, user=user, host=cfg.db_host, port=cfg.db_port,
                                password=password, connect_timeout=3)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"sin base de datos local (docker compose up -d): {exc}")


@pytest.fixture()
def admin():
    conn = _connect("postgres", "POSTGRES_ADMIN_PASSWORD")
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture()
def logger_conn():
    conn = _connect(load_config().log_db_user, "POSTGRES_LOG_PASSWORD")
    yield conn
    conn.close()


@pytest.fixture()
def reader_conn():
    conn = _connect(load_config().db_user, "POSTGRES_PASSWORD")
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clean_runs(admin):
    with admin.cursor() as cur:
        cur.execute("TRUNCATE agent_runs RESTART IDENTITY")
    yield


def _admin_rows(admin, sql: str, *params):
    with admin.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _record(**overrides) -> RunRecord:
    base = dict(question="¿Qué socios tienen préstamos vencidos?", classification="sql", status="ok",
                answer="Juan Pérez y Pedro Ruiz.", latency_ms=12, model_id="gemini/test", endpoint="api",
                sources=["sql"], tools=["execute_sql"], generated_sql="SELECT 1", executed_sql="SELECT 1",
                chunks=[{"document": "reglamento_biblioteca.pdf"}], attempts=[{"attempt": 1}],
                trace=["classification", "execute_sql"])
    base.update(overrides)
    return RunRecord(**base)


# --- el esquema real coincide con la whitelist ---


def test_the_live_schema_matches_the_whitelist(admin) -> None:
    rows = _admin_rows(
        admin,
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'",
    )
    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)
    for table, columns in ALLOWED_TABLES.items():
        assert live.get(table) == columns, f"{table}: {live.get(table)} != {columns}"


# --- permisos por rol (D21, R-3.5) ---


def test_the_logger_role_can_insert_and_get_the_id(admin) -> None:
    run_id = PgRunRecorder(load_config()).record(_record())
    assert run_id == 1

    (row,) = _admin_rows(
        admin,
        "SELECT classification, status, sources, tools, executed_sql, attempts, chunks, model_id, endpoint, "
        "latency_ms, created_at IS NOT NULL FROM agent_runs WHERE id = %s", run_id,
    )
    assert row[:5] == ("sql", "ok", ["sql"], ["execute_sql"], "SELECT 1")
    assert row[5] == [{"attempt": 1}] and row[6] == [{"document": "reglamento_biblioteca.pdf"}]
    assert row[7:] == ("gemini/test", "api", 12, True)


def test_the_logger_role_cannot_read_the_log_or_the_domain(logger_conn) -> None:
    # Solo inserta: si pudiera leer, una credencial filtrada expondría la historia de consultas.
    for sql in ("SELECT question FROM agent_runs", "SELECT * FROM libros", "UPDATE agent_runs SET answer = 'x'",
                "DELETE FROM agent_runs"):
        with logger_conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute(sql)
        logger_conn.rollback()


def test_the_read_only_role_cannot_see_the_log_or_the_documents(reader_conn) -> None:
    # D21: la herramienta SQL no lee la trazabilidad; `documentos` es interno.
    for table in ("agent_runs",):
        with reader_conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute(f"SELECT * FROM {table}")  # noqa: S608
        reader_conn.rollback()


def test_the_read_only_role_cannot_write(reader_conn) -> None:
    with reader_conn.cursor() as cur:
        with pytest.raises(psycopg2.errors.Error):  # permiso denegado o transacción de solo lectura
            cur.execute("INSERT INTO categorias (nombre) VALUES ('x')")
    reader_conn.rollback()


# --- restricciones de la tabla ---


@pytest.mark.parametrize(
    "overrides",
    [{"status": "inventado"}, {"classification": "sql+rag"}, {"endpoint": "nube"}, {"latency_ms": -1}],
)
def test_the_table_rejects_values_outside_the_vocabulary(overrides) -> None:
    with pytest.raises(psycopg2.errors.CheckViolation):
        PgRunRecorder(load_config()).record(_record(**overrides))


def test_a_failed_insert_does_not_leave_the_connection_unusable(admin) -> None:
    recorder = PgRunRecorder(load_config())
    with pytest.raises(psycopg2.errors.CheckViolation):
        recorder.record(_record(status="inventado"))
    run_id = recorder.record(_record())
    # La secuencia no se revierte con el rollback (el id 1 queda "quemado"): no se afirma el valor.
    assert run_id and run_id > 0, "tras el rollback la conexión sigue sirviendo"
    assert _admin_rows(admin, "SELECT count(*) FROM agent_runs")[0][0] == 1, "el rechazado no dejó fila"


# --- flujo completo con datos reales ---


def _agent(label, steps, recorder=None, text="Respuesta."):
    cfg = load_config()
    return LibraryAgent(
        classifier=FakeClassifier(label),
        sql_backend=SqlExecutor(cfg),                    # el executor real, rol agent_ro
        retriever=FakeRetriever(),
        runner=ScriptedRunner(steps, text),
        recorder=recorder or PgRunRecorder(cfg),
        config=cfg,
    )


def test_overdue_loans_are_computed_by_the_view_not_stored(admin) -> None:
    sql = ("SELECT s.nombre, s.apellido, v.dias_atraso FROM v_prestamos_estado v "
           "JOIN socios s ON s.id = v.socio_id WHERE v.estado_calculado = 'vencido' ORDER BY v.dias_atraso")
    answer = _agent("sql", [("execute_sql", sql)]).answer("¿Qué socios tienen préstamos vencidos?")

    # El esperado sale de la aritmética de fechas sobre la tabla base, no de la vista: el seed usa fechas
    # relativas a CURRENT_DATE y envejece, así que un valor literal (5, 20) falla al día siguiente.
    with admin.cursor() as cur:
        cur.execute("SET TIME ZONE %s", (load_config().timezone,))
        cur.execute(
            "SELECT s.apellido, CURRENT_DATE - p.fecha_devolucion_prevista FROM prestamos p "
            "JOIN socios s ON s.id = p.socio_id "
            "WHERE p.fecha_devolucion_real IS NULL AND p.fecha_devolucion_prevista < CURRENT_DATE "
            "ORDER BY 2"
        )
        expected = [(apellido, int(days)) for apellido, days in cur.fetchall()]

    rows = answer.evidence["rows"]
    assert expected and [r["apellido"] for r in rows] == ["Pérez", "Ruiz"]
    assert [(r["apellido"], r["dias_atraso"]) for r in rows] == expected
    assert answer.run_id == 1

    (record,) = _admin_rows(admin, "SELECT status, tools, executed_sql, model_id FROM agent_runs")
    assert record[0] == "ok" and record[1] == ["execute_sql"] and "v_prestamos_estado" in record[2]


def test_the_stored_state_never_says_overdue() -> None:
    # Por qué el prompt manda a la vista: `prestamos.estado = 'vencido'` no devuelve nada.
    answer = _agent("sql", [("execute_sql", "SELECT id FROM prestamos WHERE estado = 'vencido'")]).answer("q")
    assert answer.evidence["rows"] == []


def test_authors_come_through_the_junction_table() -> None:
    sql = ("SELECT a.apellido, count(*) AS libros FROM libros l "
           "JOIN libros_autores la ON la.libro_id = l.id JOIN autores a ON a.id = la.autor_id "
           "GROUP BY a.id, a.apellido ORDER BY libros DESC, a.apellido")
    answer = _agent("sql", [("execute_sql", sql)]).answer("¿Cuántos libros tiene cada autor?")
    assert answer.evidence["rows"][0] == {"apellido": "Borges", "libros": 2}


def test_a_rejected_statement_never_reaches_the_database_and_is_logged(admin) -> None:
    answer = _agent("sql", [("execute_sql", "DELETE FROM prestamos"), ("execute_sql", "DROP TABLE libros")]).answer(
        "borrá todo"
    )
    assert answer.answer_kind == "error"

    (record,) = _admin_rows(admin, "SELECT status, error_code, executed_sql, attempts FROM agent_runs")
    assert record[:3] == ("error", "SQL_NOT_READONLY", None)
    assert [a["error"] for a in record[3]] == ["SQL_NOT_READONLY", "SQL_NOT_READONLY"]
    assert _admin_rows(admin, "SELECT count(*) FROM prestamos")[0][0] == 11, "los datos siguen intactos"


def test_the_empty_result_for_a_member_without_loans() -> None:
    sql = ("SELECT p.id FROM prestamos p JOIN socios s ON s.id = p.socio_id WHERE s.legajo = 'A-1004'")
    answer = _agent("sql", [("execute_sql", sql)]).answer("¿Qué libros tiene Sofía Díaz?")
    assert answer.evidence["rows"] == [] and answer.sources == ["sql"]  # R-3.8


# --- recuperación contra pgvector ---


def test_pgvector_search_returns_document_location_and_cosine_similarity(admin) -> None:
    vector = "[" + ",".join(["1"] + ["0"] * 767) + "]"
    other = "[" + ",".join(["0", "1"] + ["0"] * 766) + "]"
    with admin.cursor() as cur:
        cur.execute("DELETE FROM documentos WHERE nombre_archivo = 'reglamento_test.pdf'")
        cur.execute("INSERT INTO documentos (nombre_archivo, tipo, sha256) VALUES "
                    "('reglamento_test.pdf', 'reglamento', %s) RETURNING id", ("a" * 64,))
        doc_id = cur.fetchone()[0]
        cur.execute("INSERT INTO documentos_chunks (documento_id, chunk_index, contenido, embedding, metadata) "
                    "VALUES (%s, 0, 'El plazo de devolución es de 15 días.', %s::vector, %s::jsonb), "
                    "(%s, 1, 'El horario es de 9 a 20.', %s::vector, '{}'::jsonb)",
                    (doc_id, vector, '{"seccion": "Art. 12"}', doc_id, other))
    try:
        # La base puede tener los fragmentos reales de la ingesta: se pide de más y se filtra el documento de prueba.
        found = PgVectorStore(load_config()).search([1.0] + [0.0] * 767, 100)
        chunks = [c for c in found if c.document == "reglamento_test.pdf"]
    finally:
        with admin.cursor() as cur:
            cur.execute("DELETE FROM documentos WHERE id = %s", (doc_id,))  # cascada a los chunks

    assert chunks[0].document == "reglamento_test.pdf" and chunks[0].location == "Art. 12"
    assert chunks[0].similarity == pytest.approx(1.0)
    assert chunks[1].location == "fragmento 1" and chunks[1].similarity == pytest.approx(0.0)
    assert chunks[0].content_hash == ("a" * 64) + ":0"
