"""Whitelist de tablas, columnas y funciones (T4.1, R-3.4, R-3.13).

Este archivo es un contrato entre el desarrollo del agente y el modelo de datos.
Si `db/schema.sql` cambia, la whitelist cambia en el mismo commit.

Incluye las 6 tablas del modelo (R-3.4) y la vista `prestamos_estado`, que es la
forma en que el estado de vencimiento se resuelve por cálculo y no por valor
almacenado (D7, R-3.12).

Las tablas internas del sistema (`agent_runs`, `documentos_embeddings`) NO están
permitidas: la herramienta SQL solo lee el dominio, nunca la trazabilidad ni el
repositorio documental.
"""
from __future__ import annotations

ALLOWED_TABLES: dict[str, set[str]] = {
    "autores": {
        "id", "nombre", "apellido", "nacionalidad", "fecha_nacimiento",
    },
    "editoriales": {
        "id", "nombre", "pais",
    },
    "categorias": {
        "id", "nombre", "descripcion",
    },
    "libros": {
        "id", "titulo", "isbn", "autor_id", "editorial_id", "categoria_id",
        "anio_publicacion", "ejemplares_totales", "ejemplares_disponibles",
    },
    "socios": {
        # No hay política de PII (Art. 11): todos los usuarios acceden a toda la información
        # del dominio. La whitelist es control de alcance y de inyección, no de privacidad.
        # Aun así la lista es vinculante porque `SELECT *` se expande a ella (R-3.4, D25):
        # una columna física del esquema que no esté acá es inalcanzable para el agente.
        "id", "nombre", "apellido", "legajo", "tipo_socio", "email", "fecha_alta",
    },
    # `estado` NO está en la whitelist de la tabla (D51): el vencimiento se calcula en la vista
    # `prestamos_estado` (D7, R-3.12). Si la tabla expusiera una columna almacenada, el modelo
    # podría leerla en vez de calcularlo y el resultado dejaría de ser verificable.
    "prestamos": {
        "id", "libro_id", "socio_id", "fecha_prestamo", "fecha_devolucion_prevista",
        "fecha_devolucion_real",
    },
    # Vista calculada (D7, R-3.12). El estado se deriva de las fechas.
    "prestamos_estado": {
        "id", "libro_id", "socio_id", "fecha_prestamo", "fecha_devolucion_prevista",
        "fecha_devolucion_real", "estado", "dias_atraso",
    },
}

# Explícitamente fuera de la whitelist, para que el test de regresión no se
# apoye en un olvido.
FORBIDDEN_TABLES: set[str] = {
    "agent_runs",
    "documentos_embeddings",
    "pg_catalog",
    "information_schema",
}

# Allowlist de funciones (R-3.13, D41). Los nombres son los que emite el dialecto
# **postgres** de sqlglot, es decir, los que efectivamente llegan a la base: no los nombres
# internos de `sqlglot` (`string_agg` es `GroupConcat`, `to_char` es `TimeToStr`).
# Cualquier función fuera de esta lista se rechaza: `pg_sleep`, `pg_read_file`, `dblink`,
# `pg_advisory_lock` son funciones de efecto, no de cálculo sobre el dominio.
# `CASE`, `EXISTS` e `IF` no son funciones: son construcciones de control y no se filtran acá.
ALLOWED_FUNCTIONS: set[str] = {
    # agregación
    "count", "sum", "avg", "min", "max", "bool_and", "bool_or",
    "string_agg", "array_agg",
    # window
    "row_number", "rank", "dense_rank", "ntile", "lag", "lead", "first_value", "last_value",
    # escalares
    "round", "floor", "ceil", "abs", "sign",
    "lower", "upper", "initcap", "length", "trim", "ltrim", "rtrim", "replace", "split_part",
    "substring", "left", "right", "position", "starts_with",
    "concat", "concat_ws",
    "coalesce", "nullif", "greatest", "least", "cast",
    # temporales (R-3.11)
    "current_date", "current_timestamp", "now", "clock_timestamp",
    "date_trunc", "date_part", "extract", "to_char", "to_date",
    "age", "make_date",
}


def sqlglot_schema() -> dict[str, dict[str, str]]:
    """La whitelist en la forma que consume `sqlglot.optimizer.qualify_columns` (D38).

    El tipo es irrelevante para la validación; solo importa qué columnas existen.
    """
    return {table: {column: "text" for column in sorted(columns)} for table, columns in ALLOWED_TABLES.items()}
