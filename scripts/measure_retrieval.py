"""Mide `RagRetriever.retrieve()` de producción con las dos estrategias, sobre los sets de calibración y validación (R-4.11, D100).

`scripts/evaluate_retrieval.py` simula las estrategias para elegir parámetros. Este script ejecuta el código real que
usa el agente —`retrieve()` con `rag_strategy="rerank"` y con `"dense"`— y cuenta lo que importa en producción:

- una consulta **cubierta** debe devolver fragmentos (si no, el usuario ve «no encontré nada» y el documento sí lo tenía);
- una **sin cobertura** no debe devolver ninguno (si lo hace, el modelo recibe fragmentos que no contestan);
- el primer fragmento de una cubierta debe ser del documento esperado;
- la latencia de cada `retrieve()` (el re-ranking suma una llamada al modelo).

Uso (requiere la base con los documentos y GEMINI_API_KEY; los vectores se cachean en `.cache/`):

    python scripts/measure_retrieval.py [--out TP/evidencia/retrieval_produccion.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def tally(results: list[dict]) -> dict:
    """Resumen de aciertos y errores de una estrategia. `accepted` = devolvió al menos un fragmento."""
    pos = [r for r in results if r["covered"]]
    neg = [r for r in results if not r["covered"]]
    tp = sum(r["accepted"] for r in pos)
    fp = sum(r["accepted"] for r in neg)
    docs = [r["top_document_ok"] for r in pos if r["accepted"] and r["top_document_ok"] is not None]
    latencies = sorted(r["latency_ms"] for r in results)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / len(pos) if pos else 0.0
    return {
        "covered": len(pos), "uncovered": len(neg),
        "recall": round(recall, 3), "missed": len(pos) - tp,
        "false_positives": fp, "false_positive_rate": round(fp / len(neg), 3) if neg else 0.0,
        "precision": round(precision, 3),
        "f1": round(2 * precision * recall / (precision + recall), 3) if (precision + recall) else 0.0,
        "top_document_accuracy": round(sum(docs) / len(docs), 3) if docs else None,
        "latency_ms_median": int(statistics.median(latencies)) if latencies else 0,
        "latency_ms_p95": latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0,
    }


class CountingReranker:
    """Cuenta las llamadas al modelo y las que fallaron (esas consultas volvieron al coseno)."""

    def __init__(self, inner) -> None:
        self.inner, self.calls, self.failures = inner, 0, 0

    def relevances(self, question, items):
        self.calls += 1
        try:
            return self.inner.relevances(question, items)
        except Exception:
            self.failures += 1
            raise


def run(cases, retriever) -> list[dict]:
    out = []
    for case in cases:
        started = time.perf_counter()
        result = retriever.retrieve(case.question)
        latency = int((time.perf_counter() - started) * 1000)
        top = result.chunks[0].document if result.chunks else None
        out.append({
            "id": case.id, "query": case.question, "covered": case.covered, "group": case.group,
            "accepted": bool(result.chunks), "error": result.error, "latency_ms": latency,
            "top_document": top,
            "top_document_ok": (top or "").startswith(case.document) if case.document and top else None,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="TP/evidencia/retrieval_produccion.json")
    parser.add_argument("--embeddings-cache", default=".cache/query_embeddings.json")
    args = parser.parse_args()

    from agent.config import load_config
    from agent.tools.rag_tool import GeminiEmbedder, PgVectorStore, RagRetriever
    from agent.tools.reranker import GeminiReranker
    from scripts.calibrate_threshold import build_cases
    from scripts.evaluate_retrieval import CachedEmbedder, build_validation_cases

    cfg = load_config()
    store = PgVectorStore(cfg)
    embedder = CachedEmbedder(GeminiEmbedder(cfg), Path(args.embeddings_cache), cfg.embedding_model, cfg.embedding_dim)
    sets = {"calibracion": build_cases(), "validacion": build_validation_cases()}
    reranker = CountingReranker(GeminiReranker(cfg))
    strategies = {
        "dense": RagRetriever(embedder, store, replace(cfg, rag_strategy="dense")),
        "rerank": RagRetriever(embedder, store, replace(cfg, rag_strategy="rerank"), reranker),
    }
    report: dict = {"config": {"similarity_threshold": cfg.similarity_threshold,
                               "rerank_threshold": cfg.rerank_threshold, "top_k": cfg.top_k}, "results": {}}
    try:
        for set_name, cases in sets.items():
            for name, retriever in strategies.items():
                rows = run(cases, retriever)
                report["results"][f"{set_name}/{name}"] = {"summary": tally(rows), "cases": rows}
    finally:
        store.close()
    report["reranker"] = {"calls": reranker.calls, "failures": reranker.failures}

    print(f"{'conjunto / estrategia':<24}{'recall':>7}{'perdidas':>9}{'falsos+':>9}{'prec.':>7}{'F1':>6}{'doc 1º':>8}"
          f"{'mediana':>9}{'p95':>8}")
    for key, value in report["results"].items():
        s = value["summary"]
        print(f"{key:<24}{s['recall']:>7.2f}{s['missed']:>6}/{s['covered']:<2}{s['false_positives']:>6}/{s['uncovered']:<2}"
              f"{s['precision']:>7.2f}{s['f1']:>6.2f}{(s['top_document_accuracy'] or 0):>8.2f}"
              f"{s['latency_ms_median']:>7}ms{s['latency_ms_p95']:>6}ms")
    print(f"\nllamadas al re-ranker: {reranker.calls} · fallidas (volvieron al coseno): {reranker.failures}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
