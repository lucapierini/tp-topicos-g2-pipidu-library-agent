"""Hace una pregunta al agente real (Gemini + base + RAG) y muestra la respuesta con su evidencia.

Sirve para probar la infraestructura de punta a punta mientras no existe la UI (tarea 8.1):

    python scripts/ask.py "¿Cuántos días puedo tener un libro prestado siendo alumno?"
    docker compose run --rm agent "¿Qué libros de Borges hay?"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.agent import answer  # noqa: E402


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Uso: ask.py "<pregunta>"', file=sys.stderr)
        return 2
    result = answer(question)
    print(f"clasificación: {result.classification} | fuentes: {result.sources} | tipo: {result.answer_kind}")
    print(f"traza: {' > '.join(result.trace)}")
    sql = result.evidence.get("sql")
    if sql:
        print(f"sql: {sql}")
    for chunk in result.evidence.get("chunks", []):
        print(f"fragmento: {json.dumps(chunk, ensure_ascii=False, default=str)[:200]}")
    print("\n" + result.answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
