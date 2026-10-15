"""Tests offline de `execute_sql` (T4.3, T4.4).

Corren sin base de datos ni credenciales (Art. 6): la conexión se inyecta como un
fake. Los casos que sí requieren base están en `tests/test_sql_tool.py`, marcados
`integration`.
"""
from __future__ import annotations

import pathlib
import re

from agent.config import load_config
from agent.errors import COLUMN_NOT_ALLOWED, EXECUTION_ERROR, SQL_NOT_READONLY, TIMEOUT
from agent.tools.sql_tool import SqlExecutor, connection_options, connection_user


class QueryCanceled(Exception):
    """`statement_timeout` en Postgres: SQLSTATE 57014 (query_canceled)."""

    pgcode = "57014"


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.fetched_limit = None

    @property
    def description(self):
        return [(col,) for col in self.conn.columns]

    def execute(self, sql):
        if self.conn.exc is not None and not sql.startswith("SET LOCAL"):
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
        self.rollbacks = 0
        self.closed = 0

    def cursor(self):
        return FakeCursor(self)

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1


def _executor(conn=None, **overrides) -> SqlExecutor:
    return SqlExecutor(load_config(), conn if conn is not None else FakeConn(**overrides))


def test_clamp_de_filas_lo_aplica_la_ejecucion() -> None:
    # R-3.6 / D24: `LIMIT 100000` es un SELECT válido; el límite lo pone la ejecución.
    rows = [(i,) for i in range(60)]
    conn = FakeConn(rows=rows)
    out = SqlExecutor(load_config(), conn).execute_sql("SELECT id FROM socios LIMIT 100000")

    assert out.executed is True
    assert len(out.rows) == load_config().max_rows
    assert conn.executed and "LIMIT 100000" in conn.executed[0]


def test_resultado_truncado_se_declara() -> None:
    # D48 / Art. 4: 50 filas presentadas como el total son una afirmación falsa.
    limit = load_config().max_rows
    out = _executor(rows=[(i,) for i in range(limit + 1)]).execute_sql("SELECT id FROM socios")
    assert out.truncated is True
    assert len(out.rows) == limit


def test_resultado_exacto_en_el_limite_no_es_truncado() -> None:
    limit = load_config().max_rows
    out = _executor(rows=[(i,) for i in range(limit)]).execute_sql("SELECT id FROM socios")
    assert out.truncated is False
    assert len(out.rows) == limit


def test_columnas_repetidas_no_pisan_datos() -> None:
    # `dict(zip(columns, row))` descartaba el primer valor de una columna repetida (D44).
    conn = FakeConn(columns=["id", "id", "nombre"], rows=[(1, 2, "Ana")])
    out = _executor(conn).execute_sql("SELECT l.id, a.id, a.nombre FROM libros l, autores a")
    assert out.rows == [{"id": 1, "id_2": 2, "nombre": "Ana"}]


def test_timeout_devuelve_error_tipado() -> None:
    out = _executor(exc=QueryCanceled()).execute_sql("SELECT id FROM libros")
    assert out.executed is False
    assert out.error == TIMEOUT


def test_timeout_se_reconoce_por_sqlstate_57014() -> None:
    # `25000` (el valor anterior) es `invalid_transaction_state`, no el de `statement_timeout`.
    class Other(Exception):
        pgcode = "25000"

    assert _executor(exc=Other()).execute_sql("SELECT id FROM libros").error == EXECUTION_ERROR


def test_fallo_de_ejecucion_no_se_reinterpreta() -> None:
    # R-3.16: se reporta el fallo, no se infiere ni se completa con datos externos.
    out = _executor(exc=Exception("relation does not exist")).execute_sql("SELECT id FROM socios")
    assert out.executed is False
    assert out.error == EXECUTION_ERROR
    assert out.rows == []


def test_sentencia_rechazada_nunca_llega_a_la_conexion() -> None:
    conn = FakeConn()
    out = SqlExecutor(load_config(), conn).execute_sql("SELECT secreto FROM socios")
    assert out.executed is False
    assert out.error == COLUMN_NOT_ALLOWED
    assert out.detail, "R-5.7: el rechazo debe llevar el motivo"
    assert conn.executed == [], "la validación debe fallar antes de tocar la base"
    assert conn.rollbacks == 0


def test_lo_que_se_ejecuta_es_la_sentencia_normalizada() -> None:
    conn = FakeConn(columns=["id", "nombre", "email"], rows=[(1, "Ana", "ana@mail.com")])
    out = SqlExecutor(load_config(), conn).execute_sql("SELECT * FROM socios")
    assert conn.executed == [out.sql]
    assert "*" not in out.sql
    assert out.sql_original == "SELECT * FROM socios"


def test_result_vacio_se_reporta_sin_inferir() -> None:
    # R-3.8
    out = _executor(rows=[]).execute_sql("SELECT id FROM socios WHERE legajo = 'INEXISTENTE'")
    assert out.executed is True
    assert out.rows == []


def test_rollback_despues_de_cada_ejecucion() -> None:
    # D45: sin rollback, tras un error la transacción queda abortada para la siguiente consulta.
    ok_conn = FakeConn()
    _executor(ok_conn).execute_sql("SELECT id FROM socios")
    assert ok_conn.rollbacks == 1

    err_conn = FakeConn(exc=Exception("boom"))
    _executor(err_conn).execute_sql("SELECT id FROM socios")
    assert err_conn.rollbacks == 1


def test_timeout_ms_se_aplica_antes_de_la_consulta() -> None:
    # D46: el parámetro dejó de ser ignorado.
    conn = FakeConn()
    SqlExecutor(load_config(), conn).execute_sql("SELECT id FROM socios", timeout_ms=1)
    assert conn.executed[0] == "SET LOCAL statement_timeout = 1"
    assert conn.executed[1].startswith("SELECT")


def test_sin_timeout_ms_no_se_emite_set() -> None:
    conn = FakeConn()
    SqlExecutor(load_config(), conn).execute_sql("SELECT id FROM socios")
    assert not any(s.startswith("SET") for s in conn.executed)


def test_conexion_inyectada_no_se_cierra() -> None:
    conn = FakeConn()
    executor = SqlExecutor(load_config(), conn)
    executor.execute_sql("SELECT id FROM socios")
    executor.close()
    assert conn.closed == 0, "la conexión es de quien la inyectó"


def test_la_conexion_propia_se_cierra_y_se_reabre() -> None:
    created: list[FakeConn] = []

    class Owned(SqlExecutor):
        def _connect(self):
            conn = FakeConn()
            created.append(conn)
            return conn

    executor = Owned(load_config())
    executor.execute_sql("SELECT id FROM socios")
    executor.execute_sql("SELECT id FROM libros")
    assert len(created) == 1, "una conexión por executor, no una por consulta (D45)"

    executor.close()
    assert created[0].closed == 1
    executor.execute_sql("SELECT id FROM socios")
    assert len(created) == 2


def test_las_opciones_de_sesion_fijan_timeout_search_path_y_zona_horaria() -> None:
    # D14 / D47: `CURRENT_DATE` no puede depender de la zona del servidor (servidor o contenedor
    # en UTC, R-3.11).
    cfg = load_config()
    options = connection_options(cfg)
    assert f"statement_timeout={cfg.statement_timeout_ms}" in options
    assert "search_path=public" in options
    assert f"timezone={cfg.timezone}" in options
    assert cfg.timezone == "America/Argentina/Buenos_Aires"


# --- regeneración (R-3.10, D8, D49) ---


def test_regeneracion_hasta_dos_intentos() -> None:
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


def test_el_rechazo_final_conserva_motivo_y_sentencia_original() -> None:
    # R-5.7 / R-6.4: el usuario ve el motivo y la traza conserva lo que generó el modelo.
    out = _executor().run_with_regeneration(["DELETE FROM prestamos", "DROP TABLE libros"])
    assert out.detail
    assert out.sql_original == "DROP TABLE libros"


def test_el_generador_se_llama_exactamente_el_maximo_de_intentos() -> None:
    calls = []

    def gen():
        calls.append(1)
        return "DELETE FROM prestamos"

    _executor().run_with_regeneration(gen)
    assert len(calls) == load_config().max_sql_attempts


def test_el_generador_recibe_el_resultado_anterior() -> None:
    # D49: regenerar a ciegas repite el mismo SQL; el modelo necesita el motivo.
    seen: list = []

    def gen(previous):
        seen.append(previous)
        return "SELECT secreto FROM socios" if previous is None else "SELECT id FROM socios"

    out = _executor().run_with_regeneration(gen)
    assert out.executed is True
    assert seen[0] is None
    assert seen[1].error == COLUMN_NOT_ALLOWED
    assert seen[1].detail


def test_lista_de_candidatas_agotada_no_lanza() -> None:
    out = _executor().run_with_regeneration(["DELETE FROM prestamos"])
    assert out.executed is False
    assert out.attempts == 1

    empty = _executor().run_with_regeneration([])
    assert empty.executed is False
    assert empty.error == SQL_NOT_READONLY


def test_la_conexion_usa_el_role_agent_ro() -> None:
    # R-3.5 / D14
    assert connection_user() == "agent_ro"


def test_no_hay_claves_hardcodeadas_en_el_executor() -> None:
    # Art. 9: leer el nombre de la variable de entorno no es hardcodear una clave.
    src = pathlib.Path("agent/tools/sql_tool.py").read_text(encoding="utf-8")
    assert re.search(r"password\s*=\s*[\"'][^\"']+[\"']", src) is None


def test_importar_el_modulo_no_abre_conexiones_ni_lee_config() -> None:
    # D45: el executor por defecto es perezoso.
    import agent.tools.sql_tool as sql_tool

    assert sql_tool._default is None or isinstance(sql_tool._default, SqlExecutor)
