"""Herramienta `execute_sql` (T4.3, T4.4, R-3.5, R-3.6, R-3.10, R-3.16).

`psycopg2` se importa de forma diferida: la validación, el clamp de filas y la
política de regeneración deben poder probarse sin base de datos ni credenciales
(Art. 6). La conexión se puede inyectar, así que el mismo executor corre con un
fake en los tests offline y con `agent_ro` en los de integración.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Iterable

from agent.config import Config, load_config
from agent.contracts import SqlResult
from agent.errors import EXECUTION_ERROR, TIMEOUT
from agent.sql_validator import validate_sql

SQLSTATE_TIMEOUT = "25000"  # inactive_sql_statement


def connection_user(config: Config | None = None) -> str:
    """R-3.5: el rol de solo lectura, no el rol de desarrollo (D14)."""
    return (config or load_config()).db_user


def _is_timeout(exc: Exception) -> bool:
    """Se resuelve por SQLSTATE, no por la clase de `psycopg2`, para no depender del paquete."""
    return getattr(exc, "pgcode", None) == SQLSTATE_TIMEOUT or type(exc).__name__ == "QueryCanceled"


class SqlExecutor:
    def __init__(self, config: Config | None = None, conn=None) -> None:
        self.cfg = config or load_config()
        self.conn = conn

    def _connect(self):
        import psycopg2  # diferido: los tests offline no requieren el paquete

        conn = psycopg2.connect(
            dbname=self.cfg.db_name,
            user=self.cfg.db_user,
            host=self.cfg.db_host,
            port=self.cfg.db_port,
            password=os.environ.get("POSTGRES_PASSWORD"),  # Art. 9: nunca un literal en el repo
        )
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (self.cfg.statement_timeout_ms,))
            cur.execute("SET search_path = public")  # D14
        return conn

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
        check = validate_sql(sql, cfg)
        if not check.ok:
            return SqlResult(
                sql=None,
                rows=[],
                error=check.error,
                executed=False,
                attempts=attempts,
                latency_ms=0,
                sql_original=sql_original or sql,
            )

        started = time.perf_counter()
        conn = self.conn if self.conn is not None else self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(check.normalized_sql)
                columns = [d[0] for d in cur.description]
                rows = [dict(zip(columns, row)) for row in cur.fetchmany(cfg.max_rows)]
        except Exception as exc:  # R-3.16: el error se reporta, no se interpreta
            return SqlResult(
                sql=check.normalized_sql,
                rows=[],
                error=TIMEOUT if _is_timeout(exc) else EXECUTION_ERROR,
                executed=False,
                attempts=attempts,
                latency_ms=int((time.perf_counter() - started) * 1000),
                sql_original=sql_original or sql,
            )

        return SqlResult(
            sql=check.normalized_sql,
            rows=rows,
            error=None,
            executed=True,
            attempts=attempts,
            latency_ms=int((time.perf_counter() - started) * 1000),
            sql_original=sql_original or sql,
        )

    def run_with_regeneration(self, candidates: Iterable[str] | Callable[[], str]) -> SqlResult:
        """R-3.10 (D8): máximo `cfg.max_sql_attempts` intentos; nada se ejecuta si se rechaza.

        `candidates` puede ser una lista de sentencias (tests) o una callable que
        invoca el modelo en cada intento (producción).
        """
        gen: Callable[[], str]
        if callable(candidates):
            gen = candidates
        else:
            seq = list(candidates)
            gen = lambda: seq.pop(0)  # noqa: E731

        last_error: str | None = None
        for attempt in range(1, self.cfg.max_sql_attempts + 1):
            sql = gen()
            result = self.execute_sql(sql, attempts=attempt)
            if result.executed:
                return result
            last_error = result.error
        # Dos rechazos: no se ejecutó nada y el error se reporta al usuario (R-5.7).
        return SqlResult(
            sql=None,
            rows=[],
            error=last_error,
            executed=False,
            attempts=self.cfg.max_sql_attempts,
            latency_ms=0,
            sql_original=None,
        )


_DEFAULT = SqlExecutor()

execute_sql = _DEFAULT.execute_sql
run_with_regeneration = _DEFAULT.run_with_regeneration
