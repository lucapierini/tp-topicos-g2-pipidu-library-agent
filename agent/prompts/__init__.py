"""Prompts del agente (T6.1).

El esquema que ve el modelo se **genera** desde la whitelist (`schema_whitelist.py`): si una
columna se agrega o se quita, el prompt cambia en el mismo commit y el modelo nunca conoce una
columna que el validador rechazaría (ni al revés).
"""
from __future__ import annotations

from pathlib import Path
from string import Template

from agent.config import Config, load_config
from agent.config.schema_whitelist import ALLOWED_TABLES

_DIR = Path(__file__).resolve().parent

# Descripción corta por tabla. Las columnas salen de la whitelist, no de acá.
TABLE_NOTES = {
    "autores": "autores de los libros",
    "editoriales": "editoriales",
    "categorias": "categorías temáticas de los libros",
    "libros": "catálogo; `ejemplares_disponibles` es el stock prestable ahora; NO tiene autor: los autores "
              "están en `libros_autores`",
    "libros_autores": "relación N:M entre libros y autores; `orden` es la posición del autor en el libro",
    "socios": "alumnos y docentes; `tipo_socio` es 'alumno' o 'docente'",
    "prestamos": "un préstamo por fila; `estado` es SOLO 'activo' o 'devuelto' (nunca 'vencido'); "
                 "`fecha_devolucion_real` es NULL si no se devolvió",
    "v_prestamos_estado": "VISTA de `prestamos` con `estado_calculado` ('activo', 'devuelto', 'vencido') y "
                          "`dias_atraso`. Para vencidos y atrasos usar SIEMPRE esta vista",
}

RELATIONS = (
    "libros.editorial_id -> editoriales.id; libros.categoria_id -> categorias.id; "
    "libros_autores.libro_id -> libros.id; libros_autores.autor_id -> autores.id (los autores de un libro "
    "se obtienen por `libros_autores`); prestamos.libro_id -> libros.id; prestamos.socio_id -> socios.id; "
    "v_prestamos_estado.libro_id / socio_id igual que prestamos."
)


def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8")


def schema_description() -> str:
    lines = []
    for table, columns in ALLOWED_TABLES.items():
        note = TABLE_NOTES.get(table, "")
        suffix = f"  -- {note}" if note else ""
        lines.append(f"- {table}({', '.join(sorted(columns))}){suffix}")
    return "\n".join(lines)


# Instrucción explícita de idioma (R-5.1). Con la regla genérica "en el idioma de la consulta" el
# modelo respondió en castellano a consultas en inglés: el prompt, las herramientas y los documentos
# están en castellano y arrastran la respuesta.
LANGUAGE_RULES = {
    "es": "**Respondé en castellano.**",
    "en": (
        "**Answer in English.** The question is in English: write the whole answer in English, even "
        "though the tools and the documents are in Spanish. Translate their content; keep titles, "
        "names and quoted values exactly as the tool returned them."
    ),
}


def render_system_prompt(
    config: Config | None = None, *, classification: str, tools: list[str], language: str = "es"
) -> str:
    cfg = config or load_config()
    return Template(_read("system_prompt.md")).safe_substitute(
        language_rule=LANGUAGE_RULES.get(language, LANGUAGE_RULES["es"]),
        classification=classification,
        tools=", ".join(f"`{t}`" for t in tools) or "ninguna",
        schema=schema_description(),
        relations=RELATIONS,
        cuatrimestre_start=cfg.cuatrimestre_start.isoformat(),
        cuatrimestre_end=cfg.cuatrimestre_end.isoformat(),
        timezone=cfg.timezone,
        max_rows=cfg.max_rows,
        max_attempts=cfg.max_sql_attempts,
    )


def render_classifier_prompt() -> str:
    return _read("classifier_prompt.md")
