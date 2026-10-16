"""La whitelist debe coincidir con `db/schema.sql` (T4.1, R-3.4).

Este test es el contrato entre el desarrollo del agente y el modelo de datos:
si el integrante que arma el esquema cambia una tabla o una columna, acá se rompe
en el mismo commit. Es **bidireccional**: una columna que existe y no está en la whitelist es
inalcanzable (y `SELECT *` no la devuelve); una columna en la whitelist que no existe hace que el
modelo genere SQL inválido (D64).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent.config.schema_whitelist import ALLOWED_FUNCTIONS, ALLOWED_TABLES, FORBIDDEN_TABLES

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"

_NOT_COLUMNS = {"CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN"}


def _schema_text() -> str:
    return SCHEMA.read_text(encoding="utf-8")


def _table_columns(text: str, table: str) -> set[str]:
    block = re.search(rf"CREATE TABLE\s+{table}\s*\((.*?)\n\);", text, re.I | re.S)
    assert block, f"{table} no aparece en schema.sql"
    names = re.findall(r"^\s{2}(\w+)\s+\w", block.group(1), re.M)
    return {n for n in names if n.upper() not in _NOT_COLUMNS}


@pytest.mark.skipif(not SCHEMA.exists(), reason="falta db/schema.sql")
def test_whitelist_matches_schema_sql() -> None:
    text = _schema_text()
    tables = set(re.findall(r"CREATE TABLE(?: IF NOT EXISTS)?\s+(\w+)", text, flags=re.I))
    views = set(re.findall(r"CREATE VIEW(?: IF NOT EXISTS)?\s+(\w+)", text, flags=re.I))
    internal = tables & FORBIDDEN_TABLES  # documentos, documentos_chunks: excluidos a propósito (D21)

    allowed = set(ALLOWED_TABLES)
    assert (tables - internal) <= allowed, f"tablas del esquema fuera de la whitelist: {tables - internal - allowed}"
    assert views <= allowed, f"vistas del esquema fuera de la whitelist: {views - allowed}"
    assert allowed <= (tables | views), f"la whitelist nombra objetos que no existen: {allowed - tables - views}"

    for table, columns in ALLOWED_TABLES.items():
        if table in views:
            continue
        actual = _table_columns(text, table)
        assert actual == columns, (
            f"{table}: en el esquema y no en la whitelist {actual - columns}; "
            f"en la whitelist y no en el esquema {columns - actual}"
        )


@pytest.mark.skipif(not SCHEMA.exists(), reason="falta db/schema.sql")
def test_view_columns_exist_in_the_view_definition() -> None:
    text = _schema_text()
    view = re.search(r"CREATE VIEW\s+v_prestamos_estado\s+AS\s+(.*?);", text, re.I | re.S)
    assert view, "v_prestamos_estado no aparece en schema.sql"
    for column in ALLOWED_TABLES["v_prestamos_estado"]:
        assert re.search(rf"\b{column}\b", view.group(1)), f"la vista no define {column}"


def test_internal_tables_are_never_allowed() -> None:
    # La herramienta SQL lee el dominio, nunca la trazabilidad ni el repositorio documental.
    for table in FORBIDDEN_TABLES:
        assert table not in ALLOWED_TABLES
    assert {"agent_runs", "documentos", "documentos_chunks"} <= FORBIDDEN_TABLES


def test_overdue_state_lives_in_the_calculated_view() -> None:
    # D7 / R-3.12 / D64: la tabla guarda solo activo/devuelto (CHECK en el esquema); el vencimiento
    # es `estado_calculado` en la vista, la única forma de que el agente consulte "vencido".
    assert "v_prestamos_estado" in ALLOWED_TABLES
    assert {"estado_calculado", "dias_atraso"} <= ALLOWED_TABLES["v_prestamos_estado"]
    assert "estado_calculado" not in ALLOWED_TABLES["prestamos"]
    assert "estado" in ALLOWED_TABLES["prestamos"]


def test_books_reach_their_authors_through_the_junction_table() -> None:
    # Un libro puede tener varios autores: `libros` no tiene `autor_id` (D64).
    assert "autor_id" not in ALLOWED_TABLES["libros"]
    assert {"libro_id", "autor_id"} <= ALLOWED_TABLES["libros_autores"]


def test_sqlglot_schema_mirrors_the_whitelist() -> None:
    from agent.config.schema_whitelist import sqlglot_schema

    schema = sqlglot_schema()
    assert set(schema) == set(ALLOWED_TABLES)
    for table, columns in ALLOWED_TABLES.items():
        assert set(schema[table]) == columns


def test_allowlist_only_contains_postgres_function_names() -> None:
    # `instr`, `datediff` y `timestamp_trunc` son de otros dialectos: no existen en PostgreSQL.
    for name in ("instr", "datediff", "timestamp_trunc"):
        assert name not in ALLOWED_FUNCTIONS


def test_function_allowlist_excludes_side_effect_functions() -> None:
    # R-3.13: el timeout limita el tiempo, no los efectos. Una función de efecto no
    # puede resolverse con "el timeout la corta".
    for fn in ("pg_sleep", "pg_read_file", "dblink", "pg_advisory_lock", "lo_import", "system"):
        assert fn not in ALLOWED_FUNCTIONS
    for fn in ("count", "max", "round", "coalesce", "current_date", "extract"):
        assert fn in ALLOWED_FUNCTIONS
