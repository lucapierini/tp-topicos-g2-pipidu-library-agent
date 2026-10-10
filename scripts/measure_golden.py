"""Mide el criterio de aceptación R-2.1 contra la API real, sin base ni PDFs (T6.3, T9.1).

Qué es real: el clasificador (Gemini), el loop del agente (smolagents + LiteLLM), el system prompt, el
validador estático de SQL y la composición de la respuesta.
Qué es falso: las filas que devuelve la base y los fragmentos que devuelve la recuperación. Por eso
**no** se evalúa el contenido (los `check` del golden set quedan para cuando exista el seed y los PDFs),
sino lo que el orquestador sí controla: clasificación, herramientas invocadas, orden y SQL válido.

Uso (desde la raíz del repo, con GEMINI_API_KEY en .env):

    .venv/Scripts/python scripts/measure_golden.py [--out evidencia.json] [--only G1,G6]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.agent import LibraryAgent  # noqa: E402
from agent.classifier import build_classifier  # noqa: E402
from agent.config import load_config  # noqa: E402
from agent.contracts import AgentAnswer, RagResult  # noqa: E402
from agent.tools.sql_tool import SqlExecutor  # noqa: E402
from tests.fakes import FakeConn, FakeRetriever, make_chunk  # noqa: E402
from tests.golden_set import ACCEPTANCE_MIN, GOLDEN_SET  # noqa: E402

CANNED_ROWS = [("Cien años de soledad", "2026-09-20"), ("Rayuela", "2026-10-01")]
CANNED_COLUMNS = ["titulo", "fecha_prestamo"]


@dataclass
class CaseReport:
    case_id: str
    expected: str
    got: str = ""
    tools: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    valid: bool = False
    kind: str = ""
    sql_original: str | None = None
    sql_rejections: list[str] = field(default_factory=list)
    seconds: float = 0.0
    error: str = ""
    violations: list[str] = field(default_factory=list)
    before_tools: bool = False

    @property
    def classified_ok(self) -> bool:
        return self.got == self.expected


def build_agent() -> LibraryAgent:
    cfg = load_config()
    conn = FakeConn(rows=CANNED_ROWS, columns=CANNED_COLUMNS)
    retriever = FakeRetriever(RagResult(
        chunks=[make_chunk("reglamento_biblioteca.pdf", "Art. 12",
                           "El plazo de devolución es de 15 días corridos. Vencido el plazo corresponde "
                           "una multa de un día de suspensión por cada día de atraso.", 0.82)],
        error=None, latency_ms=1,
    ))
    return LibraryAgent(
        classifier=build_classifier(cfg),
        sql_backend=SqlExecutor(cfg, conn),
        retriever=retriever,
        config=cfg,
    )


def run_case(agent: LibraryAgent, case) -> CaseReport:
    report = CaseReport(case_id=case.id, expected=case.expected_classification)
    started = time.perf_counter()
    try:
        answer: AgentAnswer = agent.answer(case.question)
    except Exception as exc:  # noqa: BLE001 - la medición no se corta por un caso
        report.error = f"{type(exc).__name__}: {exc}"[:200]
        report.seconds = round(time.perf_counter() - started, 1)
        return report

    report.seconds = round(time.perf_counter() - started, 1)
    report.got = answer.classification
    if answer.answer_kind == "error" and not answer.trace:
        # El clasificador falló (cuota, red, salida inválida): no es una clasificación `none`.
        report.got = "(error)"
        report.error = answer.answer.splitlines()[0][:160]
    report.tools = [t for t in answer.trace if t != "classification"]
    report.sources = answer.sources
    report.valid = answer.is_valid()
    report.kind = answer.answer_kind
    report.violations = answer.violations()
    report.sql_original = answer.evidence.get("sql_original")
    report.sql_rejections = [
        f"{e['error']}: {e['sql_original']}" for e in answer.evidence.get("sql_errors", [])
    ]
    report.before_tools = answer.classified_before_tools
    return report


def summarize(reports: list[CaseReport]) -> dict:
    hybrids = [r for r in reports if r.expected == "hybrid"]
    nones = [r for r in reports if r.expected == "none"]
    sql_cases = [r for r in reports if r.sql_original or r.sql_rejections]
    return {
        "classification_correct": f"{sum(r.classified_ok for r in reports)}/{len(reports)}",
        "acceptance_min": ACCEPTANCE_MIN,
        "hybrids_with_both_tools": f"{sum(set(r.sources) == {'sql', 'rag'} for r in hybrids)}/{len(hybrids)}",
        "none_without_tools": f"{sum(not r.tools for r in nones)}/{len(nones)}",
        "classified_before_tools": f"{sum(r.before_tools for r in reports)}/{len(reports)}",
        "classifier_errors": sum(r.got == "(error)" for r in reports),
        "valid_answers": f"{sum(r.valid for r in reports)}/{len(reports)}",
        "cases_with_sql_rejected": f"{sum(bool(r.sql_rejections) for r in sql_cases)}/{len(sql_cases)}",
        "seconds_total": round(sum(r.seconds for r in reports), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="archivo JSON donde guardar la evidencia")
    parser.add_argument("--only", help="IDs separados por coma, p. ej. G1,G6")
    args = parser.parse_args()

    selected = {s.strip() for s in args.only.split(",")} if args.only else None
    cases = [c for c in GOLDEN_SET if selected is None or c.id in selected]

    agent = build_agent()
    reports: list[CaseReport] = []
    print(f"modelo: {agent.cfg.llm_model} | api_base={agent.cfg.llm_api_base or '-'} | "
          f"max_steps={agent.cfg.max_steps} | temperature={agent.cfg.temperature}\n")
    for case in cases:
        report = run_case(agent, case)
        reports.append(report)
        mark = "OK " if report.classified_ok else "ERR"
        print(f"[{mark}] {case.id:<4} esperado={report.expected:<6} obtuvo={report.got or '-':<6} "
              f"tools={','.join(report.tools) or '-':<30} valido={report.valid!s:<5} {report.seconds:>5}s")
        if report.sql_rejections:
            for rejection in report.sql_rejections:
                print(f"        SQL rechazado -> {rejection[:150]}")
        if report.error:
            print(f"        ERROR -> {report.error}")
        if report.violations:
            print(f"        violaciones -> {report.violations}")

    summary = summarize(reports)
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        cfg = agent.cfg
        payload = {
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": cfg.llm_model,
            "api_base": cfg.llm_api_base or None,
            "config": {"max_steps": cfg.max_steps, "temperature": cfg.temperature,
                       "max_sql_attempts": cfg.max_sql_attempts, "api_max_retries": cfg.api_max_retries},
            "backends": "sql=FakeConn (validador real), rag=FakeRetriever; el contenido no se evalúa",
            "summary": summary,
            "cases": [r.__dict__ for r in reports],
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nevidencia guardada en {args.out}")

    correct = sum(r.classified_ok for r in reports)
    return 0 if correct >= ACCEPTANCE_MIN or selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
