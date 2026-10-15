"""Config central: ningún valor de comportamiento hardcodeado (T2.3, D6, D12, D15)."""
from __future__ import annotations

import os

from agent.config import load_config


def test_defaults_are_the_decided_values() -> None:
    c = load_config()
    assert (c.cuatrimestre_start.isoformat(), c.cuatrimestre_end.isoformat()) == ("2026-08-01", "2026-11-30")
    assert c.timezone == "America/Argentina/Buenos_Aires"
    assert c.top_k == 5
    assert c.similarity_threshold == 0.64
    assert c.max_rows == 50
    assert c.statement_timeout_ms == 10000
    assert c.max_sql_attempts == 2
    assert c.max_steps == 6
    assert c.temperature == 0
    assert c.api_timeout_s == 30
    assert c.embedding_dim == 768


def test_timezone_does_not_depend_on_the_system_tz_variable() -> None:
    # D47: `TZ` es del sistema (servidor o contenedor en UTC); la zona del dominio es `APP_TIMEZONE`
    # (R-3.11).
    os.environ["TZ"] = "UTC"
    try:
        assert load_config().timezone == "America/Argentina/Buenos_Aires"
        os.environ["APP_TIMEZONE"] = "America/Montevideo"
        assert load_config().timezone == "America/Montevideo"
    finally:
        os.environ.pop("TZ", None)
        os.environ.pop("APP_TIMEZONE", None)


def test_table_ref_cap_is_configurable() -> None:
    assert load_config().max_table_refs == 8
    os.environ["SQL_MAX_TABLE_REFS"] = "3"
    try:
        assert load_config().max_table_refs == 3
    finally:
        os.environ.pop("SQL_MAX_TABLE_REFS")


def test_env_file_path_is_explicit_and_inside_the_repo() -> None:
    # `find_dotenv()` falla desde stdin o con otro cwd; el path no depende del cwd.
    from agent.config import ENV_FILE

    assert ENV_FILE.name == ".env"
    assert (ENV_FILE.parent / "agent").is_dir()


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
