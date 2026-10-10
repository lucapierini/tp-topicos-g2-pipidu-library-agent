"""Golden set (T9.1, R-2.1, D16).

Dos niveles:
1. Forma del set: se puede verificar hoy, sin agente.
2. Exactitud de clasificación: requiere el agente (T6.3) y una API key. Se marca
   `llm` y se salta hasta que exista.
"""
from __future__ import annotations

import os
from collections import Counter

import pytest

from tests.golden_set import ACCENT, GOLDEN_SET, RETRIEVAL_TESTS


def test_golden_set_shape() -> None:
    assert len(GOLDEN_SET) == 13
    counts = Counter(c.expected_classification for c in GOLDEN_SET)
    assert counts["sql"] >= 5, "criterio de aprobación 2: mínimo 5 casos SQL"
    assert counts["rag"] >= 4, "criterio de aprobación 3: mínimo 4 casos RAG"
    assert counts["hybrid"] == 3, "R-2.4: 3 casos híbridos"
    assert counts["none"] == 1, "R-2.5: 1 caso de no cobertura"
    assert len({c.id for c in GOLDEN_SET}) == 13, "IDs duplicados"


def test_retrieval_tests_shape() -> None:
    assert len(RETRIEVAL_TESTS) == 4


@pytest.mark.llm
def test_classification_accuracy() -> None:
    agent = pytest.importorskip("agent.agent", reason="T6.3 todavía no implementado")
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("sin GEMINI_API_KEY")

    correct = 0
    for case in GOLDEN_SET:
        out = agent.answer(case.question)  # dict con classification, sources, rows, chunks
        assert out.get("classification") in {"sql", "rag", "hybrid", "none"}
        # D3 / R-2.7: la clasificación se emite antes de invocar herramientas.
        assert out.get("classification_emitted_before_tools"), f"{case.id}: clasificación tardía"
        if out.get("classification") == case.expected_classification and case.check(out):
            correct += 1

    assert correct >= ACCENT, f"{correct}/13, mínimo {ACCENT}"


@pytest.mark.llm
def test_hybrid_cases_invoke_both_tools() -> None:
    agent = pytest.importorskip("agent.agent", reason="T6.3 todavía no implementado")
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("sin GEMINI_API_KEY")
    for case in [c for c in GOLDEN_SET if c.expected_classification == "hybrid"]:
        out = agent.answer(case.question)
        assert {"sql", "rag"} <= set(out.get("sources", [])), f"{case.id}: no invocó ambas tools"


@pytest.mark.llm
def test_no_coverage_case_does_not_invent() -> None:
    agent = pytest.importorskip("agent.agent", reason="T6.3 todavía no implementado")
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("sin GEMINI_API_KEY")
    out = agent.answer("¿Cuál es el precio del libro X?")
    assert out.get("classification") == "none"
    assert not out.get("rows") and not out.get("chunks")
    assert out.get("answer", "").lower().startswith(("no ", "la base no"))
