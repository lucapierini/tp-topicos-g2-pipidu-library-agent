"""El set de validación es verificable sin red ni base y no se solapa con el de calibración (R-4.10, D99)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.calibration_set import CALIBRATION_SET
from tests.golden_set import BILINGUAL_SET, CALIBRATION_EXTRA, GOLDEN_SET, RETRIEVAL_TESTS
from tests.validation_set import NEGATIVES, POSITIVES, VALIDATION_SET

DOCS = Path(__file__).resolve().parents[1] / "rag" / "documents"
CORPUS = {md.stem: md.read_text(encoding="utf-8").casefold() for md in sorted(DOCS.glob("*.md"))}


def test_the_set_is_big_enough_to_validate() -> None:
    assert len(POSITIVES) >= 25 and len(NEGATIVES) >= 25 and len(VALIDATION_SET) >= 50


def test_ids_are_unique_and_do_not_collide_with_calibration() -> None:
    ids = [c.id for c in VALIDATION_SET]
    assert len(ids) == len(set(ids))
    assert not set(ids) & {c.id for c in CALIBRATION_SET}


def test_no_question_is_shared_with_the_calibration_or_golden_sets() -> None:
    """Si una pregunta estuviera en los dos sets, la validación dejaría de ser fuera de muestra."""
    seen = {c.question.casefold() for c in CALIBRATION_SET}
    seen |= {c.question.casefold() for c in [*GOLDEN_SET, *BILINGUAL_SET, *RETRIEVAL_TESTS, *CALIBRATION_EXTRA]}
    repeated = [c.id for c in VALIDATION_SET if c.question.casefold() in seen]
    assert not repeated, f"preguntas ya usadas para calibrar: {repeated}"
    questions = [c.question.casefold() for c in VALIDATION_SET]
    assert len(questions) == len(set(questions))


def test_it_exercises_every_kind_of_consulta() -> None:
    groups = {c.group for c in VALIDATION_SET}
    assert {"reglamento", "politicas", "en", "dominio_dificil", "libro_sin_resena", "ajeno", "en_negativo"} <= groups
    assert {c.document for c in POSITIVES} == set(CORPUS), "falta cubrir algún documento"


@pytest.mark.parametrize("case", POSITIVES, ids=lambda c: c.id)
def test_a_positive_is_answered_by_its_document(case) -> None:
    assert case.term.casefold() in CORPUS[case.document], f"{case.id}: «{case.term}» no está en {case.document}.md"


@pytest.mark.parametrize("case", NEGATIVES, ids=lambda c: c.id)
def test_a_negative_is_not_answered_by_any_document(case) -> None:
    found = [name for name, text in CORPUS.items() if case.term.casefold() in text]
    assert not found, f"{case.id}: «{case.term}» aparece en {found}: ya no es un negativo"
