"""Métricas de la calibración del umbral (R-4.8, D97): puras, sin red ni base.

Los valores esperados se calculan a mano sobre conjuntos chicos.
"""
from __future__ import annotations

import pytest

from scripts.calibrate_threshold import (
    auc,
    build_cases,
    confusion,
    group_stats,
    pick_thresholds,
    propose_threshold,
    sweep,
)

POS = [0.80, 0.75, 0.70, 0.66]   # consultas cubiertas
NEG = [0.64, 0.60, 0.55]         # sin cobertura


def test_confusion_counts_at_a_threshold() -> None:
    c = confusion(POS, NEG, 0.65)
    assert (c["tp"], c["fn"], c["fp"], c["tn"]) == (4, 0, 0, 3)
    assert c["recall"] == 1.0 and c["specificity"] == 1.0 and c["f1"] == 1.0


def test_a_low_threshold_lets_negatives_through_and_a_high_one_rejects_positives() -> None:
    low = confusion(POS, NEG, 0.50)
    assert low["fp"] == 3 and low["recall"] == 1.0
    high = confusion(POS, NEG, 0.78)
    assert high["tp"] == 1 and high["fn"] == 3 and high["recall"] == 0.25


def test_the_threshold_is_inclusive() -> None:
    assert confusion([0.64], [], 0.64)["tp"] == 1


def test_f1_is_the_harmonic_mean_of_precision_and_recall() -> None:
    c = confusion([0.9, 0.8, 0.5, 0.4], [0.7, 0.3], 0.6)  # tp=2 fn=2 fp=1
    assert c["precision"] == pytest.approx(2 / 3, abs=1e-3) and c["recall"] == 0.5
    assert c["f1"] == pytest.approx(2 * (2 / 3) * 0.5 / ((2 / 3) + 0.5), abs=1e-3)


def test_auc_is_one_when_the_groups_do_not_overlap_and_a_half_when_identical() -> None:
    assert auc(POS, NEG) == 1.0
    assert auc([0.5, 0.6], [0.5, 0.6]) == 0.5
    assert auc([0.5], [0.9]) == 0.0
    assert auc([], NEG) is None


def test_auc_counts_partial_overlap() -> None:
    # 2 positivos x 2 negativos: gana 3 de 4 pares
    assert auc([0.9, 0.6], [0.7, 0.5]) == 0.75


def test_sweep_covers_the_range_and_is_monotonic_in_recall() -> None:
    table = sweep(POS, NEG)
    assert table[0]["threshold"] == 0.5 and table[-1]["threshold"] == 0.9
    recalls = [r["recall"] for r in table]
    assert recalls == sorted(recalls, reverse=True)


def test_pick_thresholds_on_separable_data_finds_a_threshold_between_the_groups() -> None:
    picks = pick_thresholds(sweep(POS, NEG))
    assert 0.64 < picks["best_f1"]["threshold"] <= 0.66
    assert picks["best_f1"]["fp"] == 0 and picks["best_f1"]["recall"] == 1.0
    assert picks["no_false_positive"]["recall"] == 1.0


def test_pick_thresholds_on_overlapping_data_shows_the_trade_off() -> None:
    pos = [0.80, 0.75, 0.70, 0.646]
    neg = [0.649, 0.60]  # el mejor negativo supera al peor positivo (el caso real de D87)
    picks = pick_thresholds(sweep(pos, neg), min_recall=1.0)
    assert picks["min_recall"]["recall"] == 1.0 and picks["min_recall"]["fp"] >= 1
    assert picks["no_false_positive"]["recall"] < 1.0


def test_min_recall_picks_the_highest_threshold_that_keeps_it() -> None:
    picks = pick_thresholds(sweep([0.9, 0.8, 0.7, 0.6], [0.5]), min_recall=0.75)
    assert picks["min_recall"]["threshold"] == 0.7 and picks["min_recall"]["recall"] == 0.75


def test_pick_thresholds_without_data_is_empty() -> None:
    assert pick_thresholds([]) == {}


def test_propose_threshold_keeps_the_original_midpoint_rule() -> None:
    assert propose_threshold([0.8, 0.7], [0.6, 0.5])["proposed"] == 0.65
    assert propose_threshold([0.7, 0.6], [0.65])["separable"] is False


def test_group_stats_summarises_each_group() -> None:
    rows = [{"group": "a", "max_similarity": 0.6}, {"group": "a", "max_similarity": 0.8},
            {"group": "b", "max_similarity": 0.5}]
    stats = group_stats(rows)
    assert stats["a"] == {"n": 2, "min": 0.6, "median": 0.7, "max": 0.8}
    assert stats["b"]["n"] == 1


def test_build_cases_merges_both_sets_without_repeating_questions() -> None:
    cases = build_cases()
    questions = [c.question.casefold() for c in cases]
    assert len(questions) == len(set(questions))
    assert len(cases) >= 100
    covered = [c for c in cases if c.covered]
    assert len(covered) > 50 and len(cases) - len(covered) >= 40
