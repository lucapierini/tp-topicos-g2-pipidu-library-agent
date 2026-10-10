"""Casos adversos de sanitización de SQL (T4.2, R-3.2, R-3.3, R-3.4, R-3.7, R-3.13).

Corren **sin base de datos y sin credenciales de API** (D1): la validación es estática.
El criterio de éxito es rechazo sin ejecución contra la base.
"""
from __future__ import annotations

import pytest
from sqlglot import parse_one

from agent.errors import (
    COLUMN_NOT_ALLOWED,
    FUNCTION_NOT_ALLOWED,
    SQL_NOT_READONLY,
    TABLE_NOT_ALLOWED,
)
from agent.sql_validator import validate_sql

ADVERSARIAL = [
    ("S1", "DELETE FROM prestamos WHERE socio_id = 1", SQL_NOT_READONLY),
    ("S2", "SELECT 1; DROP TABLE libros", SQL_NOT_READONLY),
    ("S3", "SELECT * FROM pg_catalog.pg_tables", TABLE_NOT_ALLOWED),
    ("S4", "SELECT * FROM libros -- comentario", SQL_NOT_READONLY),
    ("S5", "WITH x AS (SELECT 1) INSERT INTO autores VALUES (1,'a','b','c',NULL)", SQL_NOT_READONLY),
    ("S6", "COPY libros TO '/etc/passwd'", SQL_NOT_READONLY),
    ("S7", "SELECT * FROM libros /* bloque */ ; CREATE TABLE t (a int)", SQL_NOT_READONLY),
    ("S8", "SELECT * FROM usuarios_vistos", TABLE_NOT_ALLOWED),
    ("S9", "CALL some_procedure()", SQL_NOT_READONLY),
    # S10–S12 son casos de ejecución/regeneración en `TP/05-validacion.md` (tests de executor).
    # IDs alineados con esa tabla; antes S10–S12 repetían S13–S15 y contaban doble.
    ("S13", "SELECT * FROM agent_runs", TABLE_NOT_ALLOWED),
    ("S14", "SELECT * FROM documentos_embeddings", TABLE_NOT_ALLOWED),
    ("S15", "SELECT secreto FROM socios", COLUMN_NOT_ALLOWED),
    # Fix 2 (R-3.13): funciones de efecto, no de cálculo sobre el dominio.
    ("S16", "SELECT id, pg_sleep(10) FROM libros", FUNCTION_NOT_ALLOWED),
    ("S17", "SELECT pg_read_file('/etc/passwd') FROM libros", FUNCTION_NOT_ALLOWED),
    ("S18", "SELECT dblink('dbname=x', 'SELECT 1') AS r FROM libros", FUNCTION_NOT_ALLOWED),
    ("S16b", "SELECT pg_advisory_lock(1) FROM libros", FUNCTION_NOT_ALLOWED),
    # Fix 3 (R-3.2): lock de fila no es lectura.
    ("S19", "SELECT id FROM libros FOR UPDATE", SQL_NOT_READONLY),
    # Fix 5: parse estricto, sin degradación a Command.
    ("S20", "SELECT FROM WHERE", SQL_NOT_READONLY),
]


@pytest.mark.parametrize("case_id, sql, expected", ADVERSARIAL)
def test_adversarial_rejected(case_id: str, sql: str, expected: str) -> None:
    result = validate_sql(sql)
    assert not result.ok, f"{case_id} debería rechazarse"
    assert result.error == expected, f"{case_id}: esperaba {expected}, obtuvo {result.error}"
    assert result.detail, f"{case_id}: el rechazo debe tener motivo reportable (R-5.7)"
    assert result.normalized_sql is None, f"{case_id}: un rechazo no produce sentencia ejecutable"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id, titulo FROM libros WHERE ejemplares_disponibles > 0",
        "SELECT s.nombre, p.id FROM prestamos p JOIN socios s ON s.id = p.socio_id",
        "WITH top AS (SELECT libro_id, count(*) AS c FROM prestamos GROUP BY libro_id) SELECT * FROM top",
        "SELECT estado, dias_atraso FROM prestamos_estado WHERE estado = 'vencido'",
        "SELECT a.nombre, count(l.id) AS libros FROM autores a JOIN libros l ON l.autor_id = a.id GROUP BY a.nombre",
        "SELECT id FROM libros UNION SELECT id FROM socios",
        "SELECT count(*) AS c, max(fecha_prestamo) FROM prestamos",
    ],
)
def test_valid_queries_pass(sql: str) -> None:
    result = validate_sql(sql)
    assert result.ok, f"no debería rechazarse: {result.error} ({result.detail})"


# --- Fix 1: la whitelist de columnas deja de ser evadible por `SELECT *` (R-3.4) ---

def test_star_expands_to_whitelisted_columns() -> None:
    result = validate_sql("SELECT * FROM socios")
    assert result.ok
    assert result.normalized_sql is not None
    projected = {e.alias_or_name for e in parse_one(result.normalized_sql, read="postgres").expressions}
    assert projected == {"id", "nombre", "apellido", "legajo", "tipo_socio", "email", "fecha_alta"}


def test_star_expansion_blocks_columns_that_exist_in_schema_but_not_in_whitelist() -> None:
    # Si el esquema físico tiene una columna fuera de la whitelist, `SELECT *` no puede
    # alcanzarla: la sentencia ejecutada es la expandida, no la original.
    result = validate_sql("SELECT * FROM socios")
    assert result.ok
    assert "secreto" not in result.normalized_sql
    assert "*" not in result.normalized_sql


def test_qualified_star_expands_only_its_own_table() -> None:
    result = validate_sql("SELECT s.* FROM socios s JOIN prestamos p ON p.socio_id = s.id")
    assert result.ok
    assert "prestamos." not in result.normalized_sql


# --- Fix 4: identificadores normalizados (case-sensitive false rejection) ---

def test_quoted_identifier_is_not_falsely_rejected() -> None:
    result = validate_sql('SELECT id FROM "Libros"')
    assert result.ok, result.detail
    assert result.tables == ("libros",)
    assert "libros" in result.normalized_sql.lower()


def test_string_literals_are_not_altered_by_normalization() -> None:
    # Normalizar identificadores no puede tocar valores: la respuesta final debe citar
    # los valores efectivamente devueltos (R-3.9, Art. 4).
    result = validate_sql("SELECT titulo FROM libros WHERE titulo = 'Cien años de soledad'")
    assert result.ok
    assert "Cien años de soledad" in result.normalized_sql


def test_original_sql_is_preserved_and_normalized_sql_is_the_executable_one() -> None:
    result = validate_sql("SELECT * FROM socios")
    assert result.sql == "SELECT * FROM socios"
    assert result.normalized_sql != result.sql
    # R-3.9: la interfaz muestra la sentencia efectivamente ejecutada.
    assert result.normalized_sql.startswith("SELECT socios.")
