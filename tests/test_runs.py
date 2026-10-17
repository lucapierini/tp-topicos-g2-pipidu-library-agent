"""Trazabilidad `agent_runs` (T7.4, T7.5; R-6.1 a R-6.5, Art. 5). Sin base ni red (Art. 6)."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agent.agent import LibraryAgent
from agent.classifier import ClassificationError
from agent.config import load_config
from agent.contracts import RagResult
from agent.errors import NO_RELEVANT_RESULTS
from agent.runs import (
    INSERT_SQL,
    InMemoryRunRecorder,
    PgRunRecorder,
    RunRecord,
    build_recorder,
    record_from_answer,
)
from tests.fakes import FakeClassifier, FakeRetriever, ScriptedRunner, sql_backend

GOOD_SQL = "SELECT l.titulo FROM prestamos p JOIN libros l ON l.id = p.libro_id"
BAD_SQL = "DELETE FROM prestamos"


def agent_with(label="sql", *, steps=(), text="Tiene 2 libros.", retriever=None, classifier=None,
               recorder=None, exc=None, runner_error=None, **cfg):
    recorder = recorder if recorder is not None else InMemoryRunRecorder()
    agent = LibraryAgent(
        classifier=classifier or FakeClassifier(label),
        sql_backend=sql_backend(rows=[("Rayuela",), ("Ficciones",)], columns=["titulo"], exc=exc),
        retriever=retriever or FakeRetriever(),
        runner=ScriptedRunner(steps, text, error=runner_error),
        recorder=recorder,
        config=replace(load_config(), **cfg) if cfg else None,
    )
    return agent, recorder


# --- R-6.1: contenido del registro ---


def test_a_resolved_query_records_every_field_of_r_6_1() -> None:
    agent, recorder = agent_with("hybrid", steps=[("execute_sql", GOOD_SQL), ("retrieve_documents", "multa")])
    answer = agent.answer("¿Le corresponde multa?")

    (record,) = recorder.records
    assert record.question == "¿Le corresponde multa?"
    assert record.classification == "hybrid"
    assert record.tools == ["execute_sql", "retrieve_documents"]       # herramientas invocadas
    assert record.generated_sql == GOOD_SQL                            # sentencia generada
    assert record.executed_sql and record.executed_sql != GOOD_SQL     # normalizada (R-3.9)
    assert record.chunks and record.chunks[0]["document"] == "reglamento_biblioteca.pdf"
    assert record.answer == answer.answer
    assert record.latency_ms >= 0
    assert record.status == "ok" and record.sources == ["sql", "rag"]
    assert answer.run_id == 1


def test_the_record_comes_only_from_the_answer() -> None:
    # Art. 5: no hay una segunda fuente de verdad que pueda divergir de lo que vio el usuario.
    agent, recorder = agent_with("sql", steps=[("execute_sql", GOOD_SQL)])
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert recorder.records[0] == record_from_answer(answer, recorder.records[0].latency_ms)


def test_the_classification_is_not_listed_as_a_tool() -> None:
    agent, recorder = agent_with("sql", steps=[("execute_sql", GOOD_SQL)])
    agent.answer("¿Qué libros tiene Ana?")
    assert "classification" not in recorder.records[0].tools
    assert recorder.records[0].trace[0] == "classification"


# --- R-6.3: consultas rechazadas, fallidas y sin cobertura ---


def test_a_rejected_query_is_recorded_with_its_reason_and_latency() -> None:
    agent, recorder = agent_with("sql", steps=[("execute_sql", BAD_SQL), ("execute_sql", BAD_SQL)])
    answer = agent.answer("borrá los préstamos")

    (record,) = recorder.records
    assert record.status == "error"
    assert record.error_code == "SQL_NOT_READONLY" and record.error_detail
    assert record.executed_sql is None and record.generated_sql == BAD_SQL
    assert record.latency_ms >= 0
    assert answer.run_id == 1


def test_no_coverage_is_recorded_without_an_error() -> None:
    agent, recorder = agent_with("none")
    agent.answer("¿Cuál es el precio de Rayuela?")
    record = recorder.records[0]
    assert (record.status, record.classification, record.error_code) == ("no_coverage", "none", None)
    assert record.tools == [] and record.sources == []


def test_a_greeting_is_recorded_as_ok() -> None:
    from agent.runs import STATUS_BY_KIND

    assert STATUS_BY_KIND["greeting"] == "ok"


def test_rag_without_relevant_results_is_no_coverage_not_an_error() -> None:
    empty = FakeRetriever(RagResult(chunks=[], error=NO_RELEVANT_RESULTS, latency_ms=1))
    agent, recorder = agent_with("rag", steps=[("retrieve_documents", "precio")], retriever=empty)
    agent.answer("¿Cuánto cuesta el reglamento?")
    assert recorder.records[0].status == "no_coverage"
    assert recorder.records[0].error_code is None


def test_a_classifier_failure_is_recorded() -> None:
    agent, recorder = agent_with(classifier=FakeClassifier(error=ClassificationError("finish_reason=length")))
    agent.answer("¿Qué libros tiene Ana?")
    record = recorder.records[0]
    assert record.status == "error" and record.error_code == "CLASSIFICATION_ERROR"
    assert "finish_reason=length" in record.error_detail


def test_a_model_failure_is_recorded() -> None:
    agent, recorder = agent_with("sql", runner_error=TimeoutError("30s"))
    agent.answer("¿Qué libros tiene Ana?")
    assert recorder.records[0].error_code == "RUN_ERROR"


def test_a_database_failure_is_recorded_with_the_executor_error() -> None:
    agent, recorder = agent_with("sql", steps=[("execute_sql", GOOD_SQL)], exc=Exception("conexión caída"))
    agent.answer("¿Qué libros tiene Ana?")
    assert recorder.records[0].error_code == "EXECUTION_ERROR"


def test_an_empty_question_is_not_recorded() -> None:
    # R-1.2: no hay consulta que trazar; no se invoca nada.
    from agent.agent import EmptyQuestionError

    agent, recorder = agent_with("sql")
    with pytest.raises(EmptyQuestionError):
        agent.answer("   ")
    assert recorder.records == []


# --- R-6.4: intentos de generación ---


def test_each_generation_attempt_is_recorded_with_its_result() -> None:
    agent, recorder = agent_with("sql", steps=[("execute_sql", BAD_SQL), ("execute_sql", GOOD_SQL)])
    agent.answer("¿Qué libros tiene Ana?")

    attempts = recorder.records[0].attempts
    assert [a["attempt"] for a in attempts] == [1, 2]
    assert attempts[0]["executed"] is False and attempts[0]["error"] == "SQL_NOT_READONLY"
    assert attempts[0]["sql_original"] == BAD_SQL
    assert attempts[1]["executed"] is True and attempts[1]["rows"] == 2
    assert recorder.records[0].generated_sql == GOOD_SQL, "la sentencia generada es la del último intento"


# --- R-6.5: modelo ---


def test_the_model_and_endpoint_are_recorded_without_the_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "clave-secreta")
    agent, recorder = agent_with("sql", steps=[("execute_sql", GOOD_SQL)],
                                 llm_model="openai/qwen-local", llm_api_base="http://127.0.0.1:8080/v1")
    agent.answer("¿Qué libros tiene Ana?")

    record = recorder.records[0]
    assert (record.model_id, record.endpoint) == ("openai/qwen-local", "local")
    assert "clave-secreta" not in json.dumps(record.as_params(), default=str)
    assert "127.0.0.1" not in json.dumps(record.as_params(), default=str)


def test_a_remote_model_is_recorded_as_api() -> None:
    agent, recorder = agent_with("none")
    agent.answer("¿Precio?")
    assert recorder.records[0].endpoint == "api"
    assert recorder.records[0].model_id.startswith("gemini/")


# --- el registro no rompe la respuesta ---


class BrokenRecorder:
    def record(self, record):
        raise ConnectionError("base de trazabilidad caída")


def test_a_recording_failure_does_not_break_the_answer_and_is_declared() -> None:
    agent, _ = agent_with("sql", steps=[("execute_sql", GOOD_SQL)], recorder=BrokenRecorder())
    answer = agent.answer("¿Qué libros tiene Ana?")

    assert answer.sources == ["sql"] and answer.is_valid(), answer.violations()
    assert answer.run_id is None
    assert "ConnectionError" in answer.evidence["run_recording_error"]


def test_run_id_is_none_when_recording_is_off() -> None:
    agent = LibraryAgent(classifier=FakeClassifier("none"), runner=ScriptedRunner(),
                         config=replace(load_config(), runs_backend="off"))
    assert agent.answer("¿Precio?").run_id is None


# --- backends ---


def test_build_recorder_selects_the_backend_from_configuration() -> None:
    cfg = load_config()
    assert isinstance(build_recorder(replace(cfg, runs_backend="memory")), InMemoryRunRecorder)
    assert isinstance(build_recorder(replace(cfg, runs_backend="pg")), PgRunRecorder)
    assert build_recorder(replace(cfg, runs_backend="off")) is None
    with pytest.raises(ValueError, match="AGENT_RUNS_BACKEND"):
        build_recorder(replace(cfg, runs_backend="mongo"))


class _Cursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        if self.conn.error:
            raise self.conn.error
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return (42,)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Conn:
    def __init__(self, error=None):
        self.error, self.executed, self.commits, self.rollbacks, self.closed = error, [], 0, 0, 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _record() -> RunRecord:
    return RunRecord(question="q", classification="sql", status="ok", answer="a", latency_ms=5,
                     model_id="gemini/x", endpoint="api", sources=["sql"], tools=["execute_sql"],
                     chunks=[{"document": "r.pdf"}], attempts=[{"attempt": 1}], trace=["classification"])


def test_pg_recorder_inserts_commits_and_returns_the_id() -> None:
    conn = _Conn()
    run_id = PgRunRecorder(load_config(), conn=conn).record(_record())

    assert run_id == 42 and conn.commits == 1 and conn.rollbacks == 0
    sql, params = conn.executed[0]
    assert sql == INSERT_SQL and sql.lstrip().upper().startswith("INSERT INTO AGENT_RUNS")
    assert params[0] == "q" and params[3] == ["sql"]
    assert json.loads(params[7]) == [{"document": "r.pdf"}]   # jsonb viaja como texto con cast


def test_pg_recorder_rolls_back_on_failure_and_reraises() -> None:
    conn = _Conn(error=RuntimeError("violación de CHECK"))
    with pytest.raises(RuntimeError):
        PgRunRecorder(load_config(), conn=conn).record(_record())
    assert conn.rollbacks == 1 and conn.commits == 0


def test_pg_recorder_does_not_retry_the_connection_during_the_cooldown(monkeypatch) -> None:
    # Sin esto cada consulta pagaría el timeout de conexión completo con la base caída.
    import agent.runs as runs

    attempts = []

    class FakePsycopg:
        @staticmethod
        def connect(**kwargs):
            attempts.append(kwargs)
            raise ConnectionError("no hay base")

    monkeypatch.setitem(__import__("sys").modules, "psycopg2", FakePsycopg)
    recorder = runs.PgRunRecorder(load_config())
    for _ in range(3):
        with pytest.raises(ConnectionError):
            recorder.record(_record())
    assert len(attempts) == 1, "las dos siguientes caen en el período de espera"
    assert attempts[0]["user"] == load_config().log_db_user
    assert attempts[0]["connect_timeout"] <= 5


def test_the_logger_role_is_not_the_read_only_role() -> None:
    cfg = load_config()
    assert cfg.log_db_user == "agent_logger" and cfg.log_db_user != cfg.db_user


def test_status_vocabulary_matches_the_migration() -> None:
    from pathlib import Path

    migration = (Path(__file__).resolve().parents[1] / "db" / "migrations" / "001_agent_runs.sql").read_text(
        encoding="utf-8"
    )
    for value in ("ok", "no_coverage", "error", "local", "api", "sql", "rag", "hybrid", "none"):
        assert f"'{value}'" in migration
