"""API HTTP con streaming (SSE) sobre el agente.

    uvicorn api.app:app --port 8000

`POST /ask` responde `text/event-stream`. `answer()` es bloqueante y no emite tokens: lo que se
transmite son eventos de estado y, al terminar, el `AgentAnswer` completo.

Eventos:
- `start`:     {"question": ...} apenas se acepta la consulta.
- `classified`: {"classification": "sql|rag|hybrid|none", "language": ...} al terminar de clasificar.
- `tool_call`: {"tool", "sql"|"query"} cuando el agente invoca una herramienta.
- `tool_result`: {"tool", "ok", "rows"|"chunks", "error"} con lo que devolvió.
- `composing`: se arma la respuesta final con fuente y evidencia.
- `step`:      {"step", "duration_s", "input_tokens", "output_tokens", "tools"} al terminar cada paso del agente.
- `heartbeat`: {"elapsed_s": n} cada `HEARTBEAT_S` mientras el agente trabaja (evita cortes por inactividad).
- `result`:    el `AgentAnswer` serializado (answer, answer_kind, sources, evidence, run_id, ...).
- `error`:     {"detail": ...} si el agente lanzó una excepción inesperada.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.agent import AnswerCancelled, EmptyQuestionError, answer

HEARTBEAT_S = 5

app = FastAPI(title="Agente de biblioteca")


class AskRequest(BaseModel):
    question: str


def sse(event: str, data: dict) -> str:
    # `default=str`: las filas pueden traer fechas y `Decimal`.
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _stream(question: str) -> AsyncIterator[str]:
    yield sse("start", {"question": question})
    started = time.monotonic()
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

    def on_event(name: str, data: dict) -> None:  # corre en el hilo del agente
        loop.call_soon_threadsafe(events.put_nowait, (name, data))

    cancel = threading.Event()
    task = asyncio.create_task(asyncio.to_thread(answer, question, on_event, cancel))
    try:
        while not (task.done() and events.empty()):
            try:
                name, data = await asyncio.wait_for(events.get(), timeout=HEARTBEAT_S)
            except TimeoutError:
                if not task.done():
                    yield sse("heartbeat", {"elapsed_s": int(time.monotonic() - started)})
                continue
            yield sse(name, data)
    finally:
        # Si el cliente cortó la conexión, Starlette cierra este generador: se avisa al agente para
        # que no siga gastando cuota. En una corrida normal la tarea ya terminó y no hay nada que cortar.
        if not task.done():
            cancel.set()
    try:
        result = task.result()
    except AnswerCancelled:
        return
    except Exception as exc:  # noqa: BLE001 - se informa al cliente, no se corta el stream en seco
        yield sse("error", {"detail": f"{type(exc).__name__}: {exc}"[:300]})
        return
    yield sse("result", asdict(result))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask")
async def ask(body: AskRequest) -> StreamingResponse:
    if not body.question.strip():
        # R-1.2: se rechaza antes de abrir el stream y sin invocar al agente.
        raise HTTPException(status_code=422, detail=str(EmptyQuestionError("La consulta está vacía.")))
    return StreamingResponse(
        _stream(body.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
