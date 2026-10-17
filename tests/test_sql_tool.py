"""`execute_sql` contra una base real (T4.3, T4.4, R-3.5, R-3.6, R-3.10).

Marcado `integration`: requiere `docker compose up -d` y el rol `agent_ro`. La política de
clamp, regeneración y errores se prueba offline en `tests/test_sql_tool_offline.py`; acá solo
se verifica lo que únicamente la base puede afirmar: timeout real, rol y sesión de solo lectura.
"""
from __future__ import annotations

import pytest

from agent.config import load_config
from agent.contracts import SqlResult
from agent.errors import TIMEOUT
from agent.sql_validator import validate_sql
from agent.tools import sql_tool

pytestmark = pytest.mark.integration


@pytest.fixture()
def executor():
    pytest.importorskip("psycopg2")
    with sql_tool.SqlExecutor() as ex:
        try:
            ex._connection()
        except Exception as exc:  # noqa: BLE001 - sin base no hay nada que verificar
            pytest.skip(f"sin base de datos: {exc}")
        yield ex


def test_clamp_de_filas_lo_aplica_la_ejecucion(executor) -> None:
    # R-3.6: `LIMIT 100000` es un SELECT válido; el límite de 50 filas lo aplica la ejecución.
    result = validate_sql("SELECT * FROM libros LIMIT 100000")
    assert result.ok

    out = executor.execute_sql(result.normalized_sql)
    assert isinstance(out, SqlResult)
    assert out.executed is True
    assert len(out.rows) <= load_config().max_rows


def test_timeout_devuelve_error_tipado(executor) -> None:
    # `pg_sleep` está bloqueado por R-3.13, así que el timeout se prueba con una consulta
    # legítima y un timeout reducido: el camino verificado es la cancelación de la conexión.
    out = executor.execute_sql("SELECT count(*) FROM prestamos, libros, socios", timeout_ms=1)
    assert out.executed is False
    assert out.error == TIMEOUT


def test_la_conexion_siguiente_funciona_tras_un_error(executor) -> None:
    # D45: con rollback, la consulta siguiente funciona tras un error.
    executor.execute_sql("SELECT count(*) FROM prestamos, libros, socios", timeout_ms=1)
    out = executor.execute_sql("SELECT id FROM socios")
    assert out.executed is True


def test_ejecucion_usa_el_role_agent_ro(executor) -> None:
    # R-3.5: la conexión usa el rol de solo lectura, no el rol del desarrollo.
    assert sql_tool.connection_user() == "agent_ro"
    with executor._connection().cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0] == "agent_ro"
    executor._connection().rollback()


def test_la_sesion_es_de_solo_lectura_y_con_la_zona_configurada(executor) -> None:
    cfg = load_config()
    with executor._connection().cursor() as cur:
        cur.execute("SHOW transaction_read_only")
        assert cur.fetchone()[0] == "on"
        cur.execute("SHOW timezone")
        assert cur.fetchone()[0] == cfg.timezone
        cur.execute("SHOW statement_timeout")
        assert cur.fetchone()[0] in {f"{cfg.statement_timeout_ms // 1000}s", f"{cfg.statement_timeout_ms}ms"}
    executor._connection().rollback()


def test_result_vacio_se_reporta_sin_inferir(executor) -> None:
    # R-3.8: 0 filas se reporta como "sin resultados", no se interpreta.
    out = executor.execute_sql("SELECT id FROM socios WHERE legajo = 'INEXISTENTE'")
    assert out.executed is True
    assert out.rows == []


def test_regeneracion_hasta_dos_intentos(executor) -> None:
    # D8 / R-3.10: primer intento rechazado, segundo válido, ambos consignados.
    out = executor.run_with_regeneration(["DELETE FROM prestamos", "SELECT id FROM prestamos"])
    assert out.executed is True
    assert out.attempts == 2


def test_dos_rechazos_no_ejecutan_nada(executor) -> None:
    out = executor.run_with_regeneration(["DELETE FROM prestamos", "DROP TABLE libros"])
    assert out.executed is False
    assert out.attempts == 2
    assert out.error is not None, "R-5.7: el error se reporta al usuario"
    assert out.detail
