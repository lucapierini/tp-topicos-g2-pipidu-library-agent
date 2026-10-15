"""El set de calibración es verificable sin red ni base (R-4.8, D97).

Si estos tests fallan, el umbral se estaría midiendo con etiquetas incorrectas: un "positivo" que el documento
ya no contesta, o un "negativo" que un documento nuevo sí cubre.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from tests.calibration_set import CALIBRATION_SET, NEGATIVES, POSITIVES
from tests.golden_set import BILINGUAL_SET, CALIBRATION_EXTRA, GOLDEN_SET, RETRIEVAL_TESTS

DOCS = Path(__file__).resolve().parents[1] / "rag" / "documents"
CORPUS = {md.stem: md.read_text(encoding="utf-8").casefold() for md in sorted(DOCS.glob("*.md"))}

POSITIVE_GROUPS = {"reglamento", "politicas", "resena_cien_anios", "resena_clean_code", "resena_tolkien",
                   "resena_empyrean", "en"}
NEGATIVE_GROUPS = {"dominio_dificil", "libro_sin_resena", "ajeno", "en_negativo"}


def test_the_set_is_big_enough_to_calibrate() -> None:
    assert 50 <= len(CALIBRATION_SET) <= 120
    assert len(POSITIVES) >= 50 and len(NEGATIVES) >= 30


def test_ids_and_questions_are_unique() -> None:
    ids = [c.id for c in CALIBRATION_SET]
    questions = [c.question.casefold() for c in CALIBRATION_SET]
    assert len(ids) == len(set(ids))
    assert len(questions) == len(set(questions))


def test_labels_and_groups_are_consistent() -> None:
    for case in POSITIVES:
        assert case.covered and case.group in POSITIVE_GROUPS and case.document, case.id
    for case in NEGATIVES:
        assert not case.covered and case.group in NEGATIVE_GROUPS and case.document is None, case.id


def test_every_group_has_enough_cases() -> None:
    counts = Counter(c.group for c in CALIBRATION_SET)
    for group in POSITIVE_GROUPS | NEGATIVE_GROUPS:
        assert counts[group] >= 5, f"el grupo {group} tiene {counts[group]} casos"
    assert counts["dominio_dificil"] >= 15  # los negativos que más confunden al umbral


def test_the_set_covers_every_ingested_document() -> None:
    assert {c.document for c in POSITIVES} == set(CORPUS), "falta cubrir algún documento (o sobra uno)"


@pytest.mark.parametrize("case", POSITIVES, ids=lambda c: c.id)
def test_a_positive_is_answered_by_its_document(case) -> None:
    assert case.document in CORPUS, f"{case.document} no existe en rag/documents/"
    assert case.term.casefold() in CORPUS[case.document], (
        f"{case.id}: «{case.term}» no está en {case.document}.md: la pregunta ya no está cubierta"
    )


@pytest.mark.parametrize("case", NEGATIVES, ids=lambda c: c.id)
def test_a_negative_is_not_answered_by_any_document(case) -> None:
    found = [name for name, text in CORPUS.items() if case.term.casefold() in text]
    assert not found, f"{case.id}: «{case.term}» aparece en {found}: ya no es un negativo"


def test_the_set_adds_to_the_golden_set_without_repeating_it() -> None:
    golden = {c.question.casefold() for c in [*GOLDEN_SET, *BILINGUAL_SET, *RETRIEVAL_TESTS, *CALIBRATION_EXTRA]}
    repeated = [c.id for c in CALIBRATION_SET if c.question.casefold() in golden]
    assert not repeated, f"preguntas ya presentes en el golden set: {repeated}"
