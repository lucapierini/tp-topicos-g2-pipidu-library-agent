"""Trazabilidad de ejecución: una fila de `agent_runs` por consulta (T7.4, T7.5; R-6.1 a R-6.5, Art. 5).

El registro se arma **solo desde el `AgentAnswer`**: no hay una segunda fuente de verdad que pueda
divergir de lo que se le mostró al usuario. Cada consulta se registra, resuelta o no (R-6.3): una
respuesta con `answer_kind` `error` o `no_coverage` también deja su fila, con el motivo.

Dos reglas de diseño:

1. **Registrar no puede romper la respuesta.** Si la base de trazabilidad no está disponible, la
   consulta igual se responde y el fallo queda declarado en la evidencia (`run_recording_error`): una
   respuesta correcta no se pierde por un problema de bitácora, pero tampoco se finge que se registró.
2. **Rol propio y de solo inserción.** Escribe `agent_logger`, no `agent_ro` (que es de solo lectura,
   R-3.5) ni el superusuario. La herramienta SQL no lee `agent_runs` (D21).
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from agent.config import Config, load_config
from agent.contracts import (
    ANSWER_KIND_ANSWER,
    ANSWER_KIND_ERROR,
    ANSWER_KIND_NO_COVERAGE,
    TRACE_CLASSIFICATION,
    AgentAnswer,
)

logger = logging.getLogger("agent.runs")

STATUS_BY_KIND = {
    ANSWER_KIND_ANSWER: "ok",
    ANSWER_KIND_NO_COVERAGE: "no_coverage",
    ANSWER_KIND_ERROR: "error",
}

INSERT_SQL = """
INSERT INTO agent_runs (
    question, classification, status, sources, tools, generated_sql, executed_sql, chunks, answer,
    latency_ms, attempts, error_code, error_detail, model_id, endpoint, trace
) VALUES (
    %s, %s, %s, %s::text[], %s::text[], %s, %s, %s::jsonb, %s,
    %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb
) RETURNING id
"""


@dataclass(frozen=True)
class RunRecord:
    question: str
    classification: str
    status: str                       # ok | no_coverage | error
    answer: str
    latency_ms: int
    model_id: str
    endpoint: str                     # local | api
    sources: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    generated_sql: str | None = None  # como lo generó el modelo (R-6.1)
    executed_sql: str | None = None   # normalizada, la que corrió (R-3.9)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)  # R-6.4
    error_code: str | None = None     # R-6.3
    error_detail: str | None = None
    trace: list[str] = field(default_factory=list)
    created_at: datetime | None = None  # lo fija la base (`DEFAULT now()`)

    def as_params(self) -> tuple:
        """Parámetros del INSERT. Los jsonb viajan como texto con cast: no se necesita `psycopg2.extras`."""
        dump = lambda value: json.dumps(value, ensure_ascii=False, default=str)  # noqa: E731
        return (
            self.question, self.classification, self.status, list(self.sources), list(self.tools),
            self.generated_sql, self.executed_sql, dump(self.chunks), self.answer,
            self.latency_ms, dump(self.attempts), self.error_code, self.error_detail,
            self.model_id, self.endpoint, dump(self.trace),
        )


def record_from_answer(answer: AgentAnswer, latency_ms: int) -> RunRecord:
    """Todo lo que se registra sale de la respuesta; nada se recalcula ni se infiere."""
    evidence = answer.evidence or {}
    model = evidence.get("model") or {}
    attempts = list(evidence.get("sql_attempts") or [])
    error = evidence.get("error") or {}

    # R-6.1 "sentencia generada": la del último intento, que es la que dio lugar al resultado
    # (o al rechazo final). Los intentos anteriores están en `attempts` (R-6.4).
    generated = evidence.get("sql_original") or (attempts[-1].get("sql_original") if attempts else None)

    return RunRecord(
        question=answer.question,
        classification=answer.classification,
        status=STATUS_BY_KIND.get(answer.answer_kind, "error"),
        sources=list(answer.sources),
        tools=[t for t in answer.trace if t != TRACE_CLASSIFICATION],
        generated_sql=generated,
        executed_sql=evidence.get("sql"),
        chunks=list(evidence.get("chunks") or []),
        answer=answer.answer,
        latency_ms=max(0, int(latency_ms)),
        attempts=attempts,
        error_code=error.get("code"),
        error_detail=error.get("detail"),
        model_id=str(model.get("id") or "desconocido"),
        endpoint=str(model.get("endpoint") or "api"),
        trace=list(answer.trace),
    )


class RunRecorder(Protocol):
    def record(self, record: RunRecord) -> int | None: ...


class InMemoryRunRecorder:
    """Para tests y mediciones sin base: conserva los registros en orden."""

    def __init__(self) -> None:
        self.records: list[RunRecord] = []

    def record(self, record: RunRecord) -> int:
        self.records.append(record)
        return len(self.records)


class PgRunRecorder:
    """Inserta en `agent_runs` con el rol `agent_logger` (solo INSERT).

    Si la base no responde, falla rápido (`connect_timeout` corto) y no reintenta durante
    `COOLDOWN_S`: sin esto, cada consulta pagaría el timeout de conexión completo.
    """

    COOLDOWN_S = 30.0
    CONNECT_TIMEOUT_S = 3

    def __init__(self, config: Config | None = None, conn=None) -> None:
        self.cfg = config or load_config()
        self._conn = conn
        self._owns_conn = conn is None
        self._unavailable_until = 0.0

    def _connection(self):
        if self._conn is None or getattr(self._conn, "closed", 0):
            if time.monotonic() < self._unavailable_until:
                raise ConnectionError("la base de trazabilidad no está disponible (en espera)")
            import psycopg2  # diferido: los tests offline no requieren el paquete

            try:
                self._conn = psycopg2.connect(
                    dbname=self.cfg.db_name,
                    user=self.cfg.log_db_user,
                    host=self.cfg.db_host,
                    port=self.cfg.db_port,
                    password=os.environ.get("POSTGRES_LOG_PASSWORD"),  # Art. 9
                    connect_timeout=self.CONNECT_TIMEOUT_S,
                )
            except Exception:
                self._unavailable_until = time.monotonic() + self.COOLDOWN_S
                raise
            self._owns_conn = True
        return self._conn

    def record(self, record: RunRecord) -> int | None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(INSERT_SQL, record.as_params())
                row = cur.fetchone()
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 - la conexión puede estar ya caída
                pass
            raise
        return int(row[0]) if row else None

    def close(self) -> None:
        if self._conn is not None and self._owns_conn:
            try:
                self._conn.close()
            finally:
                self._conn = None


def build_recorder(config: Config | None = None) -> RunRecorder | None:
    """`pg` (por defecto), `memory` (mediciones y tests) u `off`."""
    cfg = config or load_config()
    backend = cfg.runs_backend.lower()
    if backend == "off":
        return None
    if backend == "memory":
        return InMemoryRunRecorder()
    if backend == "pg":
        return PgRunRecorder(cfg)
    raise ValueError(f"AGENT_RUNS_BACKEND inválido: {cfg.runs_backend!r} (pg, memory u off)")
