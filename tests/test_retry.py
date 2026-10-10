"""Reintento ante 429 (cuota gratuita de la API)."""
from __future__ import annotations

import pytest

from agent.retry import MAX_WAIT_S, call_with_retry, is_rate_limited, retry_delay

QUOTA = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota. "
    "Please retry in 17.99s.'}}"
)


class Quota(Exception):
    code = 429


def flaky(failures: int, exc: Exception):
    state = {"calls": 0}

    def fn():
        state["calls"] += 1
        if state["calls"] <= failures:
            raise exc
        return "ok"

    return fn, state


def test_rate_limit_is_recognized_by_code_and_by_message() -> None:
    assert is_rate_limited(Quota("x"))
    assert is_rate_limited(Exception(QUOTA))
    assert not is_rate_limited(Exception("401 UNAUTHENTICATED"))
    assert not is_rate_limited(ValueError("boom"))


def test_the_delay_follows_the_api_hint_with_a_cap() -> None:
    assert retry_delay(Exception(QUOTA), 0) == pytest.approx(18.99)
    assert retry_delay(Exception("429 RESOURCE_EXHAUSTED retry in 500s"), 0) == MAX_WAIT_S


def test_the_delay_falls_back_to_exponential_backoff() -> None:
    assert [retry_delay(Quota("sin pista"), n) for n in range(3)] == [2.0, 4.0, 8.0]


def test_retries_until_it_succeeds_and_sleeps_between_attempts() -> None:
    fn, state = flaky(2, Quota("quota"))
    waits: list[float] = []
    assert call_with_retry(fn, retries=3, sleep=waits.append) == "ok"
    assert state["calls"] == 3 and len(waits) == 2


def test_gives_up_after_the_configured_retries() -> None:
    fn, state = flaky(10, Quota("quota"))
    with pytest.raises(Quota):
        call_with_retry(fn, retries=2, sleep=lambda s: None)
    assert state["calls"] == 3


def test_non_quota_errors_are_not_retried() -> None:
    fn, state = flaky(1, PermissionError("clave inválida"))
    with pytest.raises(PermissionError):
        call_with_retry(fn, retries=5, sleep=lambda s: None)
    assert state["calls"] == 1


def test_zero_retries_means_a_single_attempt() -> None:
    fn, state = flaky(1, Quota("quota"))
    with pytest.raises(Quota):
        call_with_retry(fn, retries=0, sleep=lambda s: None)
    assert state["calls"] == 1
