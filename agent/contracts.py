"""Contratos entre herramientas, orquestador e interfaz (T4.5, T5.2, T7.1).

Son la interfaz con el resto del equipo: se congelan acá y no se duplican en la UI.
Traza a `TP/02-especificacion-tecnica.md` §5.4 y al Art. 4 de la constitución.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CLASSIFICATIONS = {"sql", "rag", "hybrid", "none"}

# El Art. 4 exige declarar la ausencia de información de forma explícita.
# Estas son las frases que el prompt del sistema produce; el test las verifica.
NO_INFORMATION_PATTERNS = (
    r"no (se )?(encontr|dispon|encuentra)",
    r"no contiene información",
    r"no dispone de información suficiente",
)


@dataclass(frozen=True)
class SqlResult:
    sql: str | None            # sentencia efectivamente ejecutada (normalizada, R-3.9)
    rows: list[dict]
    error: str | None          # SQL_NOT_READONLY | TABLE_NOT_ALLOWED | COLUMN_NOT_ALLOWED | FUNCTION_NOT_ALLOWED | TIMEOUT
    executed: bool
    attempts: int
    latency_ms: int
    sql_original: str | None = None  # como la produjo el modelo, para la trazabilidad (R-6.4)


@dataclass(frozen=True)
class Chunk:
    id: int
    document: str
    location: str
    text: str
    content_hash: str
    similarity: float


@dataclass(frozen=True)
class RagResult:
    chunks: list[Chunk]
    error: str | None
    latency_ms: int


@dataclass(frozen=True)
class AgentAnswer:
    question: str
    classification: str
    sources: list[str]
    answer: str
    evidence: dict = field(default_factory=dict)
    run_id: int | None = None

    def violations(self) -> list[str]:
        problems: list[str] = []
        if self.classification not in CLASSIFICATIONS:
            problems.append(f"classificación inválida: {self.classification!r}")
        if not self.question.strip():
            problems.append("consulta vacía (R-1.2)")
        if not self.answer.strip():
            problems.append("respuesta vacía")

        if self.classification == "none":
            if self.sources:
                problems.append("classification=none no puede declarar fuentes")
            if not any(re.search(p, self.answer, re.I) for p in NO_INFORMATION_PATTERNS):
                problems.append("classification=none debe declarar ausencia de información (Art. 4)")
        else:
            if not self.sources:
                problems.append("sources vacío sin declarar ausencia (Art. 4)")
            if not self.evidence:
                problems.append("respuesta con fuente sin evidencia (R-5.3, R-5.4)")

        expected = {"sql": {"sql"}, "rag": {"rag"}, "hybrid": {"sql", "rag"}}
        if self.classification in expected and set(self.sources) != expected[self.classification]:
            problems.append(
                f"fuente declarada {sorted(self.sources)} no coincide con {self.classification}"
            )
        return problems

    def is_valid(self) -> bool:
        return not self.violations()
