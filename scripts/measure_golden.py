"""Mide el criterio de aceptación R-2.1 contra la API real, sin base ni PDFs (T6.3, T9.1).

Qué es real: el clasificador (Gemini), el loop del agente (smolagents + LiteLLM), el system prompt, el
validador estático de SQL y la composición de la respuesta.
Qué es falso por defecto: las filas que devuelve la base y los fragmentos que devuelve la recuperación.
Por eso **no** se evalúa el contenido, sino lo que el orquestador sí controla: clasificación,
herramientas invocadas, orden y SQL válido. Con `--db` las filas son reales (rol `agent_ro`) y con
`--rag-mock` los fragmentos salen del corpus simulado de `tests/rag_fixture.py` (D69); el `check` de
contenido de cada caso se evalúa solo si sus fuentes no son falsas.

Uso (desde la raíz del repo, con GEMINI_API_KEY en .env):

    .venv/Scripts/python scripts/measure_golden.py [--out evidencia.json] [--only G1,G6] [--db] [--rag-mock]
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
from agent.runs import InMemoryRunRecorder, PgRunRecorder  # noqa: E402
from agent.tools.sql_tool import SqlExecutor  # noqa: E402
from tests.fakes import FakeConn, FakeRetriever, make_chunk  # noqa: E402
from tests.golden_set import ACCEPTANCE_MIN, BILINGUAL_SET, GOLDEN_SET  # noqa: E402
from tests.rag_fixture import build_mock_retriever  # noqa: E402

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
    run_id: int | None = None          # fila de agent_runs (R-6.2)
    rows: int = 0
    content_ok: bool | None = None     # check del golden set; solo si las fuentes del caso no son falsas
    language: str = ""                 # idioma con el que el agente compuso la respuesta (R-5.1)

    @property
    def classified_ok(self) -> bool:
        return self.got == self.expected


def build_agent(use_db: bool = False, rag_mock: bool = False, rag_real: bool = False) -> LibraryAgent:
    """`use_db=True`: ejecuta el SQL contra la base local (rol `agent_ro`) y registra en `agent_runs`.

    `rag_mock=True`: la recuperación usa el corpus simulado de `tests/rag_fixture.py` (un `RagRetriever`
    real con embedder léxico); permite evaluar el contenido de los casos RAG e híbridos sin PDFs. Sin
    él, la recuperación devuelve siempre el mismo fragmento falso.

    `rag_real=True`: la recuperación es la de producción (embeddings de Gemini, pgvector y la estrategia
    `RAG_STRATEGY`, con re-ranking por defecto); necesita la base con los documentos ingestados.
    """
    cfg = load_config()
    conn = FakeConn(rows=CANNED_ROWS, columns=CANNED_COLUMNS)
    if rag_real:
        retriever = None  # `LibraryAgent` arma el recuperador de producción
    elif rag_mock:
        retriever = build_mock_retriever(cfg)
    else:
        retriever = FakeRetriever(RagResult(
            chunks=[make_chunk("reglamento_biblioteca.pdf", "Art. 12",
                               "El plazo de devolución es de 15 días corridos. Vencido el plazo "
                               "corresponde una multa de un día de suspensión por cada día de atraso.",
                               0.82)],
            error=None, latency_ms=1,
        ))
    return LibraryAgent(
        classifier=build_classifier(cfg),
        sql_backend=SqlExecutor(cfg) if use_db else SqlExecutor(cfg, conn),
        retriever=retriever,
        # Con base real la corrida deja su traza en `agent_runs`; sin base, en memoria.
        recorder=PgRunRecorder(cfg) if use_db else InMemoryRunRecorder(),
        config=cfg,
    )


def run_case(agent: LibraryAgent, case, with_content: bool = False) -> CaseReport:
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
    report.run_id = answer.run_id
    report.language = answer.evidence.get("language", "")
    report.rows = len(answer.evidence.get("rows", []))
    if with_content:
        report.content_ok = bool(case.check(answer.as_outcome()))
    return report


def content_evaluable(expected: str, use_db: bool, rag_mock: bool, rag_real: bool = False) -> bool:
    """El `check` de un caso solo significa algo si las fuentes que usa no son falsas.

    SQL necesita la base local; RAG, el corpus simulado; un híbrido, las dos. `none` no depende de
    ninguna fuente: debe terminar sin filas ni fragmentos.
    """
    rag = rag_mock or rag_real
    return {
        "sql": use_db,
        "rag": rag,
        "hybrid": use_db and rag,
        "none": True,
    }[expected]


def _ratio(values: list[bool]) -> str:
    return f"{sum(values)}/{len(values)}" if values else "no evaluado"


def summarize_english(reports: list[CaseReport]) -> dict:
    """Casos en inglés (T7.6): fuera del criterio R-2.1, que se mide solo sobre los 13 del golden set."""
    return {
        "cases": [r.case_id for r in reports],
        "classification_correct": f"{sum(r.classified_ok for r in reports)}/{len(reports)}",
        "declared_language_en": f"{sum(r.language == 'en' for r in reports)}/{len(reports)}",
        "content_ok": _ratio([r.content_ok for r in reports if r.content_ok is not None]),
    }


def summarize(reports: list[CaseReport]) -> dict:
    hybrids = [r for r in reports if r.expected == "hybrid"]
    nones = [r for r in reports if r.expected == "none"]
    sql_cases = [r for r in reports if r.sql_original or r.sql_rejections]
    sql_by_class = [r for r in reports if r.expected == "sql"]
    return {
        "classification_correct": f"{sum(r.classified_ok for r in reports)}/{len(reports)}",
        "acceptance_min": ACCEPTANCE_MIN,
        "hybrids_with_both_tools": f"{sum(set(r.sources) == {'sql', 'rag'} for r in hybrids)}/{len(hybrids)}",
        "none_without_tools": f"{sum(not r.tools for r in nones)}/{len(nones)}",
        "classified_before_tools": f"{sum(r.before_tools for r in reports)}/{len(reports)}",
        "classifier_errors": sum(r.got == "(error)" for r in reports),
        "valid_answers": f"{sum(r.valid for r in reports)}/{len(reports)}",
        "sql_content_ok": _ratio([r.content_ok for r in sql_by_class if r.content_ok is not None]),
        "content_ok": _ratio([r.content_ok for r in reports if r.content_ok is not None]),
        "content_ok_by_expected": {
            kind: _ratio([r.content_ok for r in reports
                          if r.expected == kind and r.content_ok is not None])
            for kind in ("sql", "rag", "hybrid", "none")
        },
        "runs_recorded": f"{sum(r.run_id is not None for r in reports)}/{len(reports)}",
        "cases_with_sql_rejected": f"{sum(bool(r.sql_rejections) for r in sql_cases)}/{len(sql_cases)}",
        "seconds_total": round(sum(r.seconds for r in reports), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="archivo JSON donde guardar la evidencia")
    parser.add_argument("--only", help="IDs separados por coma, p. ej. G1,G6")
    parser.add_argument("--db", action="store_true",
                        help="ejecutar el SQL contra la base local y registrar en agent_runs "
                             "(docker compose up -d); evalúa el contenido de los casos SQL")
    parser.add_argument("--rag-mock", action="store_true",
                        help="recuperación sobre el corpus simulado de tests/rag_fixture.py (sin PDFs); "
                             "evalúa el contenido de los casos RAG; no calibra ni mide retrieval real")
    parser.add_argument("--rag-real", action="store_true",
                        help="recuperación de producción: pgvector con los documentos ingestados y la estrategia "
                             "RAG_STRATEGY (re-ranking por defecto); evalúa el contenido de los casos RAG; "
                             "requiere la base y gasta cuota de Gemini")
    parser.add_argument("--bilingual", action="store_true",
                        help="agrega los casos en inglés (B1, B2); no cuentan para el criterio R-2.1")
    args = parser.parse_args()

    selected = {s.strip() for s in args.only.split(",")} if args.only else None
    pool = [*GOLDEN_SET, *(BILINGUAL_SET if args.bilingual else [])]
    cases = [c for c in pool if selected is None or c.id in selected]

    if args.rag_real and args.rag_mock:
        parser.error("--rag-real y --rag-mock son excluyentes")
    agent = build_agent(use_db=args.db, rag_mock=args.rag_mock, rag_real=args.rag_real)
    reports: list[CaseReport] = []
    print(f"modelo: {agent.cfg.llm_model} | api_base={agent.cfg.llm_api_base or '-'} | "
          f"max_steps={agent.cfg.max_steps} | temperature={agent.cfg.temperature}\n")
    for case in cases:
        report = run_case(
            agent, case,
            with_content=content_evaluable(case.expected_classification, args.db, args.rag_mock, args.rag_real),
        )
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

    english_ids = {c.id for c in BILINGUAL_SET}
    golden_reports = [r for r in reports if r.case_id not in english_ids]
    english_reports = [r for r in reports if r.case_id in english_ids]
    summary = summarize(golden_reports)
    if english_reports:
        summary["english"] = summarize_english(english_reports)
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        cfg = agent.cfg
        payload = {
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": cfg.llm_model,
            "api_base": cfg.llm_api_base or None,
            "config": {"max_steps": cfg.max_steps, "temperature": cfg.temperature,
                       "max_sql_attempts": cfg.max_sql_attempts, "api_max_retries": cfg.api_max_retries},
            "backends": {
                "sql": ("PostgreSQL local (rol agent_ro, dev_seed.sql)" if args.db
                        else "FakeConn (validador real)"),
                "rag": (f"producción: pgvector + Gemini, estrategia {cfg.rag_strategy} "
                        f"(umbral de re-ranking {cfg.rerank_threshold}, de coseno {cfg.similarity_threshold})"
                        if args.rag_real
                        else "corpus simulado tests/rag_fixture.py (RagRetriever real, embedder léxico; no "
                             "mide retrieval semántico ni calibra el umbral)" if args.rag_mock
                        else "FakeRetriever (un fragmento fijo)"),
                "content_evaluated_for": [
                    kind for kind in ("sql", "rag", "hybrid", "none")
                    if content_evaluable(kind, args.db, args.rag_mock, args.rag_real)
                ],
            },
            "summary": summary,
            "cases": [r.__dict__ for r in reports],
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nevidencia guardada en {args.out}")

    correct = sum(r.classified_ok for r in golden_reports)
    return 0 if correct >= ACCEPTANCE_MIN or selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
