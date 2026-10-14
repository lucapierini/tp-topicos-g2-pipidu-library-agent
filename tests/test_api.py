"""API HTTP con streaming SSE (R-7.1 a R-7.7), sin modelo ni base.

`api.app.answer` se reemplaza por un doble que emite eventos como lo haría el agente. Lo que se prueba
es el contrato HTTP: qué eventos salen, en qué orden, cómo se rechaza una consulta vacía, cuándo hay
latidos y qué pasa cuando el cliente corta.
"""
from __future__ import annotations

import asyncio
import gc
import json
import threading
import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import api.app as api_app  # noqa: E402
from agent.agent import AnswerCancelled  # noqa: E402
from agent.contracts import AgentAnswer  # noqa: E402


def _answer(question: str = "¿Qué libros tiene Juan?") -> AgentAnswer:
    return AgentAnswer(
        question=question, classification="sql", sources=["sql"],
        answer="Juan tiene prestado Rayuela.\n\nFuente: SQL",
        evidence={"sql": "SELECT titulo FROM libros", "rows": [{"titulo": "Rayuela"}], "language": "es"},
        run_id=3, answer_kind="answer", trace=["classification", "execute_sql"],
    )


def _scripted(question, on_event=None, cancel=None):
    on_event("classified", {"classification": "sql", "language": "es"})
    on_event("tool_call", {"tool": "execute_sql", "sql": "SELECT titulo FROM libros"})
    on_event("tool_result", {"tool": "execute_sql", "ok": True, "rows": 1, "error": None, "detail": None})
    on_event("composing", {})
    return _answer(question)


def _events(response) -> list[tuple[str, dict]]:
    """Parsea el cuerpo `text/event-stream` en pares (evento, datos)."""
    parsed = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


@pytest.fixture()
def client():
    return TestClient(api_app.app)


def test_health_answers_without_invoking_the_agent(client, monkeypatch) -> None:
    monkeypatch.setattr(api_app, "answer", lambda *a, **k: pytest.fail("no debe invocar al agente"))

    response = client.get("/health")

    assert response.status_code == 200 and response.json() == {"status": "ok"}


@pytest.mark.parametrize("question", ["", "   ", "\n\t "])
def test_an_empty_question_is_rejected_before_opening_the_stream(client, monkeypatch, question) -> None:
    # R-1.2, R-7.4: 422 y el agente no se invoca.
    monkeypatch.setattr(api_app, "answer", lambda *a, **k: pytest.fail("no debe invocar al agente"))

    response = client.post("/ask", json={"question": question})

    assert response.status_code == 422
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_the_stream_reports_progress_in_order_and_ends_with_the_full_answer(client, monkeypatch) -> None:
    monkeypatch.setattr(api_app, "answer", _scripted)

    response = client.post("/ask", json={"question": "¿Qué libros tiene Juan?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in _events(response)]
    assert names == ["start", "classified", "tool_call", "tool_result", "composing", "result"]


def test_the_result_event_carries_the_complete_agent_answer(client, monkeypatch) -> None:
    monkeypatch.setattr(api_app, "answer", _scripted)

    events = _events(client.post("/ask", json={"question": "q"}))

    name, payload = events[-1]
    assert name == "result"
    assert payload["answer_kind"] == "answer" and payload["sources"] == ["sql"]
    assert payload["answer"].endswith("Fuente: SQL")
    assert payload["evidence"]["sql"] == "SELECT titulo FROM libros"
    assert payload["run_id"] == 3


def test_only_the_result_event_declares_sources(client, monkeypatch) -> None:
    # Art. 4 / D58: lo anterior al `result` es progreso, no una respuesta con proveniencia.
    monkeypatch.setattr(api_app, "answer", _scripted)

    events = _events(client.post("/ask", json={"question": "q"}))

    assert [name for name, data in events if "sources" in data] == ["result"]


def test_dates_and_decimals_in_the_rows_are_serialized(client, monkeypatch) -> None:
    from datetime import date
    from decimal import Decimal

    def with_rows(question, on_event=None, cancel=None):
        result = _answer(question)
        result.evidence["rows"] = [{"fecha": date(2026, 10, 1), "monto": Decimal("12.50")}]
        return result

    monkeypatch.setattr(api_app, "answer", with_rows)

    events = _events(client.post("/ask", json={"question": "q"}))

    assert events[-1][1]["evidence"]["rows"][0] == {"fecha": "2026-10-01", "monto": "12.50"}


def test_an_unexpected_exception_is_reported_as_an_error_event(client, monkeypatch) -> None:
    def broken(question, on_event=None, cancel=None):
        raise RuntimeError("se cayó la base")

    monkeypatch.setattr(api_app, "answer", broken)

    response = client.post("/ask", json={"question": "q"})

    events = _events(response)
    assert response.status_code == 200
    assert [name for name, _ in events] == ["start", "error"]
    assert "RuntimeError" in events[-1][1]["detail"]


def test_heartbeats_are_sent_while_the_agent_is_silent(client, monkeypatch) -> None:
    # R-7.3: sin latidos un proxy corta la conexión durante una espera larga de cuota.
    monkeypatch.setattr(api_app, "HEARTBEAT_S", 0.05)

    def slow(question, on_event=None, cancel=None):
        time.sleep(0.4)
        return _answer(question)

    monkeypatch.setattr(api_app, "answer", slow)

    names = [name for name, _ in _events(client.post("/ask", json={"question": "q"}))]

    assert names.count("heartbeat") >= 1
    assert names[0] == "start" and names[-1] == "result"


def test_the_result_is_not_delayed_by_the_heartbeat_interval(monkeypatch) -> None:
    # Regresión: el bucle esperaba el próximo evento y, al terminar el agente sin emitir nada más, el
    # `result` salía recién al vencer el latido (hasta HEARTBEAT_S de retraso en cada consulta).
    def instant(question, on_event=None, cancel=None):
        on_event("composing", {})
        return _answer(question)

    monkeypatch.setattr(api_app, "answer", instant)
    assert api_app.HEARTBEAT_S >= 5, "el test necesita el intervalo real para detectar el retraso"

    async def timed() -> float:
        started = time.perf_counter()
        _ = [chunk async for chunk in api_app._stream("q")]
        return time.perf_counter() - started

    assert asyncio.run(timed()) < 2.0


def test_closing_the_stream_cancels_the_agent(monkeypatch) -> None:
    # R-7.5: si el cliente corta, el agente recibe la señal y no sigue gastando cuota.
    seen: dict = {}

    def waits_for_cancel(question, on_event=None, cancel=None):
        seen["cancel"] = cancel
        on_event("classified", {"classification": "sql", "language": "es"})
        cancel.wait(timeout=5)
        raise AnswerCancelled()

    monkeypatch.setattr(api_app, "answer", waits_for_cancel)

    async def consume_and_drop() -> None:
        stream = api_app._stream("q")
        await stream.__anext__()   # start
        await stream.__anext__()   # classified
        await stream.aclose()      # el cliente se fue

    asyncio.run(consume_and_drop())

    assert isinstance(seen["cancel"], threading.Event) and seen["cancel"].is_set()


def test_a_cancelled_answer_does_not_emit_a_result(monkeypatch) -> None:
    def cancelled(question, on_event=None, cancel=None):
        raise AnswerCancelled()

    monkeypatch.setattr(api_app, "answer", cancelled)

    async def collect() -> list[str]:
        return [chunk async for chunk in api_app._stream("q")]

    chunks = asyncio.run(collect())

    assert all("event: result" not in chunk and "event: error" not in chunk for chunk in chunks)


def test_a_cancelled_answer_after_the_client_left_leaves_no_unretrieved_exception(monkeypatch) -> None:
    # R-7.5: cortar la conexión no debe dejar la excepción de cancelación sin recuperar: asyncio la
    # registra al recolectar la tarea y ese registro llegó a dejar la API sin responder.
    def waits_for_cancel(question, on_event=None, cancel=None):
        on_event("classified", {"classification": "sql", "language": "es"})
        cancel.wait(timeout=5)
        raise AnswerCancelled()

    monkeypatch.setattr(api_app, "answer", waits_for_cancel)
    reported: list[dict] = []

    async def run() -> None:
        asyncio.get_running_loop().set_exception_handler(lambda _loop, context: reported.append(context))
        stream = api_app._stream("q")
        await stream.__anext__()   # start
        await stream.__anext__()   # classified
        await stream.aclose()      # el cliente se fue
        del stream
        await asyncio.sleep(0.3)   # el hilo del agente termina con AnswerCancelled
        gc.collect()               # asyncio avisa de las excepciones sin recuperar al recolectar la tarea

    asyncio.run(run())

    assert reported == []



def test_the_loop_exception_handler_reports_without_going_through_logging(capsys) -> None:
    # El registro por `logging` rompía dentro del filtro de litellm y ocultaba el error real.
    loop = asyncio.new_event_loop()
    try:
        api_app._report_loop_exception(loop, {"message": "Task exception was never retrieved", "exception": ValueError("boom")})
    finally:
        loop.close()

    err = capsys.readouterr().err
    assert "Task exception was never retrieved" in err and "ValueError: boom" in err


def test_the_app_installs_the_loop_exception_handler_on_startup() -> None:
    with TestClient(api_app.app) as started:
        started.get("/health")
    # TestClient ejecuta el lifespan: si el handler no se pudiera instalar, el arranque fallaría.


def test_litellm_is_loaded_before_the_first_request() -> None:
    # La primera consulta importaba litellm en el hilo del agente mientras el hilo del servidor registraba el
    # acceso: el filtro de logging de litellm fallaba con `KeyError: 'litellm'` y la respuesta no llegaba.
    pytest.importorskip("litellm")
    import sys

    sys.modules.pop("litellm", None)
    with TestClient(api_app.app):
        assert "litellm" in sys.modules
