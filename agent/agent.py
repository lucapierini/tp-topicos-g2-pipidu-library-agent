"""Orquestador del agente (T6.2, T6.3; R-2.x, R-5.x, D1, D2, D3, D8, D15).

Flujo de una consulta:

1. **Clasificación** en salida estructurada (llamada separada, D3). Ocurre antes de cualquier
   herramienta y queda en `trace[0]` (R-2.7).
2. `none` -> respuesta determinista de falta de cobertura. No hay llamada al modelo ni a tools
   (R-2.5): lo que no se llama no se puede inventar.
3. `sql` / `rag` / `hybrid` -> un `ToolCallingAgent` (D2) con **solo** las herramientas de esa
   fuente. El modelo genera el SQL y la herramienta solo valida y ejecuta (D1).
4. **Composición**: las fuentes declaradas son las **efectivamente invocadas** (R-2.7), la
   evidencia sale de lo que devolvieron las tools y no de lo que dijo el modelo (Art. 4), y los
   fallos de herramienta se reportan con una plantilla fija en vez de dejar que el modelo improvise
   sobre datos que no tiene (R-5.7).

Los backends (SQL, recuperación, clasificador, runner) se inyectan: el orquestador se prueba
sin base, sin API y sin `smolagents` (Art. 6).
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from agent.classifier import Classification, Classifier, build_classifier
from agent.config import Config, load_config
from agent.contracts import (
    ANSWER_KIND_ANSWER,
    ANSWER_KIND_ERROR,
    ANSWER_KIND_NO_COVERAGE,
    TRACE_CLASSIFICATION,
    AgentAnswer,
    Chunk,
    RagResult,
    SqlResult,
    ToolSpec,
)
from agent.errors import NO_RELEVANT_RESULTS
from agent.prompts import render_system_prompt
from agent.runs import RunRecorder, build_recorder, record_from_answer

logger = logging.getLogger("agent.agent")

TOOL_EXECUTE_SQL = "execute_sql"
TOOL_RETRIEVE = "retrieve_documents"

TOOLS_BY_CLASSIFICATION = {
    "sql": (TOOL_EXECUTE_SQL,),
    "rag": (TOOL_RETRIEVE,),
    "hybrid": (TOOL_EXECUTE_SQL, TOOL_RETRIEVE),
}
SOURCES_BY_CLASSIFICATION = {"sql": {"sql"}, "rag": {"rag"}, "hybrid": {"sql", "rag"}}

SOURCE_LABELS = {
    "es": {"sql": "SQL", "rag": "RAG", "both": "SQL + RAG", "none": "ninguna", "prefix": "Fuente"},
    "en": {"sql": "SQL", "rag": "RAG", "both": "SQL + RAG", "none": "none", "prefix": "Source"},
}

MESSAGES = {
    "es": {
        "no_coverage": "No dispongo de información suficiente para responder esta consulta con los "
                       "datos de la biblioteca ni con sus documentos.",
        "no_relevant": "No se encontró información relevante en los documentos de la biblioteca para "
                       "esta consulta.",
        "sql_failed": "No pude resolver la consulta con los datos de la base: {error}. {detail}",
        "sql_not_called": "No pude resolver la consulta: no se llegó a consultar la base de datos.",
        "rag_failed": "No pude consultar los documentos de la biblioteca: {error}.",
        "run_failed": "No pude completar la consulta: {detail}",
        "classify_failed": "No pude interpretar la consulta: {detail}",
        "partial_sql": "Nota: no se pudo obtener el dato de la base ({error}), por lo que no es posible concluir.",
        "partial_rag": "Nota: no se encontró la norma en los documentos ({error}), por lo que no es posible concluir.",
        "truncated": "Nota: el resultado se limitó a {n} filas; hay más datos que no se muestran.",
    },
    "en": {
        "no_coverage": "I don't have enough information to answer this question with the library's data "
                       "or its documents.",
        "no_relevant": "No relevant information was found in the library's documents for this question.",
        "sql_failed": "I couldn't resolve the question with the database: {error}. {detail}",
        "sql_not_called": "I couldn't resolve the question: the database was never queried.",
        "rag_failed": "I couldn't query the library's documents: {error}.",
        "run_failed": "I couldn't complete the question: {detail}",
        "classify_failed": "I couldn't interpret the question: {detail}",
        "partial_sql": "Note: the database value could not be obtained ({error}), so no conclusion is possible.",
        "partial_rag": "Note: the rule was not found in the documents ({error}), so no conclusion is possible.",
        "truncated": "Note: the result was limited to {n} rows; there is more data not shown.",
    },
}


class EmptyQuestionError(ValueError):
    """R-1.2: una consulta vacía se rechaza sin invocar al agente."""


class SqlBackend(Protocol):
    def execute_sql(
        self, sql: str, *, attempts: int = 1, sql_original: str | None = None
    ) -> SqlResult: ...


class Retriever(Protocol):
    def retrieve(self, query: str) -> RagResult: ...


class AgentRunner(Protocol):
    def run(self, *, question: str, system_prompt: str, tools: list[ToolSpec], max_steps: int) -> str: ...


# --------------------------------------------------------------------------- runner real


class SmolagentsRunner:
    """`ToolCallingAgent` (D2) sobre Gemini vía LiteLLM, con temperatura 0 y timeout (D15)."""

    def __init__(self, config: Config | None = None, model: Any = None) -> None:
        self.cfg = config or load_config()
        self._model = model

    def _get_model(self):
        if self._model is None:
            import logging

            from smolagents import LiteLLMModel

            # LiteLLM avisa por cada llamada que `temperature` se deprecia en Gemini 3: ruido, no error.
            logging.getLogger("LiteLLM").setLevel(logging.ERROR)

            kwargs: dict[str, Any] = {}
            if self.cfg.llm_api_base:
                # Servidor local OpenAI-compatible: no hay clave real, pero el cliente exige una.
                kwargs["api_base"] = self.cfg.llm_api_base
                kwargs["api_key"] = os.environ.get("LLM_API_KEY") or "not-needed"
            else:
                key = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
                if not key:
                    raise RuntimeError("GEMINI_API_KEY no está definida (Art. 9)")
                kwargs["api_key"] = key
            self._model = LiteLLMModel(
                model_id=self.cfg.llm_model,
                temperature=self.cfg.temperature,
                timeout=self.cfg.api_timeout_s,
                num_retries=self.cfg.api_max_retries,  # LiteLLM reintenta los 429 con espera
                **kwargs,
            )
        return self._model

    def run(self, *, question: str, system_prompt: str, tools: list[ToolSpec], max_steps: int) -> str:
        from smolagents import ToolCallingAgent
        from smolagents.monitoring import LogLevel

        from agent.tools.smol_tools import to_smolagents_tools

        agent = ToolCallingAgent(
            tools=to_smolagents_tools(tools),
            model=self._get_model(),
            instructions=system_prompt,
            max_steps=max_steps,
            verbosity_level=LogLevel.OFF,
        )
        return str(agent.run(question))


# --------------------------------------------------------------------------- sesión de tools


@dataclass
class ToolSession:
    """Lo que devolvieron las herramientas en **esta** consulta. Es la fuente de la evidencia."""

    sql_results: list[SqlResult] = field(default_factory=list)
    rag_results: list[RagResult] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    @property
    def sql_failures(self) -> int:
        return sum(1 for r in self.sql_results if not r.executed)

    @property
    def executed_sql(self) -> list[SqlResult]:
        return [r for r in self.sql_results if r.executed]

    @property
    def chunks(self) -> list[Chunk]:
        seen: dict[str, Chunk] = {}
        for result in self.rag_results:
            for chunk in result.chunks:
                seen.setdefault(chunk.content_hash, chunk)
        return list(seen.values())


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- orquestador


class LibraryAgent:
    def __init__(
        self,
        *,
        classifier: Classifier | None = None,
        sql_backend: SqlBackend | None = None,
        retriever: Retriever | None = None,
        runner: AgentRunner | None = None,
        recorder: RunRecorder | None = None,
        config: Config | None = None,
    ) -> None:
        self.cfg = config or load_config()
        self._classifier = classifier
        self._sql_backend = sql_backend
        self._retriever = retriever
        self._runner = runner
        self._recorder = recorder
        # `recorder=None` explícito no significa "sin registro": significa "el de la configuración".
        self._recorder_resolved = recorder is not None

    # Los backends reales se crean al primer uso: construir el agente no abre conexiones.
    @property
    def classifier(self) -> Classifier:
        if self._classifier is None:
            self._classifier = build_classifier(self.cfg)
        return self._classifier

    @property
    def sql_backend(self) -> SqlBackend:
        if self._sql_backend is None:
            from agent.tools.sql_tool import SqlExecutor

            self._sql_backend = SqlExecutor(self.cfg)
        return self._sql_backend

    @property
    def retriever(self) -> Retriever:
        if self._retriever is None:
            from agent.tools.rag_tool import GeminiEmbedder, PgVectorStore, RagRetriever

            self._retriever = RagRetriever(GeminiEmbedder(self.cfg), PgVectorStore(self.cfg), self.cfg)
        return self._retriever

    @property
    def runner(self) -> AgentRunner:
        if self._runner is None:
            self._runner = SmolagentsRunner(self.cfg)
        return self._runner

    @property
    def recorder(self) -> RunRecorder | None:
        if not self._recorder_resolved:
            self._recorder = build_recorder(self.cfg)  # `pg` | `memory` | `off`
            self._recorder_resolved = True
        return self._recorder

    # ------------------------------------------------------------------ herramientas

    def _sql_tool(self, session: ToolSession) -> ToolSpec:
        max_attempts = self.cfg.max_sql_attempts

        def execute(sql: str) -> str:
            session.trace.append(TOOL_EXECUTE_SQL)
            if session.sql_failures >= max_attempts:
                # D8: el límite lo aplica la herramienta, no el prompt.
                return _json({
                    "ok": False,
                    "error": "ATTEMPTS_EXHAUSTED",
                    "detail": f"se agotaron los {max_attempts} intentos; informá el motivo al usuario",
                })
            result = self.sql_backend.execute_sql(
                sql, attempts=session.sql_failures + 1, sql_original=sql
            )
            session.sql_results.append(result)
            if not result.executed:
                return _json({"ok": False, "error": result.error, "detail": result.detail})
            payload: dict[str, Any] = {
                "ok": True,
                "sql": result.sql,
                "row_count": len(result.rows),
                "rows": result.rows,
                "truncated": result.truncated,
            }
            if not result.rows:
                payload["note"] = "sin resultados: la consulta no devolvió filas"
            return _json(payload)

        return ToolSpec(
            name=TOOL_EXECUTE_SQL,
            description=(
                "Ejecuta UNA sentencia SELECT de PostgreSQL sobre la base de datos de la biblioteca y "
                "devuelve las filas como JSON. Si la sentencia es rechazada devuelve el código de error y "
                "el motivo para que la corrijas."
            ),
            parameter="sql",
            parameter_description="La sentencia SELECT completa, sin punto y coma ni comentarios.",
            fn=execute,
        )

    def _retrieve_tool(self, session: ToolSession) -> ToolSpec:
        def retrieve(query: str) -> str:
            session.trace.append(TOOL_RETRIEVE)
            result = self.retriever.retrieve(query)
            session.rag_results.append(result)
            if result.error:
                return _json({
                    "ok": False,
                    "error": result.error,
                    "detail": "no se encontró información relevante" if result.error == NO_RELEVANT_RESULTS
                    else "falló la recuperación de documentos",
                })
            return _json({
                "ok": True,
                "chunks": [
                    {
                        "document": c.document,
                        "location": c.location,
                        "text": c.text,
                        "similarity": round(c.similarity, 3),
                    }
                    for c in result.chunks
                ],
            })

        return ToolSpec(
            name=TOOL_RETRIEVE,
            description=(
                "Busca en los documentos de la biblioteca (reglamento, manual de uso, políticas, reseñas) "
                "y devuelve los fragmentos más relevantes con su documento y ubicación."
            ),
            parameter="query",
            parameter_description="Palabras clave de la norma, procedimiento o tema que se busca.",
            fn=retrieve,
        )

    def _tools_for(self, label: str, session: ToolSession) -> list[ToolSpec]:
        builders: dict[str, Callable[[ToolSession], ToolSpec]] = {
            TOOL_EXECUTE_SQL: self._sql_tool,
            TOOL_RETRIEVE: self._retrieve_tool,
        }
        return [builders[name](session) for name in TOOLS_BY_CLASSIFICATION[label]]

    # ------------------------------------------------------------------ consulta

    def answer(self, question: str) -> AgentAnswer:
        text = (question or "").strip()
        if not text:
            # R-1.2: no se invoca nada ni se registra: no hay consulta que trazar.
            raise EmptyQuestionError("La consulta está vacía.")

        started = time.perf_counter()
        result = self._resolve(text)
        return self._persist(result, int((time.perf_counter() - started) * 1000))

    def _persist(self, answer: AgentAnswer, latency_ms: int) -> AgentAnswer:
        """Registra la consulta en `agent_runs` (R-6.2, R-6.3).

        Registrar no puede romper la respuesta: si falla, la consulta igual se contesta y el fallo
        queda declarado en la evidencia, sin fingir que se registró.
        """
        recorder = self.recorder
        if recorder is None:
            return answer
        try:
            run_id = recorder.record(record_from_answer(answer, latency_ms))
        except Exception as exc:  # noqa: BLE001
            logger.warning("no se pudo registrar la consulta en agent_runs: %s", type(exc).__name__)
            evidence = {**answer.evidence, "run_recording_error": f"{type(exc).__name__}: {exc}"[:200]}
            return replace(answer, evidence=evidence)
        return replace(answer, run_id=run_id)

    def _resolve(self, text: str) -> AgentAnswer:
        try:
            classification = self.classifier.classify(text)
        except Exception as exc:  # noqa: BLE001 - R-5.7: el fallo se reporta, no se adivina
            detail = f"{type(exc).__name__}: {exc}"[:200]
            return self._gap_answer(
                text, "none", "es", ANSWER_KIND_ERROR, [],
                MESSAGES["es"]["classify_failed"].format(detail=detail),
                error=("CLASSIFICATION_ERROR", detail),
            )

        trace = [TRACE_CLASSIFICATION]
        if classification.label == "none":
            return self._gap_answer(
                text, "none", classification.language, ANSWER_KIND_NO_COVERAGE, trace,
                MESSAGES[classification.language]["no_coverage"],
            )

        session = ToolSession()
        tools = self._tools_for(classification.label, session)
        system_prompt = render_system_prompt(
            self.cfg, classification=classification.label, tools=[t.name for t in tools],
            language=classification.language,
        )
        run_error: str | None = None
        model_text = ""
        try:
            model_text = self.runner.run(
                question=text, system_prompt=system_prompt, tools=tools, max_steps=self.cfg.max_steps
            )
        except Exception as exc:  # noqa: BLE001
            run_error = f"{type(exc).__name__}"

        return self._compose(text, classification, session, model_text, run_error, trace)

    # ------------------------------------------------------------------ composición

    def _model_info(self) -> dict[str, Any]:
        """Qué modelo resolvió la consulta (R-6.5): una corrida local no es evidencia de aceptación.

        Solo identificador y tipo de endpoint: ni la clave ni la URL completa.
        """
        return {"id": self.cfg.llm_model, "endpoint": "local" if self.cfg.llm_api_base else "api"}

    def _gap_answer(
        self, question: str, label: str, language: str, kind: str, trace: list[str], message: str,
        evidence: dict | None = None, error: tuple[str, str] | None = None,
    ) -> AgentAnswer:
        """Respuesta que declara una ausencia o un error: plantilla fija, sin fuentes (R-5.2).

        `error` es (código, detalle): queda en la evidencia y de ahí en `agent_runs` (R-6.3).
        """
        labels = SOURCE_LABELS[language]
        merged = {**(evidence or {}), "model": self._model_info(), "language": language}
        if error is not None:
            merged["error"] = {"code": error[0], "detail": error[1]}
        return AgentAnswer(
            question=question,
            classification=label,
            sources=[],
            answer=f"{message}\n\n{labels['prefix']}: {labels['none']}",
            evidence=merged,
            answer_kind=kind,
            trace=trace,
        )

    def _compose(
        self,
        question: str,
        classification: Classification,
        session: ToolSession,
        model_text: str,
        run_error: str | None,
        trace: list[str],
    ) -> AgentAnswer:
        label, language = classification.label, classification.language
        msg = MESSAGES[language]
        full_trace = trace + session.trace

        executed = session.executed_sql
        chunks = session.chunks
        sources = [s for s, used in (("sql", bool(executed)), ("rag", bool(chunks))) if used]
        expected = SOURCES_BY_CLASSIFICATION[label]

        evidence: dict[str, Any] = {"model": self._model_info(), "language": language}
        if executed:
            last = executed[-1]
            evidence.update(
                sql=last.sql, sql_original=last.sql_original, rows=last.rows,
                truncated=last.truncated, attempts=last.attempts,
            )
        if chunks:
            evidence["chunks"] = [
                {
                    "id": c.id, "document": c.document, "location": c.location, "text": c.text,
                    "similarity": round(c.similarity, 3), "content_hash": c.content_hash,
                }
                for c in chunks
            ]
        failed = [
            {"error": r.error, "detail": r.detail, "sql_original": r.sql_original}
            for r in session.sql_results if not r.executed
        ]
        if failed:
            evidence["sql_errors"] = failed  # R-6.4: lo que generó el modelo y se rechazó
        if session.sql_results:
            # R-6.4: cada intento de generación con su resultado, en orden (los rechazados y el que corrió).
            evidence["sql_attempts"] = [
                {
                    "attempt": index,
                    "sql_original": r.sql_original,
                    "executed_sql": r.sql,
                    "executed": r.executed,
                    "error": r.error,
                    "detail": r.detail,
                    "rows": len(r.rows),
                    "latency_ms": r.latency_ms,
                }
                for index, r in enumerate(session.sql_results, start=1)
            ]
        if sources and set(sources) != expected:
            # R-2.7: la fuente declarada es la efectivamente invocada; la diferencia se registra.
            evidence["inconsistency"] = {"classified": label, "invoked": sources}

        # --- nada utilizable: el error o la ausencia se declaran con plantilla fija ---
        if run_error and not sources:
            return self._gap_answer(
                question, label, language, ANSWER_KIND_ERROR, full_trace,
                msg["run_failed"].format(detail=run_error), evidence,
                error=("RUN_ERROR", run_error),
            )
        if not sources:
            kind, message = self._empty_outcome(label, session, msg)
            return self._gap_answer(
                question, label, language, kind, full_trace, message, evidence,
                error=self._empty_error(label, session),
            )

        body = (model_text or "").strip()
        if not body:
            return self._gap_answer(
                question, label, language, ANSWER_KIND_ERROR, full_trace,
                msg["run_failed"].format(detail="el modelo no devolvió una respuesta"), evidence,
                error=("EMPTY_MODEL_RESPONSE", "el modelo no devolvió una respuesta"),
            )

        notes = []
        if "sql" in expected and "sql" not in sources and session.sql_results:
            last_failed = failed[-1] if failed else {}
            notes.append(msg["partial_sql"].format(error=last_failed.get("error", "sin datos")))
        if "rag" in expected and "rag" not in sources and session.rag_results:
            notes.append(msg["partial_rag"].format(error=session.rag_results[-1].error))
        if executed and executed[-1].truncated:
            notes.append(msg["truncated"].format(n=len(executed[-1].rows)))

        labels = SOURCE_LABELS[language]
        source_text = labels["both"] if len(sources) == 2 else labels[sources[0]]
        answer = "\n\n".join([body, *notes, f"{labels['prefix']}: {source_text}"])
        return AgentAnswer(
            question=question,
            classification=label,
            sources=sources,
            answer=answer,
            evidence=evidence,
            answer_kind=ANSWER_KIND_ANSWER,
            trace=full_trace,
        )

    def _empty_error(self, label: str, session: ToolSession) -> tuple[str, str] | None:
        """(código, detalle) para `agent_runs` cuando no hubo evidencia; `None` si fue falta de cobertura."""
        if "sql" in SOURCES_BY_CLASSIFICATION[label] and not session.sql_results:
            return "TOOL_NOT_CALLED", "no se invocó execute_sql"
        if session.sql_failures:
            last = session.sql_results[-1]
            return last.error or "EXECUTION_ERROR", last.detail or ""
        if session.rag_results:
            error = session.rag_results[-1].error
            if error == NO_RELEVANT_RESULTS:
                return None
            return error or "RETRIEVAL_ERROR", "falló la recuperación de documentos"
        return "TOOL_NOT_CALLED", "no se invocó ninguna herramienta"

    def _empty_outcome(self, label: str, session: ToolSession, msg: dict) -> tuple[str, str]:
        """(answer_kind, mensaje) cuando ninguna herramienta aportó evidencia utilizable."""
        if "sql" in SOURCES_BY_CLASSIFICATION[label] and not session.sql_results:
            return ANSWER_KIND_ERROR, msg["sql_not_called"]
        if session.sql_failures:
            last = session.sql_results[-1]
            return ANSWER_KIND_ERROR, msg["sql_failed"].format(error=last.error, detail=last.detail or "")
        if session.rag_results:
            error = session.rag_results[-1].error
            if error == NO_RELEVANT_RESULTS:
                return ANSWER_KIND_NO_COVERAGE, msg["no_relevant"]
            return ANSWER_KIND_ERROR, msg["rag_failed"].format(error=error)
        return ANSWER_KIND_ERROR, msg["sql_not_called"]


# --------------------------------------------------------------------------- atajo de módulo

_default: LibraryAgent | None = None


def get_agent() -> LibraryAgent:
    global _default
    if _default is None:
        _default = LibraryAgent()
    return _default


def answer(question: str) -> AgentAnswer:
    """Punto de entrada de la UI y del golden set: `answer(question) -> AgentAnswer`."""
    return get_agent().answer(question)
