"""Golden set como fixtures compartidas (T9.1, D16).

Se define **antes** de implementar el agente, para que los dos integrantes codeen
contra la misma definición de "terminado".

Las afirmaciones van sobre **clasificación, SQL y filas**, nunca sobre la prosa
generada por el modelo. La prosa se valida con la rúbrica manual de 3 criterios
de `TP/05-validacion.md`.

Los `check` reciben `AgentAnswer.as_outcome()`: un dict con `classification`, `sources`,
`sql`, `rows`, `chunks` y `classification_emitted_before_tools`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# Entidades que el seed (`scripts/seed_data.py`, T2.x) debe contener para que las preguntas
# tengan respuesta. Eran placeholders literales (`X`, "el libro X") que ninguna base satisface.
# `tests/test_golden_seed.py` verifica que existan cuando haya base.
SEED_ENTITIES = {
    "socio_nombre": "Juan",
    "socio_apellido": "Pérez",
    "categoria": "Ciencias de la Computación",
    "editorial": "Sudamericana",
    "libro_con_resena": "Cien años de soledad",   # tiene reseña en `resenas_libro_*.pdf`
    "libro_sin_precio": "Rayuela",                 # el modelo de datos no registra precios (G13)
}
SOCIO = f"{SEED_ENTITIES['socio_nombre']} {SEED_ENTITIES['socio_apellido']}"


@dataclass(frozen=True)
class GoldenCase:
    id: str
    question: str
    expected_classification: str
    check: Callable[[dict], bool]
    note: str = ""


def _min_rows(n: int) -> Callable[[dict], bool]:
    return lambda out: len(out.get("rows", [])) >= n


def _first_number_positive(out: dict) -> bool:
    """El valor agregado, sea cual sea el alias que elija el modelo (`count`, `total`, ...)."""
    for row in out.get("rows", [])[:1]:
        for value in row.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value > 0
    return False


def _document(prefix: str) -> Callable[[dict], bool]:
    """El primer fragmento citado proviene de un documento cuyo nombre empieza con `prefix`."""
    return lambda out: bool(out.get("chunks")) and str(out["chunks"][0]["document"]).startswith(prefix)


def _both_sources(out: dict) -> bool:
    """Las dos fuentes con evidencia: una sentencia ejecutada y al menos un fragmento citado.

    Las filas pueden ser 0: "sin resultados" es una respuesta válida (R-3.8) y, en un híbrido, la
    última sentencia suele ser una verificación (p. ej. "¿tiene vencidos?") cuya respuesta correcta es
    vacía. Exigir filas daba por fallida a G11 aun con la respuesta correcta.
    """
    return {"sql", "rag"} <= set(out.get("sources", [])) and bool(out.get("sql")) and bool(out.get("chunks"))


GOLDEN_SET: list[GoldenCase] = [
    # --- SQL (criterio de aprobación 2) ---
    GoldenCase("G1", f"¿Qué libros tiene prestados el socio {SOCIO}?", "sql", _min_rows(1),
               "lista de títulos con fecha de préstamo"),
    GoldenCase("G2", "¿Cuáles son los 5 libros más prestados este cuatrimestre?", "sql", _min_rows(1),
               "ranking de 5 títulos con conteo; usa el rango configurado (R-3.11)"),
    GoldenCase("G3", "¿Qué socios tienen préstamos vencidos?", "sql", _min_rows(1),
               "estado por cálculo sobre la vista, no por valor almacenado (R-3.12)"),
    GoldenCase("G4", f'¿Cuántos libros de la categoría "{SEED_ENTITIES["categoria"]}" hay disponibles?',
               "sql", _first_number_positive, "conteo de ejemplares"),
    GoldenCase("G5", f"¿Qué autor tiene más libros publicados por la editorial {SEED_ENTITIES['editorial']}?",
               "sql", _min_rows(1), "autor + cantidad"),

    # --- RAG (criterio de aprobación 3) ---
    GoldenCase("G6", "¿Cuántos días tengo para devolver un libro antes de que me multen?", "rag",
               _document("reglamento_biblioteca"), "plazo exacto citado"),
    GoldenCase("G7", f'¿De qué trata el libro "{SEED_ENTITIES["libro_con_resena"]}"?', "rag",
               _document("resenas_libro_"), "sinopsis citada"),
    GoldenCase("G8", "¿Cómo renuevo un préstamo desde el sistema?", "rag",
               _document("manual_uso_sistema"), "pasos del manual"),
    GoldenCase("G9", "¿Cuál es el horario de la biblioteca?", "rag",
               _document("reglamento_biblioteca"), "horario citado"),

    # --- Híbridos (R-2.4) ---
    GoldenCase("G10", f"{SOCIO} tiene un libro prestado hace 20 días, ¿le corresponde multa según el reglamento?",
               "hybrid", _both_sources, "fecha + norma + conclusión"),
    GoldenCase("G11", "¿El socio con más préstamos puede renovar según el reglamento?", "hybrid",
               _both_sources, "socio top + límite"),
    GoldenCase("G12", "¿Un docente tiene un plazo distinto que un alumno para el libro más prestado?", "hybrid",
               _both_sources, "tipo de socio + norma"),

    # --- No cobertura (R-2.5) ---
    GoldenCase("G13", f'¿Cuál es el precio del libro "{SEED_ENTITIES["libro_sin_precio"]}"?', "none",
               lambda out: not out.get("sources") and not out.get("rows") and not out.get("chunks"),
               "declara ausencia de información (Art. 4)"),
]

# Pruebas de retrieval (R-4.4, R-4.6)
RETRIEVAL_TESTS: list[GoldenCase] = [
    GoldenCase("R1", "plazo de devolución y multas", "rag", _document("reglamento_biblioteca")),
    GoldenCase("R2", f"sinopsis del libro {SEED_ENTITIES['libro_con_resena']}", "rag", _document("resenas_libro_")),
    GoldenCase("R3", "pasos para renovar un préstamo", "rag", _document("manual_uso_sistema")),
    GoldenCase("R4", f"precio del libro {SEED_ENTITIES['libro_sin_precio']}", "none",
               lambda out: not out.get("chunks"), "similitud máxima < umbral → reporte de no-relevancia"),
]

ACCEPTANCE_MIN = 11  # ≥ 11/13 (R-2.1)
ACCENT = ACCEPTANCE_MIN  # alias del nombre anterior
