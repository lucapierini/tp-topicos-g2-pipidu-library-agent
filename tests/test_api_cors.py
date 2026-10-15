"""CORS para el frontend externo (R-7.8, D82).

Solo se prueba el contrato HTTP: qué orígenes reciben `Access-Control-Allow-Origin`, cuáles no, y que
no hay wildcard. Sin modelo ni base: `answer` se reemplaza por un doble.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import api.app as api_app  # noqa: E402
from agent.config import load_config  # noqa: E402
from agent.contracts import AgentAnswer  # noqa: E402

ALLOWED = "http://127.0.0.1:5173"
OTHER = "http://127.0.0.1:9999"


def _answer(question: str) -> AgentAnswer:
    return AgentAnswer(
        question=question, classification="sql", sources=["sql"],
        answer="Respuesta.",
        evidence={"sql": "SELECT titulo FROM libros", "rows": [], "language": "es"},
        run_id=1, answer_kind="answer", trace=["classification", "execute_sql"],
    )


@pytest.fixture()
def client(monkeypatch):
    def scripted(question, on_event=None, cancel=None):
        on_event("classified", {"classification": "sql", "language": "es"})
        return _answer(question)

    monkeypatch.setattr(api_app, "answer", scripted)
    return TestClient(api_app.create_app(allowed_origins=(ALLOWED,)))


def test_allowed_origin_gets_the_cors_header(client) -> None:
    response = client.options("/ask", headers={"Origin": ALLOWED, "Access-Control-Request-Method": "POST"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_a_disallowed_origin_is_rejected_without_the_cors_header(client) -> None:
    response = client.options("/ask", headers={"Origin": OTHER, "Access-Control-Request-Method": "POST"})

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_a_simple_request_from_an_allowed_origin_carries_the_header(client) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_no_wildcard_when_no_origins_are_configured() -> None:
    app = api_app.create_app(allowed_origins=())

    response = TestClient(app).get("/health", headers={"Origin": ALLOWED})

    assert response.headers.get("access-control-allow-origin") not in ("*", ALLOWED)


def test_the_stream_from_an_allowed_origin_carries_the_header(client) -> None:
    response = client.post("/ask", json={"question": "¿Qué libros tiene Juan?"}, headers={"Origin": ALLOWED})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    events = [block.split("\n")[0] for block in response.text.strip().split("\n\n")]
    assert events[-1].startswith("event: result")


def test_origins_are_read_from_api_allowed_origins(monkeypatch) -> None:
    monkeypatch.setenv("API_ALLOWED_ORIGINS", "http://127.0.0.1:5173,https://frontend.example")

    origins = load_config().api_allowed_origins

    assert origins == ("http://127.0.0.1:5173", "https://frontend.example")


def test_the_app_uses_the_configured_origins(monkeypatch) -> None:
    monkeypatch.setenv("API_ALLOWED_ORIGINS", ALLOWED)

    app = api_app.create_app(load_config().api_allowed_origins)
    response = TestClient(app).get("/health", headers={"Origin": ALLOWED})

    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_no_credentials_are_required_from_an_allowed_origin(client) -> None:
    response = client.post("/ask", json={"question": "¿Qué libros tiene Juan?"}, headers={"Origin": ALLOWED})

    body = json.loads(response.text.strip().split("\n\n")[-1].split("data: ", 1)[1])

    assert response.status_code == 200
    assert "access-control-allow-credentials" not in response.headers
    assert body["run_id"] == 1
