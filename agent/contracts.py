"""Contratos entre herramientas, orquestador e interfaz (T4.5, T5.2, T7.1).

Son la interfaz con el resto del equipo: se congelan acá y no se duplican en la UI.
Traza a `TP/02-especificacion-tecnica.md` §5.4 y al Art. 4 de la constitución.

Forma de `AgentAnswer.evidence` (D52):
- `sql`: sentencia efectivamente ejecutada (normalizada, R-3.9). `rows`: filas devueltas.
- `chunks`: fragmentos citados, cada uno con al menos `document` y `location`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Vocabulario único de clasificación (D50): el de la spec (`seleccion-de-fuente`). El enum que
# se le pasa al modelo, el contrato y los tests usan exactamente estos valores.
CLASSIFICATIONS = {"sql", "rag", "hybrid", "none"}

# Una respuesta puede declarar la ausencia de información de forma estructural (D52).
ANSWER_KIND_ANSWER = "answer"
ANSWER_KIND_NO_COVERAGE = "no_coverage"

# Respaldo para respuestas que no traen `answer_kind`. El camino principal es el campo
# estructural: una regex sobre prosa libre es frágil.
NO_INFORMATION_PATTERNS = (
    r"no (se )?(encontr|dispon|encuentra)",
    r"no (hay|existe|cuento con) ",
    r"no contiene información",
    r"no dispone de información suficiente",
)

# Eventos de `AgentAnswer.trace`.
TRACE_CLASSIFICATION = "classification"


def normalize_classification(value: object) -> str:
    """El modelo puede responder `"SQL"` o `" rag "`: se normaliza antes de comparar."""
    return str(value).strip().lower()


@dataclass(frozen=True)
class SqlResult:
    sql: str | None            # sentencia efectivamente ejecutada (normalizada, R-3.9)
    rows: list[dict]
    # SQL_NOT_READONLY | TABLE_NOT_ALLOWED | COLUMN_NOT_ALLOWED | FUNCTION_NOT_ALLOWED |
    # QUERY_TOO_COMPLEX | TIMEOUT | EXECUTION_ERROR
    error: str | None
    executed: bool
    attempts: int
    latency_ms: int
    sql_original: str | None = None  # como la produjo el modelo, para la trazabilidad (R-6.4)
    detail: str | None = None        # motivo del rechazo, reportable al usuario (R-5.7)
    truncated: bool = False          # había más filas que el límite (R-3.6, Art. 4)


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
    answer_kind: str = ANSWER_KIND_ANSWER
    # Eventos en orden: la clasificación estructurada y luego cada invocación de herramienta.
    # Permite afirmar "clasificó antes de invocar tools" sin depender de la prosa (D3, D16).
    trace: list[str] = field(default_factory=list)

    @property
    def classified_before_tools(self) -> bool:
        return bool(self.trace) and self.trace[0] == TRACE_CLASSIFICATION

    def as_outcome(self) -> dict:
        """Vista plana para los `check` del golden set: clasificación, SQL, filas y chunks."""
        return {
            "classification": self.classification,
            "sources": list(self.sources),
            "sql": self.evidence.get("sql"),
            "rows": list(self.evidence.get("rows", [])),
            "chunks": list(self.evidence.get("chunks", [])),
            "answer": self.answer,
            "answer_kind": self.answer_kind,
            "classification_emitted_before_tools": self.classified_before_tools,
        }

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
            declares_absence = self.answer_kind == ANSWER_KIND_NO_COVERAGE or any(
                re.search(p, self.answer, re.I) for p in NO_INFORMATION_PATTERNS
            )
            if not declares_absence:
                problems.append("classification=none debe declarar ausencia de información (Art. 4)")
        else:
            if not self.sources:
                problems.append("sources vacío sin declarar ausencia (Art. 4)")
            if not self.evidence:
                problems.append("respuesta con fuente sin evidencia (R-5.3, R-5.4)")

        expected = {"sql": {"sql"}, "rag": {"rag"}, "hybrid": {"sql", "rag"}}
        if self.classification in expected:
            if set(self.sources) != expected[self.classification]:
                problems.append(
                    f"fuente declarada {sorted(self.sources)} no coincide con {self.classification}"
                )
            # Cada fuente declarada exige su propia evidencia: un híbrido con la evidencia de
            # una sola fuente no prueba que se invocaron las dos (R-2.4).
            if "sql" in expected[self.classification] and not self.evidence.get("sql"):
                problems.append("fuente sql sin la sentencia ejecutada en la evidencia (R-3.9)")
            if "rag" in expected[self.classification] and not self.evidence.get("chunks"):
                problems.append("fuente rag sin fragmentos citados en la evidencia (R-5.4)")
        return problems

    def is_valid(self) -> bool:
        return not self.violations()
