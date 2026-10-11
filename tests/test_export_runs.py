"""Export de `agent_runs` a un archivo versionable (T7.7; R-6.1, R-6.2).

La tabla no es una evidencia durable: el fixture de integración la trunca. El informe necesita las 13
consultas del golden set en un archivo del repo, con los ocho campos de R-6.1 y el modelo (R-6.5).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scripts.export_runs import build_payload, fetch_runs, write_payload

COLUMNS = ["id", "created_at", "question", "classification", "status", "sources", "tools",
           "generated_sql", "executed_sql", "chunks", "answer", "latency_ms", "attempts",
           "error_code", "error_detail", "model_id", "endpoint", "trace"]


def _row(i: int, classification="sql", status="ok", model="gemini/gemini-3.1-flash-lite") -> tuple:
    return (i, datetime(2026, 10, 11, 12, 0, i, tzinfo=UTC), f"pregunta {i}", classification, status,
            ["sql"], ["execute_sql"], "select 1", "SELECT 1", [], "respuesta", 120 + i, [],
            None, None, model, "api", ["classification", "execute_sql"])


def _run(row: tuple) -> dict:
    return dict(zip(COLUMNS, row, strict=True))


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.description = [(name,) for name in COLUMNS]
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj

    def rollback(self):
        pass


def test_fetch_runs_returns_one_dict_per_row_with_every_column() -> None:
    runs = fetch_runs(FakeConn([_row(1), _row(2)]))

    assert [r["id"] for r in runs] == [1, 2]
    assert set(runs[0]) == set(COLUMNS)


def test_fetch_runs_reads_in_order_and_can_limit_to_the_latest() -> None:
    conn = FakeConn([_row(1)])

    fetch_runs(conn, last=13)

    assert "ORDER BY ID" in conn.cursor_obj.sql.upper()
    assert conn.cursor_obj.params == (13,)


def test_payload_summarises_status_classification_and_model() -> None:
    runs = [
        _run(_row(1)),
        _run(_row(2, "rag")),
        _run(_row(3, "none", "no_coverage")),
    ]

    payload = build_payload(runs)

    assert payload["count"] == 3
    assert payload["by_classification"] == {"sql": 1, "rag": 1, "none": 1}
    assert payload["by_status"] == {"ok": 2, "no_coverage": 1}
    assert payload["models"] == ["gemini/gemini-3.1-flash-lite"]
    assert payload["endpoints"] == ["api"]


def test_a_local_model_run_is_flagged_as_not_acceptance_evidence() -> None:
    # R-2.8 / R-6.5: una corrida local no puede confundirse con evidencia de aceptación.
    local = _run(_row(1, model="openai/qwen3.8"))
    local["endpoint"] = "local"

    assert build_payload([local])["counts_as_acceptance_evidence"] is False


def test_an_api_only_export_is_not_flagged() -> None:
    assert build_payload([_run(_row(1))])["counts_as_acceptance_evidence"] is True


def test_the_written_file_is_valid_json_and_keeps_utf8(tmp_path) -> None:
    runs = [_run(_row(1))]
    runs[0]["question"] = "¿Qué libros tiene prestados Juan Pérez?"
    out = tmp_path / "evidencia" / "agent_runs.json"

    write_payload(build_payload(runs), out)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["runs"][0]["question"] == "¿Qué libros tiene prestados Juan Pérez?"
    assert data["runs"][0]["created_at"] == "2026-10-11T12:00:01+00:00"


def test_an_empty_table_is_reported_not_silently_exported() -> None:
    with pytest.raises(ValueError, match="agent_runs está vacía"):
        build_payload([])
