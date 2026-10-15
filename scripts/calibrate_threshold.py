"""Calibra el umbral de similitud con los documentos reales (T3.6, R-4.8, D12).

El 0.35 inicial era una **hipótesis**; la calibración lo fijó en 0.67 (D85). Este script mide, contra los PDFs ya
indexados en `documentos_embeddings`, la similitud máxima de cada prueba de retrieval:

- R1–R3 (consultas con cobertura): la similitud máxima debe quedar **por encima** del umbral.
- R4 (sin cobertura): la similitud máxima debe quedar **por debajo**.

Si la mayor similitud de R4 es menor que la menor de R1–R3, cualquier umbral entre las dos las separa y
se propone el punto medio. Si se solapan, el umbral no puede separar los casos y se informa: hace
falta otro modelo de embeddings, otro chunking o más casos negativos.

El valor medido y esta salida se registran en `TP/CHANGELOG.md` (R-4.8).

Uso (requiere la base con los documentos indexados y GEMINI_API_KEY):

    .venv/Scripts/python scripts/calibrate_threshold.py [--out evidencia.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.config import load_config  # noqa: E402
from agent.tools.rag_tool import GeminiEmbedder, PgVectorStore, RagRetriever  # noqa: E402
from tests.golden_set import BILINGUAL_SET, CALIBRATION_EXTRA, GOLDEN_SET, RETRIEVAL_TESTS  # noqa: E402


def propose_threshold(positive_max: list[float], negative_max: list[float]) -> dict:
    """Punto medio entre el peor positivo y el mejor negativo, si los separa."""
    if not positive_max or not negative_max:
        return {"separable": None, "reason": "faltan casos positivos o negativos"}
    worst_positive, best_negative = min(positive_max), max(negative_max)
    if best_negative < worst_positive:
        return {
            "separable": True,
            "worst_positive": round(worst_positive, 3),
            "best_negative": round(best_negative, 3),
            "proposed": round((worst_positive + best_negative) / 2, 3),
        }
    return {
        "separable": False,
        "worst_positive": round(worst_positive, 3),
        "best_negative": round(best_negative, 3),
        "reason": "las similitudes de los casos con y sin cobertura se solapan",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="archivo JSON donde guardar la evidencia")
    args = parser.parse_args()

    cfg = load_config()
    store = PgVectorStore(cfg)
    retriever = RagRetriever(GeminiEmbedder(cfg), store, cfg)

    positive: list[float] = []
    negative: list[float] = []
    rows = []
    try:
        # Positivos: las pruebas de retrieval, los casos extra y las preguntas `rag` del golden set (incluido el inglés,
        # que puntúa más bajo y es el que más acota el umbral). Los híbridos no: su consulta documental la redacta el modelo.
        cases = [*RETRIEVAL_TESTS, *CALIBRATION_EXTRA,
                 *(c for c in [*GOLDEN_SET, *BILINGUAL_SET] if c.expected_classification == "rag")]
        for case in cases:
            scores = retriever.scores(case.question)
            top = max(scores) if scores else 0.0
            (negative if case.expected_classification == "none" else positive).append(top)
            rows.append({"id": case.id, "query": case.question, "expected": case.expected_classification,
                         "max_similarity": round(top, 3), "scores": [round(s, 3) for s in scores]})
            print(f"{case.id:<3} {case.expected_classification:<5} max={top:.3f}  {case.question}")
    finally:
        store.close()

    verdict = propose_threshold(positive, negative)
    print(f"\numbral configurado: {cfg.similarity_threshold}")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"threshold": cfg.similarity_threshold, "top_k": cfg.top_k,
                        "embedding_model": cfg.embedding_model, "cases": rows, "verdict": verdict},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0 if verdict.get("separable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
