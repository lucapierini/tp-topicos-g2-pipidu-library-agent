"""Golden set (T9.1, R-2.1, D16).

Dos niveles:
1. Forma del set y de sus `check`: se verifica hoy, sin agente.
2. Exactitud de clasificación: requiere el agente (T6.3) y una API key. Se marca
   `llm` y se salta hasta que exista.

Contrato del orquestador (D52): `agent.agent.answer(question) -> AgentAnswer`. Los `check` del
golden set se evalúan sobre `AgentAnswer.as_outcome()`: clasificación, SQL, filas y chunks.
Nunca sobre la prosa (D16).
"""
from __future__ import annotations

import os
from collections import Counter

import pytest

from agent.contracts import CLASSIFICATIONS, normalize_classification
from tests.golden_set import ACCEPTANCE_MIN, GOLDEN_SET, RETRIEVAL_TESTS, SEED_ENTITIES


def test_golden_set_shape() -> None:
    assert len(GOLDEN_SET) == 13
    counts = Counter(c.expected_classification for c in GOLDEN_SET)
    assert counts["sql"] >= 5, "criterio de aprobación 2: mínimo 5 casos SQL"
    assert counts["rag"] >= 4, "criterio de aprobación 3: mínimo 4 casos RAG"
    assert counts["hybrid"] == 3, "R-2.4: 3 casos híbridos"
    assert counts["none"] == 1, "R-2.5: 1 caso de no cobertura"
    assert len({c.id for c in GOLDEN_SET}) == 13, "IDs duplicados"
    assert {c.expected_classification for c in GOLDEN_SET} <= CLASSIFICATIONS


def test_retrieval_tests_shape() -> None:
    assert len(RETRIEVAL_TESTS) == 4


def test_no_placeholders_left_in_questions() -> None:
    # Las preguntas con `X` literal no tienen respuesta en ninguna base.
    for case in GOLDEN_SET + RETRIEVAL_TESTS:
        assert " X" not in case.question and '"X"' not in case.question, case.id


def test_seed_entities_are_referenced_by_the_questions() -> None:
    # Si cambia una entidad del seed, la pregunta que la usa cambia con ella.
    text = " ".join(c.question for c in GOLDEN_SET)
    assert SEED_ENTITIES["categoria"] in text
    assert SEED_ENTITIES["editorial"] in text
    assert SEED_ENTITIES["libro_con_resena"] in text


def _case(case_id: str):
    return next(c for c in GOLDEN_SET + RETRIEVAL_TESTS if c.id == case_id)


def test_aggregate_check_does_not_depend_on_the_alias() -> None:
    # El modelo puede llamar `total`, `cantidad` o `count` a la columna: el check no debe cambiar.
    g4 = _case("G4").check
    assert g4({"rows": [{"count": 7}]})
    assert g4({"rows": [{"total_disponibles": 7}]})
    assert not g4({"rows": [{"count": 0}]})
    assert not g4({"rows": []})
    assert not g4({"rows": [{"titulo": "x"}]})


def test_document_check_matches_by_prefix() -> None:
    g7 = _case("G7").check
    assert g7({"chunks": [{"document": "resenas_libro_2.pdf"}]})
    assert not g7({"chunks": [{"document": "reglamento_biblioteca.pdf"}]})
    assert not g7({"chunks": []})


def test_hybrid_check_requires_evidence_from_both_sources() -> None:
    g10 = _case("G10").check
    both = {"sources": ["sql", "rag"], "rows": [{"id": 1}], "chunks": [{"document": "r.pdf"}]}
    assert g10(both)
    assert not g10({**both, "chunks": []}), "declarar la fuente sin evidencia no alcanza"
    assert not g10({**both, "sources": ["sql"]})


def test_none_check_requires_no_sources_rows_or_chunks() -> None:
    g13 = _case("G13").check
    assert g13({"sources": [], "rows": [], "chunks": []})
    assert not g13({"sources": ["sql"], "rows": [], "chunks": []})
    assert not g13({"sources": [], "rows": [{"precio": 1}], "chunks": []})


def test_classification_is_normalized_before_comparing() -> None:
    # El modelo puede responder "SQL" en vez de "sql" (enum case-sensitive).
    assert normalize_classification(" SQL ") == "sql"
    assert normalize_classification("Hybrid") == "hybrid"


# --- requieren el agente (T6.3) ---


def _agent_or_skip():
    agent = pytest.importorskip("agent.agent", reason="T6.3 todavía no implementado")
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("sin GEMINI_API_KEY")
    return agent


@pytest.mark.llm
def test_classification_accuracy() -> None:
    agent = _agent_or_skip()
    correct = 0
    for case in GOLDEN_SET:
        answer = agent.answer(case.question)
        outcome = answer.as_outcome()
        assert normalize_classification(outcome["classification"]) in CLASSIFICATIONS
        # D3 / R-2.7: la clasificación se emite antes de invocar herramientas.
        assert answer.classified_before_tools, f"{case.id}: clasificación tardía (trace={answer.trace})"
        if outcome["classification"] == case.expected_classification and case.check(outcome):
            correct += 1

    assert correct >= ACCEPTANCE_MIN, f"{correct}/13, mínimo {ACCEPTANCE_MIN}"


@pytest.mark.llm
def test_hybrid_cases_invoke_both_tools() -> None:
    agent = _agent_or_skip()
    for case in [c for c in GOLDEN_SET if c.expected_classification == "hybrid"]:
        outcome = agent.answer(case.question).as_outcome()
        assert case.check(outcome), f"{case.id}: no invocó ambas tools o falta evidencia"


@pytest.mark.llm
def test_no_coverage_case_does_not_invent() -> None:
    # D16: se afirma sobre estructura (clasificación, fuentes, tipo de respuesta), no sobre prosa.
    agent = _agent_or_skip()
    case = _case("G13")
    answer = agent.answer(case.question)
    outcome = answer.as_outcome()
    assert outcome["classification"] == "none"
    assert case.check(outcome)
    assert answer.answer_kind == "no_coverage"
    assert answer.is_valid(), answer.violations()
