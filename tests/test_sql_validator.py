"""Casos adversos de sanitización de SQL (T4.2, R-3.2, R-3.3, R-3.4, R-3.7).

Corren **sin base de datos y sin credenciales de API** (D1): la validación es estática.
El criterio de éxito es rechazo sin ejecución contra la base.
"""
from __future__ import annotations

import pytest

from agent.errors import SQL_NOT_READONLY, TABLE_NOT_ALLOWED
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
    ("S10", "SELECT * FROM agent_runs", TABLE_NOT_ALLOWED),
    ("S11", "SELECT * FROM documentos_embeddings", TABLE_NOT_ALLOWED),
    ("S12", "SELECT secreto FROM socios", TABLE_NOT_ALLOWED),
]


@pytest.mark.parametrize("case_id, sql, expected", ADVERSARIAL)
def test_adversarial_rejected(case_id: str, sql: str, expected: str) -> None:
    result = validate_sql(sql)
    assert not result.ok, f"{case_id} debería rechazarse"
    assert result.error == expected, f"{case_id}: esperaba {expected}, obtuvo {result.error}"
    assert result.detail, f"{case_id}: el rechazo debe tener motivo reportable (R-5.7)"


def test_s10_limit_is_applied_by_executor_not_by_validator() -> None:
    # S10 es un SELECT válido: el límite de 50 filas lo aplica la ejecución (T4.3),
    # no la validación estática.
    result = validate_sql("SELECT * FROM libros LIMIT 100000")
    assert result.ok
    assert result.tables == ("libros",)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id, titulo FROM libros WHERE ejemplares_disponibles > 0",
        "SELECT s.nombre, p.id FROM prestamos p JOIN socios s ON s.id = p.socio_id",
        "WITH top AS (SELECT libro_id, count(*) AS c FROM prestamos GROUP BY libro_id) SELECT * FROM top",
        "SELECT estado, dias_atraso FROM prestamos_estado WHERE estado = 'vencido'",
        "SELECT a.nombre, count(l.id) AS libros FROM autores a JOIN libros l ON l.autor_id = a.id GROUP BY a.nombre",
    ],
)
def test_valid_queries_pass(sql: str) -> None:
    result = validate_sql(sql)
    assert result.ok, f"no debería rechazarse: {result.error} ({result.detail})"
