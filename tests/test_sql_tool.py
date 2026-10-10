"""Herramienta `execute_sql` (T4.3, T4.4, R-3.5, R-3.6, R-3.10).

Estas pruebas requieren base de datos y el executor todavía no existe, así que se
saltan. Se escribieron ahora para que el requisito quede verifiable y no se
confunda con lo que la validación estática sí puede afirmar hoy.
"""
from __future__ import annotations

import pytest

from agent.contracts import SqlResult
from agent.errors import TIMEOUT
from agent.sql_validator import validate_sql

pytestmark = pytest.mark.integration


def test_clamp_de_filas_lo_aplica_la_ejecucion() -> None:
    # R-3.6: S10 es un SELECT válido; el límite de 50 filas lo aplica la ejecución.
    result = validate_sql("SELECT * FROM libros LIMIT 100000")
    assert result.ok

    sql_tool = pytest.importorskip("agent.tools.sql_tool", reason="T4.3 todavía no implementado")
    out = sql_tool.execute_sql(result.normalized_sql)
    assert isinstance(out, SqlResult)
    assert len(out.rows) <= 50, "la herramienta debe devolver como máximo 50 filas"
    assert out.executed is True


def test_timeout_devuelve_error_tipado() -> None:
    sql_tool = pytest.importorskip("agent.tools.sql_tool", reason="T4.3 todavía no implementado")
    # `pg_sleep` está bloqueado por R-3.13, así que el timeout se prueba con una
    # consulta legítima y un timeout reducido: el camino verificado es la cancelación
    # de la conexión, no una función peligrosa.
    out = sql_tool.execute_sql("SELECT count(*) FROM prestamos, libros, socios", timeout_ms=1)
    assert out.executed is False
    assert out.error == TIMEOUT


def test_ejecucion_usa_el_role_agent_ro() -> None:
    # R-3.5: la conexión usa el rol de solo lectura, no el rol del desarrollo.
    sql_tool = pytest.importorskip("agent.tools.sql_tool", reason="T4.3 todavía no implementado")
    assert sql_tool.connection_user() == "agent_ro"


def test_result_vacio_se_reporta_sin_inferir() -> None:
    # R-3.8: 0 filas se reporta como "sin resultados", no se interpreta.
    sql_tool = pytest.importorskip("agent.tools.sql_tool", reason="T4.3 todavía no implementado")
    out = sql_tool.execute_sql("SELECT id FROM socios WHERE legajo = 'INEXISTENTE'")
    assert out.executed is True
    assert out.rows == []


def test_regeneracion_hasta_dos_intentos() -> None:
    # D8 / R-3.10: primer intento rechazado, segundo válido, ambos consignados.
    sql_tool = pytest.importorskip("agent.tools.sql_tool", reason="T4.4 todavía no implementado")
    out = sql_tool.run_with_regeneration(["DELETE FROM prestamos", "SELECT id FROM prestamos"])
    assert out.executed is True
    assert out.attempts == 2


def test_dos_rechazos_no_ejecutan_nada() -> None:
    sql_tool = pytest.importorskip("agent.tools.sql_tool", reason="T4.4 todavía no implementado")
    out = sql_tool.run_with_regeneration(["DELETE FROM prestamos", "DROP TABLE libros"])
    assert out.executed is False
    assert out.attempts == 2
    assert out.error is not None, "R-5.7: el error se reporta al usuario"
