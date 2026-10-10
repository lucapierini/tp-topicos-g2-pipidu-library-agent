"""Config central: ningún valor de comportamiento hardcodeado (T2.3, D6, D12, D15)."""
from __future__ import annotations

import os

from agent.config import load_config


def test_defaults_are_the_decided_values() -> None:
    c = load_config()
    assert (c.cuatrimestre_start.isoformat(), c.cuatrimestre_end.isoformat()) == ("2026-08-01", "2026-11-30")
    assert c.timezone == "America/Argentina/Buenos_Aires"
    assert c.top_k == 5
    assert c.similarity_threshold == 0.35
    assert c.max_rows == 50
    assert c.statement_timeout_ms == 10000
    assert c.max_sql_attempts == 2
    assert c.max_steps == 6
    assert c.temperature == 0
    assert c.api_timeout_s == 30
    assert c.embedding_dim == 768


def test_values_are_overridable_by_env() -> None:
    os.environ["RAG_SIMILARITY_THRESHOLD"] = "0.42"
    os.environ["SQL_MAX_ATTEMPTS"] = "3"
    c = load_config()
    assert c.similarity_threshold == 0.42
    assert c.max_sql_attempts == 3
    os.environ.pop("RAG_SIMILARITY_THRESHOLD")
    os.environ.pop("SQL_MAX_ATTEMPTS")


def test_no_secrets_in_config() -> None:
    # Art. 9: las claves se leen de entorno, nunca del código.
    import inspect
    import agent.config as cfg
    src = inspect.getsource(cfg)
    assert "API_KEY" not in src
    assert "password" not in src.lower()
