"""Adaptadores entre las herramientas del dominio y `smolagents` (T6.2).

El orquestador describe cada herramienta como un `ToolSpec` (nombre, descripción, parámetro y una
función `str -> str`), sin depender de `smolagents`. Este módulo es el único que importa la
librería, y solo se carga cuando se construye el agente real: los tests del orquestador corren
con un runner falso y no lo necesitan (Art. 6).
"""
from __future__ import annotations

from smolagents import Tool

from agent.contracts import ToolSpec


class _SingleStringTool(Tool):
    """Base: una herramienta con un único argumento de texto que devuelve texto."""

    output_type = "string"

    def __init__(self, spec: ToolSpec) -> None:
        self._spec = spec
        self.name = spec.name
        self.description = spec.description
        self.inputs = {spec.parameter: {"type": "string", "description": spec.parameter_description}}
        super().__init__()


class SqlTool(_SingleStringTool):
    def forward(self, sql: str) -> str:  # noqa: D102 - la firma debe coincidir con `inputs`
        return self._spec.fn(sql)


class QueryTool(_SingleStringTool):
    def forward(self, query: str) -> str:  # noqa: D102
        return self._spec.fn(query)


_ADAPTERS = {"sql": SqlTool, "query": QueryTool}


def to_smolagents_tools(specs: list[ToolSpec]) -> list[Tool]:
    try:
        return [_ADAPTERS[spec.parameter](spec) for spec in specs]
    except KeyError as exc:
        raise ValueError(f"no hay adaptador para el parámetro {exc.args[0]!r}") from exc
