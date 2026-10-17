"""Resumen de la medición de `retrieve()` de producción (R-4.11, D100): puro, sin red ni base."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.measure_retrieval import CountingReranker, run, tally


def row(covered: bool, accepted: bool, doc_ok=None, latency=100) -> dict:
    return {"covered": covered, "accepted": accepted, "top_document_ok": doc_ok, "latency_ms": latency}


def test_tally_counts_missed_positives_and_false_positives() -> None:
    rows = [row(True, True, True), row(True, True, False), row(True, False), row(False, False), row(False, True)]
    t = tally(rows)
    assert (t["covered"], t["uncovered"]) == (3, 2)
    assert t["recall"] == pytest.approx(2 / 3, abs=1e-3) and t["missed"] == 1
    assert t["false_positives"] == 1 and t["false_positive_rate"] == 0.5
    assert t["precision"] == pytest.approx(2 / 3, abs=1e-3)
    assert t["top_document_accuracy"] == 0.5     # solo cuentan las cubiertas aceptadas


def test_tally_latency_percentiles() -> None:
    t = tally([row(True, True, latency=ms) for ms in (100, 200, 300, 400, 5000)])
    assert t["latency_ms_median"] == 300 and t["latency_ms_p95"] == 400


def test_tally_of_an_empty_set_does_not_divide_by_zero() -> None:
    t = tally([])
    assert t["recall"] == 0.0 and t["f1"] == 0.0 and t["latency_ms_median"] == 0


def test_run_records_acceptance_and_the_top_document() -> None:
    chunk = SimpleNamespace(document="reglamento_biblioteca.pdf")
    retriever = SimpleNamespace(retrieve=lambda q: SimpleNamespace(chunks=[chunk] if "multa" in q else [], error=None))
    cases = [SimpleNamespace(id="a", question="multa", covered=True, group="g", document="reglamento"),
             SimpleNamespace(id="b", question="wifi", covered=False, group="n", document=None)]
    a, b = run(cases, retriever)
    assert a["accepted"] and a["top_document_ok"] is True
    assert not b["accepted"] and b["top_document"] is None


def test_counting_reranker_counts_calls_and_failures_and_reraises() -> None:
    class Inner:
        def relevances(self, q, items):
            if q == "falla":
                raise RuntimeError("429")
            return [3]

    counting = CountingReranker(Inner())
    assert counting.relevances("ok", []) == [3]
    with pytest.raises(RuntimeError):
        counting.relevances("falla", [])
    assert (counting.calls, counting.failures) == (2, 1)
