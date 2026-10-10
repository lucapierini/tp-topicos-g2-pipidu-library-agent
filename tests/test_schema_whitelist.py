"""La whitelist debe coincidir con `db/schema.sql` (T4.1, R-3.4).

Este test es el contrato entre el desarrollo del agente y el modelo de datos:
si el integrante que arma el esquema cambia una tabla o una columna, acá se rompe
en el mismo commit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent.config.schema_whitelist import ALLOWED_FUNCTIONS, ALLOWED_TABLES, FORBIDDEN_TABLES

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


@pytest.mark.skipif(not SCHEMA.exists(), reason="db/schema.sql todavía no existe (T2.1)")
def test_whitelist_matches_schema_sql() -> None:
    # Art. 11: la whitelist no oculta columnas por política, debe cubrir el modelo completo.
    # Si el esquema tiene una columna, la whitelist la incluye; si no, la columna es
    # inalcanzable para el agente y el test se rompe en el mismo commit.
    text = SCHEMA.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE(?: IF NOT EXISTS)?\s+(\w+)", text, flags=re.I))
    views = set(re.findall(r"CREATE VIEW(?: IF NOT EXISTS)?\s+(\w+)", text, flags=re.I))

    allowed = set(ALLOWED_TABLES)
    assert tables <= allowed, f"tablas en el esquema fuera de la whitelist: {tables - allowed}"
    assert views <= allowed, f"vistas en el esquema fuera de la whitelist: {views - allowed}"

    for table, columns in ALLOWED_TABLES.items():
        if table in views:
            continue
        block = re.search(rf"CREATE TABLE(?: IF NOT EXISTS)?\s+{table}\s*\((.*?)\n\)", text, re.I | re.S)
        assert block, f"{table} no aparece en schema.sql"
        cols = set(re.findall(r"^\s{2}(\w+)\s+\w", block.group(1), re.M))
        assert cols <= columns, f"columnas de {table} fuera de la whitelist: {cols - columns}"


def test_internal_tables_are_never_allowed() -> None:
    # La herramienta SQL lee el dominio, nunca la trazabilidad ni el repositorio documental.
    for table in FORBIDDEN_TABLES:
        assert table not in ALLOWED_TABLES


def test_prestamos_estado_is_a_view_not_a_stored_state() -> None:
    # D7 / R-3.12: el estado se resuelve por cálculo. La vista existe en la whitelist
    # porque es la única forma de que el agente consulte el vencimiento.
    assert "prestamos_estado" in ALLOWED_TABLES
    assert "dias_atraso" in ALLOWED_TABLES["prestamos_estado"]


def test_function_allowlist_excludes_side_effect_functions() -> None:
    # R-3.13: el timeout limita el tiempo, no los efectos. Una función de efecto no
    # puede resolverse con "el timeout la corta".
    for fn in ("pg_sleep", "pg_read_file", "dblink", "pg_advisory_lock", "lo_import", "system"):
        assert fn not in ALLOWED_FUNCTIONS
    for fn in ("count", "max", "round", "coalesce", "current_date", "extract"):
        assert fn in ALLOWED_FUNCTIONS
