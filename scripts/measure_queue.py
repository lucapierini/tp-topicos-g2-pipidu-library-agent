"""Medición del costo de atender las consultas en serie (T9.11, D77, R-1.3).

Es un script de medición, no un test: afirma tiempos, no resultados, y un test de tiempos sería
flaky en CI (Art. 6, suite determinística). Corre offline: no abre base, no lee credenciales y no
llama a ningún modelo.

Qué se prueba acá: se usa el `answer()` real de `LibraryAgent` con su `_lock` real (D77), sobre
dobles de `tests/fakes.py` (base falsa, clasificador doble, recorder apagado). Lo único que tarda
es la llamada al modelo: el runner doble duerme un tiempo de servicio S dentro del lock. Entonces la
espera observada es la cola del lock real, y S sigue siendo simulado — no una latencia de modelo.

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
import time
from dataclasses import replace
from pathlib import Path

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import api.app as api_module  # noqa: E402 - el path se agrega antes del import
from agent.agent import LibraryAgent  # noqa: E402
from agent.config import load_config  # noqa: E402
from tests import fakes  # noqa: E402

EVIDENCE_DIR = ROOT / "TP" / "evidencia"
DEFAULT_COUNTS = (1, 2, 3, 5)
DEFAULT_SERVICE_TIME_S = 1.0

# Sentencia aceptada por el validador, para que el flujo real complete la etapa de herramientas.
MEASURE_SQL = "SELECT l.titulo FROM prestamos p JOIN libros l ON l.id = p.libro_id"

# `question -> [instante en que entra al agente, instante en que entra a la llamada al modelo]`.
# El segundo instante está dentro del lock real: es el turno de la consulta.
waits: dict[str, list[float]] = {}


class SleepingModel(fakes.ScriptedRunner):
    """Modelo simulado: duerme S dentro del lock. Es la única parte que tarda."""

    def __init__(self, service_time_s: float) -> None:
        super().__init__(steps=[("execute_sql", MEASURE_SQL)], text="respuesta simulada")
        self.service_time_s = service_time_s

    def run(self, *, question: str, system_prompt: str, tools, max_steps: int,
           on_event=None, cancel=None) -> str:
        waits[question][1] = time.monotonic()
        time.sleep(self.service_time_s)
        return super().run(question=question, system_prompt=system_prompt, tools=tools,
                           max_steps=max_steps, on_event=on_event, cancel=cancel)


def build_agent(service_time_s: float) -> LibraryAgent:
    """El agente real, con backends dobles y sin registro en base (`runs_backend="off"`)."""
    return LibraryAgent(
        classifier=fakes.FakeClassifier("sql", "es"),
        sql_backend=fakes.sql_backend(),
        retriever=fakes.FakeRetriever(),
        runner=SleepingModel(service_time_s),
        config=replace(load_config(), runs_backend="off"),
    )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
    agent = build_agent(service_time_s)
    original_answer = api_module.answer

    def measured(question, on_event=None, cancel=None):
        waits[question] = [time.monotonic(), None]
        return agent.answer(question, on_event, cancel)

    api_module.answer = measured
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
        api_module.answer = original_answer
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
    parser = argparse.ArgumentParser(description="Mide la espera de la cola del lock real (T9.11, D77).")
    parser.add_argument("--service-time", type=float, default=DEFAULT_SERVICE_TIME_S, help="S simulado en segundos")
    parser.add_argument("--counts", type=int, nargs="*", default=list(DEFAULT_COUNTS))
    parser.add_argument("--evidence", action="store_true", help="resume las latencias ya medidas en TP/evidencia/")
    args = parser.parse_args()

    if args.evidence:
        for name, st in evidence_latencies().items():
            print(f"{name}: n={st['n']} min={st['min']}{st['unit']} median={st['median']}{st['unit']} max={st['max']}{st['unit']}")
        return

    print(f"S simulado = {args.service_time} s (no es latencia de modelo). "
          f"HEARTBEAT_S = {api_module.HEARTBEAT_S} s. Lock: `LibraryAgent._lock` real.")
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
