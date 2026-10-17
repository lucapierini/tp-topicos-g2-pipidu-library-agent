"""Calibra el umbral de similitud con los documentos reales (T3.6, R-4.8, D12, D97).

Este script mide, contra los PDFs ya indexados, la similitud máxima de ~120 consultas etiquetadas
(`tests/calibration_set.py` + los casos del golden set) y deja el umbral como una decisión con números, no con
el mejor y el peor caso:

- **Barrido**: para cada umbral, cuántas consultas cubiertas se aceptan (recall) y cuántas sin cobertura se
  dejan pasar (falsos positivos), con precisión y F1.
- **AUC**: probabilidad de que una consulta cubierta puntúe más alto que una sin cobertura. 1.0 = el modelo de
  embeddings las separa perfecto; 0.5 = no separa nada. Mide qué tan bueno es el *puntaje*, sea cual sea el umbral.
- **Umbrales candidatos**: el de mejor F1, el de Youden (recall + especificidad), el más alto que conserva un
  recall mínimo y el más bajo sin falsos positivos.
- **Por grupo**: mínimo, mediana y máximo de la similitud, para ver qué tipo de consulta confunde.
- **Recuperación**: en las cubiertas, si el fragmento de arriba es del documento esperado.
- **Margen**: similitud del primero menos la del último del top-k; si separa mejor que la similitud sola
  conviene un umbral relativo.

Uso (requiere la base con los documentos indexados y GEMINI_API_KEY):

    python scripts/calibrate_threshold.py [--out evidencia.json] [--min-recall 0.95]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# --------------------------------------------------------------------------- métricas (puras, sin red)


def confusion(positive: list[float], negative: list[float], threshold: float) -> dict:
    """Con `similitud >= umbral` se acepta la consulta. Positivo = cubierta por los documentos."""
    tp = sum(1 for s in positive if s >= threshold)
    fp = sum(1 for s in negative if s >= threshold)
    fn, tn = len(positive) - tp, len(negative) - fp
    recall = tp / len(positive) if positive else 0.0
    specificity = tn / len(negative) if negative else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "threshold": round(threshold, 4), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "recall": round(recall, 4), "specificity": round(specificity, 4),
        "precision": round(precision, 4), "f1": round(f1, 4),
        "youden": round(recall + specificity - 1, 4),
    }


def sweep(positive: list[float], negative: list[float], low: float = 0.50, high: float = 0.90,
          step: float = 0.005) -> list[dict]:
    steps = int(round((high - low) / step))
    return [confusion(positive, negative, low + i * step) for i in range(steps + 1)]


def auc(positive: list[float], negative: list[float]) -> float | None:
    """P(positivo > negativo) + 0.5 * P(empate)."""
    if not positive or not negative:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positive for n in negative)
    return round(wins / (len(positive) * len(negative)), 4)


def _middle(rows: list[dict]) -> float:
    """El centro de una meseta de umbrales empatados: más estable que su borde."""
    return round((rows[0]["threshold"] + rows[-1]["threshold"]) / 2, 3)


def pick_thresholds(table: list[dict], min_recall: float = 0.95) -> dict:
    """Umbrales candidatos a partir del barrido. Cada uno responde una prioridad distinta."""
    if not table:
        return {}
    out: dict = {}
    best_f1 = max(r["f1"] for r in table)
    plateau = [r for r in table if r["f1"] == best_f1]
    out["best_f1"] = {"threshold": _middle(plateau), **{k: plateau[0][k] for k in ("f1", "recall", "fp")}}
    best_youden = max(r["youden"] for r in table)
    plateau = [r for r in table if r["youden"] == best_youden]
    out["youden"] = {"threshold": _middle(plateau), "youden": best_youden,
                     "recall": plateau[0]["recall"], "fp": plateau[0]["fp"]}
    keeps_recall = [r for r in table if r["recall"] >= min_recall]
    if keeps_recall:
        row = keeps_recall[-1]  # el umbral más alto que todavía acepta el recall mínimo
        out["min_recall"] = {"threshold": row["threshold"], "target": min_recall,
                             "recall": row["recall"], "fp": row["fp"], "specificity": row["specificity"]}
    no_fp = [r for r in table if r["fp"] == 0]
    if no_fp:
        row = no_fp[0]  # el más bajo sin falsos positivos
        out["no_false_positive"] = {"threshold": row["threshold"], "recall": row["recall"], "fn": row["fn"]}
    return out


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


def group_stats(rows: list[dict]) -> dict:
    groups: dict[str, list[float]] = {}
    for row in rows:
        groups.setdefault(row["group"], []).append(row["max_similarity"])
    return {
        name: {"n": len(v), "min": round(min(v), 3), "median": round(statistics.median(v), 3),
               "max": round(max(v), 3)}
        for name, v in sorted(groups.items())
    }


# --------------------------------------------------------------------------- casos


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    covered: bool
    group: str
    document: str | None = None


def build_cases() -> list[Case]:
    from tests.calibration_set import CALIBRATION_SET
    from tests.golden_set import BILINGUAL_SET, CALIBRATION_EXTRA, GOLDEN_SET, RETRIEVAL_TESTS

    cases = [Case(c.id, c.question, c.covered, c.group, c.document) for c in CALIBRATION_SET]
    seen = {c.question.casefold() for c in cases}
    # Los casos del golden set: las pruebas de retrieval, los extra y las preguntas `rag` (incluido el inglés).
    # Los híbridos no: su consulta documental la redacta el modelo.
    golden = [*RETRIEVAL_TESTS, *CALIBRATION_EXTRA,
              *(c for c in [*GOLDEN_SET, *BILINGUAL_SET] if c.expected_classification == "rag")]
    for case in golden:
        if case.question.casefold() in seen:
            continue
        seen.add(case.question.casefold())
        cases.append(Case(case.id, case.question, case.expected_classification != "none", "golden"))
    return cases


# --------------------------------------------------------------------------- ejecución


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", help="archivo JSON donde guardar la evidencia")
    parser.add_argument("--min-recall", type=float, default=0.95,
                        help="recall mínimo para el umbral 'min_recall' (por defecto 0.95)")
    args = parser.parse_args()

    from agent.config import load_config
    from agent.tools.rag_tool import GeminiEmbedder, PgVectorStore, RagRetriever

    cfg = load_config()
    store = PgVectorStore(cfg)
    retriever = RagRetriever(GeminiEmbedder(cfg), store, cfg)

    rows = []
    try:
        for case in build_cases():
            ranked = retriever.ranked(case.question)
            scores = [c.similarity for c in ranked]
            top = max(scores) if scores else 0.0
            top_doc = ranked[0].document if ranked else None
            rows.append({
                "id": case.id, "query": case.question, "covered": case.covered, "group": case.group,
                "expected_document": case.document, "max_similarity": round(top, 3),
                "margin": round(top - min(scores), 3) if scores else 0.0,
                "top_document": top_doc,
                "document_ok": (top_doc or "").startswith(case.document) if case.document else None,
                "scores": [round(s, 3) for s in scores],
            })
            mark = "" if case.covered else "  (sin cobertura)"
            print(f"{case.id:<5} {top:.3f}  {case.group:<17} {case.question}{mark}")
    finally:
        store.close()

    positive = [r["max_similarity"] for r in rows if r["covered"]]
    negative = [r["max_similarity"] for r in rows if not r["covered"]]
    table = sweep(positive, negative)
    candidates = pick_thresholds(table, args.min_recall)
    retrieval = [r["document_ok"] for r in rows if r["document_ok"] is not None]
    report = {
        "threshold": cfg.similarity_threshold, "top_k": cfg.top_k, "embedding_model": cfg.embedding_model,
        "n_covered": len(positive), "n_uncovered": len(negative),
        "auc_similarity": auc(positive, negative),
        "auc_margin": auc([r["margin"] for r in rows if r["covered"]],
                          [r["margin"] for r in rows if not r["covered"]]),
        "at_configured": confusion(positive, negative, cfg.similarity_threshold),
        "candidates": candidates,
        "groups": group_stats(rows),
        "retrieval_top1_accuracy": round(sum(retrieval) / len(retrieval), 3) if retrieval else None,
        "verdict": propose_threshold(positive, negative),
    }

    print(f"\ncubiertas: {len(positive)} · sin cobertura: {len(negative)}")
    print(f"AUC de la similitud: {report['auc_similarity']}  (1.0 separa perfecto, 0.5 no separa)")
    print(f"AUC del margen top1-top{cfg.top_k}: {report['auc_margin']}")
    print(f"documento correcto en el primer fragmento: {report['retrieval_top1_accuracy']}")
    print("\numbral  recall  falsos+  precisión   F1")
    for row in table:
        if round(row["threshold"] * 100) % 2 == 0:
            print(f"{row['threshold']:.3f}   {row['recall']:.2f}    {row['fp']:>3}/{len(negative)}   "
                  f"{row['precision']:.2f}      {row['f1']:.2f}")
    print(f"\nconfigurado ({cfg.similarity_threshold}): {json.dumps(report['at_configured'])}")
    print("candidatos:")
    print(json.dumps(candidates, ensure_ascii=False, indent=2))
    print("por grupo:")
    print(json.dumps(report["groups"], ensure_ascii=False, indent=2))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({**report, "sweep": table, "cases": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0 if positive and negative else 1


if __name__ == "__main__":
    raise SystemExit(main())
