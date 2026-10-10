"""Tests offline de `execute_sql` (T4.3, T4.4).

Corren sin base de datos ni credenciales (Art. 6): la conexión se inyecta como un
fake. Los casos que sí requieren base están en `tests/test_sql_tool.py`, marcados
`integration`.
"""
from __future__ import annotations

import pytest

from agent.config import load_config
from agent.errors import COLUMN_NOT_ALLOWED, EXECUTION_ERROR, SQL_NOT_READONLY, TIMEOUT
from agent.tools.sql_tool import SqlExecutor, connection_user


class TimeoutError_(Exception):
    pgcode = "25000"


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.fetched_limit = None

    @property
    def description(self):
        return [(col,) for col in self.conn.columns]

    def execute(self, sql):
        if self.conn.exc is not None:
            raise self.conn.exc
        self.conn.executed.append(sql)

    def fetchmany(self, n):
        self.fetched_limit = n
        return self.conn.rows[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, rows=None, columns=None, exc=None):
        self.rows = rows if rows is not None else [(1,), (2,)]
        self.columns = columns if columns is not None else ["id"]
        self.exc = exc
        self.executed: list[str] = []

    def cursor(self):
        return FakeCursor(self)


def test_clamp_de_filas_lo_aplica_la_ejecucion() -> None:
    # R-3.6 / D24: `LIMIT 100000` es un SELECT válido; el límite lo pone la ejecución.
    rows = [(i,) for i in range(60)]
    conn = FakeConn(rows=rows)
    out = SqlExecutor(load_config(), conn).execute_sql("SELECT id FROM socios LIMIT 100000")

    assert out.executed is True
    assert len(out.rows) == load_config().max_rows
    assert conn.executed and "LIMIT 100000" in conn.executed[0]


def test_timeout_devuelve_error_tipado() -> None:
    out = SqlExecutor(load_config(), FakeConn(exc=TimeoutError_())).execute_sql("SELECT id FROM libros")
    assert out.executed is False
    assert out.error == TIMEOUT


def test_fallo_de_ejecucion_no_se_reinterpreta() -> None:
    # R-3.16: se reporta el fallo, no se infiere ni se completa con datos externos.
    out = SqlExecutor(load_config(), FakeConn(exc=Exception("relation does not exist"))).execute_sql(
        "SELECT id FROM socios"
    )
    assert out.executed is False
    assert out.error == EXECUTION_ERROR


def test_sentencia_rechazada_nunca_llega_a_la_conexion() -> None:
    conn = FakeConn()
    out = SqlExecutor(load_config(), conn).execute_sql("SELECT secreto FROM socios")
    assert out.executed is False
    assert out.error == COLUMN_NOT_ALLOWED
    assert conn.executed == [], "la validación debe fallar antes de tocar la base"


def test_lo_que_se_ejecuta_es_la_sentencia_normalizada() -> None:
    conn = FakeConn(columns=["id", "nombre", "email"], rows=[(1, "Ana", "ana@mail.com")])
    out = SqlExecutor(load_config(), conn).execute_sql("SELECT * FROM socios")
    assert conn.executed == [out.sql]
    assert "*" not in out.sql
    assert out.sql_original == "SELECT * FROM socios"


def test_result_vacio_se_reporta_sin_inferir() -> None:
    # R-3.8
    out = SqlExecutor(load_config(), FakeConn(rows=[])).execute_sql(
        "SELECT id FROM socios WHERE legajo = 'INEXISTENTE'"
    )
    assert out.executed is True
    assert out.rows == []


def test_regeneracion_hasta_dos_intentos() -> None:
    # D8 / R-3.10
    conn = FakeConn()
    out = SqlExecutor(load_config(), conn).run_with_regeneration(
        ["DELETE FROM prestamos", "SELECT id FROM prestamos"]
    )
    assert out.executed is True
    assert out.attempts == 2
    assert len(conn.executed) == 1, "el primer intento rechazado no se ejecuta"


def test_dos_rechazos_no_ejecutan_nada() -> None:
    conn = FakeConn()
    out = SqlExecutor(load_config(), conn).run_with_regeneration(
        ["DELETE FROM prestamos", "DROP TABLE libros"]
    )
    assert out.executed is False
    assert out.attempts == 2
    assert out.error == SQL_NOT_READONLY
    assert conn.executed == []


def test_el_generador_se_llama_exactamente_el_maximo_de_intentos() -> None:
    calls = []

    def gen():
        calls.append(1)
        return "DELETE FROM prestamos"

    SqlExecutor(load_config(), FakeConn()).run_with_regeneration(gen)
    assert len(calls) == load_config().max_sql_attempts


def test_la_conexion_usa_el_role_agent_ro() -> None:
    # R-3.5 / D14
    assert connection_user() == "agent_ro"


def test_no_hay_claves_hardcodeadas_en_el_executor() -> None:
    # Art. 9: leer el nombre de la variable de entorno no es hardcodear una clave.
    import pathlib
    import re

    src = pathlib.Path("agent/tools/sql_tool.py").read_text(encoding="utf-8")
    assert re.search(r"password\s*=\s*[\"'][^\"']+[\"']", src) is None
