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

CORS: los orígenes del frontend se declaran en `API_ALLOWED_ORIGINS` (R-7.8, D82). Sin autenticación:
el servicio corre en entorno local (D81).
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
import threading
import time
import traceback
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.agent import AnswerCancelled, EmptyQuestionError, answer
from agent.config import load_config

HEARTBEAT_S = 5
_DONE = "__done__"  # marcador interno: el agente terminó; nunca sale al cliente


def _report_loop_exception(_loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Handler del bucle de eventos que no pasa por `logging`.

    El handler por defecto escribe con `logging` y el filtro de litellm falla con `KeyError: 'litellm'`;
    este handler escribe directo en stderr.
    """
    exc = context.get("exception")
    detail = "".join(traceback.format_exception(exc)) if exc else ""
    print(f"asyncio: {context.get('message')}\n{detail}", file=sys.stderr, flush=True)


def _preload_model_libraries() -> None:
    """Carga `litellm` antes de atender la primera consulta.

    smolagents lo importa perezosamente dentro del hilo del agente. Mientras tanto el hilo del servidor
    registra el acceso de `POST /ask` y el filtro de logging de litellm intenta importar `litellm.rust_bridge`
    con el paquete a medio cargar: `KeyError: 'litellm'`, la respuesta se corta antes del primer evento y el
    cliente queda en «Trabajando…». Con el módulo ya cargado no hay carrera.
    """
    try:
        importlib.import_module("litellm")
    except ImportError:  # sin la dependencia opcional no hay nada que precargar
        pass


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    asyncio.get_running_loop().set_exception_handler(_report_loop_exception)
    await asyncio.to_thread(_preload_model_libraries)
    yield


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
    # Al terminar el agente se encola un marcador. El marcador evita esperar el próximo evento o el
    # latido (hasta HEARTBEAT_S) antes de emitir el `result`.
    # Los eventos del agente se encolan antes que el marcador, así que el orden se conserva.
    task.add_done_callback(lambda _task: events.put_nowait((_DONE, {})))
    # Si el cliente corta, el generador se cierra sin leer el resultado: este callback consume la
    # excepción para que asyncio no la registre por el logger.
    task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
    try:
        while True:
            try:
                name, data = await asyncio.wait_for(events.get(), timeout=HEARTBEAT_S)
            except TimeoutError:
                if not task.done():
                    yield sse("heartbeat", {"elapsed_s": int(time.monotonic() - started)})
                continue
            if name == _DONE:
                break
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


def create_app(allowed_origins: Sequence[str] = ()) -> FastAPI:
    """Construye la app con los orígenes del frontend (R-7.8, D82).

    Sin orígenes configurados no se agrega el middleware: la API no declara
    `Access-Control-Allow-Origin` y un navegador desde otro origen no puede leer la respuesta. No se usa
    `*` y no hay credenciales (R-7.8): el servicio corre en entorno local (D81).
    """
    app = FastAPI(title="Agente de biblioteca", lifespan=_lifespan)
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            allow_methods=["POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            allow_credentials=False,
        )

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

    return app


app = create_app(load_config().api_allowed_origins)
