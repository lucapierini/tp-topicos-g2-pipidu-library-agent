"""Herramienta `execute_sql` (T4.3, T4.4, R-3.5, R-3.6, R-3.10, R-3.16).

`psycopg2` se importa de forma diferida: la validación, el clamp de filas y la
política de regeneración deben poder probarse sin base de datos ni credenciales
(Art. 6). La conexión se puede inyectar, así que el mismo executor corre con un
fake en los tests offline y con `agent_ro` en los de integración.

Conexión (D45): una conexión por executor, creada de forma perezosa, de **solo lectura**,
con `statement_timeout`, `search_path` y zona horaria fijados al conectar. Se hace
`rollback()` después de cada ejecución para no dejar transacciones abiertas ni abortadas.
"""
from __future__ import annotations

import inspect
import os
import time
from collections.abc import Callable, Iterable

from agent.config import Config, load_config
from agent.contracts import SqlResult
from agent.errors import EXECUTION_ERROR, SQL_NOT_READONLY, TIMEOUT
from agent.sql_validator import validate_sql

# `statement_timeout` cancela la consulta con `QueryCanceled`, SQLSTATE 57014 (query_canceled).
SQLSTATE_QUERY_CANCELED = "57014"


def connection_user(config: Config | None = None) -> str:
    """R-3.5: el rol de solo lectura, no el rol de desarrollo (D14)."""
    return (config or load_config()).db_user


def connection_options(config: Config) -> str:
    """Parámetros de sesión fijados al conectar (D14, D47).

    La zona horaria es la configurada y no la del servidor: `CURRENT_DATE` en Cloud SQL
    (UTC) cambia de día a las 21:00 en Buenos Aires y "vencido" dejaría de ser reproducible.
    """
    return (
        f"-c statement_timeout={int(config.statement_timeout_ms)} "
        f"-c search_path=public "
        f"-c timezone={config.timezone}"
    )


def _is_timeout(exc: Exception) -> bool:
    """Se resuelve por SQLSTATE, no por la clase de `psycopg2`, para no depender del paquete."""
    return getattr(exc, "pgcode", None) == SQLSTATE_QUERY_CANCELED or type(exc).__name__ == "QueryCanceled"


def _unique_names(names: list[str]) -> list[str]:
    """`dict(zip(columns, row))` pisa las columnas repetidas: se desambiguan con `_2`, `_3`."""
    seen: dict[str, int] = {}
    unique: list[str] = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        unique.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return unique


class SqlExecutor:
    def __init__(self, config: Config | None = None, conn=None) -> None:
        self.cfg = config or load_config()
        self._conn = conn
        self._owns_conn = conn is None

    # ------------------------------------------------------------------ conexión

    def _connect(self):
        import psycopg2  # diferido: los tests offline no requieren el paquete

        conn = psycopg2.connect(
            dbname=self.cfg.db_name,
            user=self.cfg.db_user,
            host=self.cfg.db_host,
            port=self.cfg.db_port,
            password=os.environ.get("POSTGRES_PASSWORD"),  # Art. 9: nunca un literal en el repo
            options=connection_options(self.cfg),
            sslmode=self.cfg.db_sslmode or None,
            connect_timeout=self.cfg.api_timeout_s,
        )
        conn.set_session(readonly=True)  # defensa en profundidad además del rol (Art. 3)
        return conn

    def _connection(self):
        if self._conn is None or getattr(self._conn, "closed", 0):
            self._conn = self._connect()
            self._owns_conn = True
        return self._conn

    def close(self) -> None:
        """Cierra la conexión propia. Una conexión inyectada es de quien la inyectó."""
        if self._conn is not None and self._owns_conn:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def __enter__(self) -> SqlExecutor:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ ejecución

    def execute_sql(
        self,
        sql: str,
        *,
        timeout_ms: int | None = None,
        attempts: int = 1,
        sql_original: str | None = None,
    ) -> SqlResult:
        """Valida y ejecuta. No genera SQL: esa es la parte del agente (D1)."""
        cfg = self.cfg
        original = sql_original or sql
        check = validate_sql(sql, cfg)
        if not check.ok:
            return SqlResult(
                sql=None,
                rows=[],
                error=check.error,
                executed=False,
                attempts=attempts,
                latency_ms=0,
                sql_original=original,
                detail=check.detail,
            )

        started = time.perf_counter()

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started) * 1000)

        conn = None
        try:
            conn = self._connection()
            with conn.cursor() as cur:
                if timeout_ms is not None:
                    # Sobrescritura puntual (D46): `LOCAL` vale solo para esta transacción.
                    cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                cur.execute(check.normalized_sql)
                names = _unique_names([d[0] for d in cur.description])
                # Una fila de más permite saber si el resultado se truncó (D48, Art. 4).
                fetched = cur.fetchmany(cfg.max_rows + 1)
            rows = [dict(zip(names, row, strict=True)) for row in fetched[: cfg.max_rows]]
            return SqlResult(
                sql=check.normalized_sql,
                rows=rows,
                error=None,
                executed=True,
                attempts=attempts,
                latency_ms=elapsed_ms(),
                sql_original=original,
                truncated=len(fetched) > cfg.max_rows,
            )
        except Exception as exc:  # R-3.16: el error se reporta, no se interpreta
            return SqlResult(
                sql=check.normalized_sql,
                rows=[],
                error=TIMEOUT if _is_timeout(exc) else EXECUTION_ERROR,
                executed=False,
                attempts=attempts,
                latency_ms=elapsed_ms(),
                sql_original=original,
                detail=f"{type(exc).__name__}: {exc}"[:300],
            )
        finally:
            # Sin esto, tras un error la transacción queda abortada y la siguiente consulta
            # falla con "current transaction is aborted" (D45).
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001 - la conexión puede estar ya caída
                    pass

    def run_with_regeneration(self, candidates: Iterable[str] | Callable[..., str]) -> SqlResult:
        """R-3.10 (D8): máximo `cfg.max_sql_attempts` intentos; nada se ejecuta si se rechaza.

        `candidates` puede ser una lista de sentencias (tests) o una callable que invoca al
        modelo en cada intento (producción). Si la callable acepta un argumento, recibe el
        `SqlResult` del intento anterior (con `error` y `detail`) para no regenerar a ciegas
        (D49); una callable sin parámetros sigue siendo válida.
        """
        if callable(candidates):
            gen = candidates
            takes_feedback = bool(inspect.signature(gen).parameters)
        else:
            seq = list(candidates)

            def gen(_previous: SqlResult | None = None) -> str:
                return seq.pop(0)

            takes_feedback = True

        last: SqlResult | None = None
        for attempt in range(1, self.cfg.max_sql_attempts + 1):
            try:
                sql = gen(last) if takes_feedback else gen()
            except IndexError:  # la lista de candidatas se agotó antes del límite
                break
            result = self.execute_sql(sql, attempts=attempt)
            if result.executed:
                return result
            last = result

        if last is None:
            return SqlResult(
                sql=None,
                rows=[],
                error=SQL_NOT_READONLY,
                executed=False,
                attempts=0,
                latency_ms=0,
                detail="no se generó ninguna sentencia",
            )
        # Todos los intentos fallaron: no se ejecutó nada y el error se reporta (R-5.7). Se
        # conservan `sql_original` y `detail` del último intento para la trazabilidad (R-6.4);
        # `attempts` es el número del último intento, es decir, cuántos se hicieron.
        return last


# Executor por defecto: perezoso, para que importar el módulo no lea configuración ni
# abra conexiones (D45).
_default: SqlExecutor | None = None


def get_executor() -> SqlExecutor:
    global _default
    if _default is None:
        _default = SqlExecutor()
    return _default


def execute_sql(sql: str, **kwargs) -> SqlResult:
    return get_executor().execute_sql(sql, **kwargs)


def run_with_regeneration(candidates: Iterable[str] | Callable[..., str]) -> SqlResult:
    return get_executor().run_with_regeneration(candidates)
