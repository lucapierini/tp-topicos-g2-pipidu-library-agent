"""El corpus simulado responde a las preguntas del golden set (sin PDFs ni red).

No prueba retrieval semántico: prueba que el *mock* que usa `scripts/measure_golden.py --rag-mock`
devuelve lo que cada caso espera, para que una corrida con modelo real mida al agente y no al mock.
"""
from __future__ import annotations

import pytest

from agent.config import load_config
from agent.errors import NO_RELEVANT_RESULTS
from tests.golden_set import GOLDEN_SET, RETRIEVAL_TESTS
from tests.rag_fixture import LexicalEmbedder, build_mock_retriever

RAG_CASES = [c for c in GOLDEN_SET if c.expected_classification == "rag"]
HYBRID_CASES = [c for c in GOLDEN_SET if c.expected_classification == "hybrid"]


@pytest.fixture(scope="module")
def retriever():
    return build_mock_retriever(load_config())


@pytest.mark.parametrize("case", RAG_CASES, ids=lambda c: c.id)
def test_each_rag_case_gets_its_expected_document_first(retriever, case) -> None:
    result = retriever.retrieve(case.question)

    assert result.error is None
    assert case.check({"chunks": [{"document": c.document} for c in result.chunks]})


@pytest.mark.parametrize("case", [c for c in RETRIEVAL_TESTS if c.expected_classification == "rag"],
                         ids=lambda c: c.id)
def test_retrieval_cases_get_their_expected_document_first(retriever, case) -> None:
    result = retriever.retrieve(case.question)

    assert result.error is None
    assert case.check({"chunks": [{"document": c.document} for c in result.chunks]})


def test_a_question_without_coverage_reports_no_relevant_results(retriever) -> None:
    uncovered = next(c for c in RETRIEVAL_TESTS if c.id == "R4")

    result = retriever.retrieve(uncovered.question)

    assert result.error == NO_RELEVANT_RESULTS
    assert result.chunks == []


def test_the_none_case_has_no_chunk_to_cite(retriever) -> None:
    none_case = next(c for c in GOLDEN_SET if c.expected_classification == "none")

    assert retriever.retrieve(none_case.question).chunks == []


@pytest.mark.parametrize("case", HYBRID_CASES, ids=lambda c: c.id)
def test_the_norm_side_of_each_hybrid_case_is_found(retriever, case) -> None:
    """El agente le pasa a la tool la parte normativa; con la pregunta entera alcanza para el mock."""
    assert retriever.retrieve(case.question).chunks


def test_every_chunk_declares_document_and_location(retriever) -> None:
    result = retriever.retrieve("plazo de devolución y multas")

    assert result.chunks
    assert all(c.document and c.location and c.content_hash.startswith("mock:") for c in result.chunks)


def test_the_embedder_is_deterministic() -> None:
    embedder = LexicalEmbedder()

    first = embedder.embed_query("horario de la biblioteca")

    assert first == embedder.embed_query("horario de la biblioteca")
    assert any(first)


# --- el mock dentro del orquestador: la evidencia que mide `measure_golden.py --rag-mock` ---


@pytest.mark.parametrize("case", RAG_CASES, ids=lambda c: c.id)
def test_the_orchestrator_cites_the_mock_chunk_and_the_golden_check_passes(retriever, case) -> None:
    from agent.agent import LibraryAgent
    from tests.fakes import FakeClassifier, ScriptedRunner

    agent = LibraryAgent(
        classifier=FakeClassifier("rag"),
        sql_backend=None,
        retriever=retriever,
        runner=ScriptedRunner([("retrieve_documents", case.question)], "Según el documento citado."),
    )

    answer = agent.answer(case.question)

    assert answer.sources == ["rag"] and answer.is_valid()
    assert case.check(answer.as_outcome())


def test_content_is_only_evaluated_where_the_sources_are_not_fake() -> None:
    from scripts.measure_golden import content_evaluable

    assert content_evaluable("sql", use_db=True, rag_mock=False)
    assert not content_evaluable("sql", use_db=False, rag_mock=True)
    assert content_evaluable("rag", use_db=False, rag_mock=True)
    assert not content_evaluable("rag", use_db=True, rag_mock=False)
    assert not content_evaluable("hybrid", use_db=True, rag_mock=False)
    assert content_evaluable("hybrid", use_db=True, rag_mock=True)
    assert content_evaluable("none", use_db=False, rag_mock=False)
