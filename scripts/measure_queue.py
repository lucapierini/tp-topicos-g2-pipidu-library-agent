"""Medición del costo de atender las consultas en serie (T9.11, D77, R-1.3).

Es un script de medición, no un test: afirma tiempos, no resultados, y un test de tiempos sería
flaky en CI (Art. 6, suite determinística). Corre offline: no abre base, no lee credenciales y no
llama a ningún modelo. `answer()` se reemplaza por un doble que duerme un tiempo de servicio fijo S,
así que la espera observada es exactamente la cola del lock (`LibraryAgent._lock`, D77).

Importante: el evento `start` se emite al abrir el stream, antes de tomar el lock. La espera real se
ve en el primer evento del agente (`classified`) y en el `result`. Se usa un servidor real (uvicorn
en un puerto efímero) porque el transporte ASGI de `httpx` acumula el cuerpo y no permite medir el
instante en que llega cada evento.

Uso:
  python scripts/measure_queue.py --service-time 1.0 --counts 1 2 3 5
  python scripts/measure_queue.py --service-time 6.0 --counts 3      # latidos durante la espera
  python scripts/measure_queue.py --evidence                         # latencias reales de TP/evidencia/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import statistics
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import api.app as api_module  # noqa: E402 - el path se agrega antes del import
from agent.agent import AnswerCancelled  # noqa: E402
from agent.contracts import AgentAnswer  # noqa: E402

EVIDENCE_DIR = ROOT / "TP" / "evidencia"
DEFAULT_COUNTS = (1, 2, 3, 5)
DEFAULT_SERVICE_TIME_S = 1.0

# Lock compartido del doble: reproduce la serialización de `LibraryAgent._lock` (D77).
QUEUE_LOCK = threading.Lock()
waits: dict[str, tuple[float, float]] = {}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fake_answer(
    question: str, on_event=None, cancel: threading.Event | None = None, service_time_s: float = 1.0,
) -> AgentAnswer:
    """Doble de `answer()`: espera el lock, informa la clasificación, duerme S y responde."""
    entered = time.monotonic()
    with QUEUE_LOCK:
        acquired = time.monotonic()
        if cancel is not None and cancel.is_set():
            raise AnswerCancelled()
        waits[question] = (entered, acquired)
        if on_event is not None:
            on_event("classified", {"classification": "sql", "language": "es"})
        time.sleep(service_time_s)
        if on_event is not None:
            on_event("composing", {})
    return AgentAnswer(
        question=question,
        classification="sql",
        sources=["sql"],
        answer="respuesta simulada",
        evidence={"queue_wait_s": round(acquired - entered, 3)},
        run_id=None,
        trace=["classification"],
    )


async def one_request(client: httpx.AsyncClient, question: str) -> dict:
    t0 = time.monotonic()
    first_event = None
    classified = None
    result = None
    heartbeats = 0
    async with client.stream("POST", "/ask", json={"question": question}) as resp:
        status = resp.status_code
        async for line in resp.aiter_lines():
            if not line.startswith("event: "):
                continue
            name = line[len("event: ") :]
            if first_event is None:
                first_event = time.monotonic()
            if name == "heartbeat":
                heartbeats += 1
            elif name == "classified" and classified is None:
                classified = time.monotonic()
            elif name == "result":
                result = time.monotonic()
    return {
        "question": question,
        "status": status,
        "first_event_s": round(first_event - t0, 3) if first_event else None,
        "classified_s": round(classified - t0, 3) if classified else None,
        "result_s": round(result - t0, 3) if result else None,
        "heartbeats": heartbeats,
    }


async def run_case(service_time_s: float, n: int) -> list[dict]:
    def double(question, on_event=None, cancel=None):
        return fake_answer(question, on_event, cancel, service_time_s)

    api_module.answer = double
    waits.clear()

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(api_module.create_app(), host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=60.0) as client:
            results = await asyncio.gather(*(one_request(client, f"q{i}") for i in range(1, n + 1)))
    finally:
        server.should_exit = True
        await task
    return sorted(results, key=lambda r: r["classified_s"] or 0.0)


def _stats(values: list[float], unit: str) -> dict[str, float]:
    return {
        "unit": unit,
        "n": len(values),
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "max": round(max(values), 3),
    }


def evidence_latencies() -> dict[str, dict[str, float]]:
    """Latencias reales ya medidas en TP/evidencia/ (no se vuelve a llamar al modelo)."""
    out: dict[str, dict[str, float]] = {}
    runs = json.loads((EVIDENCE_DIR / "agent_runs_2026-10-11.json").read_text(encoding="utf-8"))["runs"]
    values_ms = [r["latency_ms"] for r in runs if r.get("latency_ms") is not None]
    out["agent_runs_2026-10-11.json"] = _stats(values_ms, unit="ms")
    for path in sorted(EVIDENCE_DIR.glob("golden_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        seconds = [c["seconds"] for c in data.get("cases", []) if c.get("seconds") is not None]
        if seconds:
            out[path.name] = _stats(seconds, unit="s")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Mide la espera de la cola del lock (T9.11, D77).")
    parser.add_argument("--service-time", type=float, default=DEFAULT_SERVICE_TIME_S, help="S simulado en segundos")
    parser.add_argument("--counts", type=int, nargs="*", default=list(DEFAULT_COUNTS))
    parser.add_argument("--evidence", action="store_true", help="resume las latencias ya medidas en TP/evidencia/")
    args = parser.parse_args()

    if args.evidence:
        for name, st in evidence_latencies().items():
            print(f"{name}: n={st['n']} min={st['min']}{st['unit']} median={st['median']}{st['unit']} max={st['max']}{st['unit']}")
        return

    print(f"S simulado = {args.service_time} s (no es latencia de modelo). HEARTBEAT_S = {api_module.HEARTBEAT_S} s")
    for n in args.counts:
        rows = asyncio.run(run_case(args.service_time, n))
        print(f"\nN = {n}")
        print(f"{'orden':>5} {'consulta':>8} {'1er evento':>10} {'classified':>10} {'result':>8} {'latidos':>7}")
        for k, row in enumerate(rows, start=1):
            print(
                f"{k:>5} {row['question']:>8} {row['first_event_s']:>10} {row['classified_s']:>10} "
                f"{row['result_s']:>8} {row['heartbeats']:>7}"
            )
        waits_sorted = sorted((b - a) for a, b in waits.values())
        print("esperas de cola (s):", [round(w, 3) for w in waits_sorted])


if __name__ == "__main__":
    main()
