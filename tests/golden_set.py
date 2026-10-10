"""Golden set como fixtures compartidas (T9.1, D16).

Se define **antes** de implementar el agente, para que los dos integrantes codeen
contra la misma definición de "terminado".

Las afirmaciones van sobre **clasificación, SQL y filas**, nunca sobre la prosa
generada por el modelo. La prosa se valida con la rúbrica manual de 3 criterios
de `TP/05-validacion.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class GoldenCase:
    id: str
    question: str
    expected_classification: str
    check: Callable[[dict], bool]
    note: str = ""


def _min_rows(n: int) -> Callable[[dict], bool]:
    return lambda out: len(out.get("rows", [])) >= n


def _document(name: str) -> Callable[[dict], bool]:
    return lambda out: bool(out.get("chunks")) and out["chunks"][0]["document"] == name


GOLDEN_SET: list[GoldenCase] = [
    # --- SQL (criterio de aprobación 2) ---
    GoldenCase("G1", "¿Qué libros tiene prestados el socio Juan Pérez?", "sql", _min_rows(1),
               "lista de títulos con fecha de préstamo"),
    GoldenCase("G2", "¿Cuáles son los 5 libros más prestados este cuatrimestre?", "sql", _min_rows(1),
               "ranking de 5 títulos con conteo; usa el rango configurado (R-3.11)"),
    GoldenCase("G3", "¿Qué socios tienen préstamos vencidos?", "sql", _min_rows(1),
               "estado por cálculo sobre la vista, no por valor almacenado (R-3.12)"),
    GoldenCase("G4", '¿Cuántos libros de la categoría "Ciencias de la Computación" hay disponibles?', "sql",
               lambda out: any(r.get("count", 0) > 0 for r in out.get("rows", [])), "conteo de ejemplares"),
    GoldenCase("G5", "¿Qué autor tiene más libros publicados por la editorial X?", "sql", _min_rows(1),
               "autor + cantidad"),

    # --- RAG (criterio de aprobación 3) ---
    GoldenCase("G6", "¿Cuántos días tengo para devolver un libro antes de que me multen?", "rag",
               _document("reglamento_biblioteca.pdf"), "plazo exacto citado"),
    GoldenCase("G7", '¿De qué trata el libro "X"?', "rag", _document("resenas.md"), "sinopsis citada"),
    GoldenCase("G8", "¿Cómo renuevo un préstamo desde el sistema?", "rag",
               _document("manual_uso_sistema.pdf"), "pasos del manual"),
    GoldenCase("G9", "¿Cuál es el horario de la biblioteca?", "rag",
               _document("reglamento_biblioteca.pdf"), "horario citado"),

    # --- Híbridos (R-2.4) ---
    GoldenCase("G10", "Juan Pérez tiene un libro prestado hace 20 días, ¿le corresponde multa según el reglamento?",
               "hybrid", lambda out: {"sql", "rag"} <= set(out.get("sources", [])), "fecha + norma + conclusión"),
    GoldenCase("G11", "¿El socio con más préstamos puede renovar según el reglamento?", "hybrid",
               lambda out: {"sql", "rag"} <= set(out.get("sources", [])), "socio top + límite"),
    GoldenCase("G12", "¿Un docente tiene un plazo distinto que un alumno para el libro más prestado?", "hybrid",
               lambda out: {"sql", "rag"} <= set(out.get("sources", [])), "tipo de socio + norma"),

    # --- No cobertura (R-2.5) ---
    GoldenCase("G13", "¿Cuál es el precio del libro X?", "none",
               lambda out: not out.get("sources"), "declara ausencia de información (Art. 4)"),
]

# Pruebas de retrieval (R-4.4, R-4.6)
RETRIEVAL_TESTS: list[GoldenCase] = [
    GoldenCase("R1", "plazo de devolución y multas", "rag", _document("reglamento_biblioteca.pdf")),
    GoldenCase("R2", "sinopsis del libro X", "rag", _document("resenas.md")),
    GoldenCase("R3", "pasos para renovar un préstamo", "rag", _document("manual_uso_sistema.pdf")),
    GoldenCase("R4", "precio del libro X", "none", lambda out: not out.get("chunks"),
               "similitud máxima < umbral → reporte de no-relevancia"),
]

ACCENT = 11  # ≥ 11/13 (R-2.1)
