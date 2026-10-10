"""Prompts (T6.1): el esquema se genera desde la whitelist y los ejemplos pasan el validador."""
from __future__ import annotations

import re

import pytest

from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_TABLES
from agent.contracts import CLASSIFICATIONS
from agent.prompts import render_classifier_prompt, render_system_prompt, schema_description
from agent.sql_validator import validate_sql


def system_prompt(label="hybrid", tools=("execute_sql", "retrieve_documents")) -> str:
    return render_system_prompt(load_config(), classification=label, tools=list(tools))


def test_schema_lists_exactly_the_whitelisted_columns() -> None:
    # Si la whitelist cambia, el prompt cambia con ella: el modelo nunca ve una columna rechazable.
    description = schema_description()
    for table, columns in ALLOWED_TABLES.items():
        line = next(ln for ln in description.splitlines() if ln.startswith(f"- {table}("))
        listed = set(re.search(r"\(([^)]*)\)", line).group(1).split(", "))
        assert listed == columns, table


def test_prestamos_does_not_advertise_a_stored_state_column() -> None:
    line = next(ln for ln in schema_description().splitlines() if ln.startswith("- prestamos("))
    assert "estado" not in line
    assert "prestamos_estado" in system_prompt()


def test_no_unresolved_placeholders_remain() -> None:
    rendered = system_prompt()
    assert not re.search(r"\$[a-z_]+", rendered), re.findall(r"\$[a-z_]+", rendered)


def test_configured_values_are_injected() -> None:
    cfg = load_config()
    rendered = system_prompt("sql", ("execute_sql",))
    assert cfg.cuatrimestre_start.isoformat() in rendered and cfg.cuatrimestre_end.isoformat() in rendered
    assert cfg.timezone in rendered
    assert str(cfg.max_rows) in rendered and str(cfg.max_sql_attempts) in rendered
    assert "**sql**" in rendered


def test_the_prompt_forbids_what_the_validator_forbids() -> None:
    rendered = system_prompt().lower()
    for fragment in ("select", "recursive", "prestamos_estado", "no_relevant_results"):
        assert fragment in rendered


def _examples(rendered: str) -> list[str]:
    return [m for m in re.findall(r"`(SELECT [^`]+)`", rendered)]


def test_the_few_shot_examples_pass_the_static_validator() -> None:
    # Un ejemplo que el validador rechaza le enseña al modelo a gastar sus 2 intentos.
    examples = _examples(system_prompt())
    assert len(examples) >= 8
    for sql in examples:
        result = validate_sql(sql)
        assert result.ok, f"{result.error} ({result.detail}): {sql}"


def test_the_period_example_uses_the_configured_range() -> None:
    cfg = load_config()
    ranked = next(e for e in _examples(system_prompt()) if "BETWEEN" in e)
    assert cfg.cuatrimestre_start.isoformat() in ranked and cfg.cuatrimestre_end.isoformat() in ranked


@pytest.mark.parametrize("label", sorted(CLASSIFICATIONS))
def test_the_classifier_prompt_defines_every_label(label: str) -> None:
    assert f"`{label}`" in render_classifier_prompt()


def test_the_classifier_prompt_asks_for_the_structured_fields() -> None:
    prompt = render_classifier_prompt()
    assert "classification" in prompt and "language" in prompt
