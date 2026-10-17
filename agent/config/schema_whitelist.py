"""Whitelist de tablas, columnas y funciones (T4.1, R-3.4, R-3.13).

Este archivo es un contrato entre el desarrollo del agente y el modelo de datos.
Si `db/schema.sql` cambia, la whitelist cambia en el mismo commit.

Refleja el esquema real compartido (`db/schema.sql`, D64): las 7 tablas del dominio y la vista
`v_prestamos_estado`, que es donde el vencimiento se resuelve por cálculo (D7, R-3.12): la tabla
`prestamos` solo guarda `activo`/`devuelto`, nunca `vencido`.

Las tablas internas NO están permitidas (D21): `agent_runs` (trazabilidad) y `documentos` /
`documentos_chunks` (repositorio documental, que lee la herramienta de RAG por su propia vía).
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
    # No hay `autor_id`: un libro puede tener varios autores (`libros_autores`, N:M).
    "libros": {
        "id", "titulo", "isbn", "editorial_id", "categoria_id",
        "anio_publicacion", "ejemplares_totales", "ejemplares_disponibles",
    },
    "libros_autores": {
        "libro_id", "autor_id", "orden",
    },
    "socios": {
        # No hay política de PII (Art. 11): todos los usuarios acceden a toda la información
        # del dominio. La whitelist es control de alcance y de inyección, no de privacidad.
        # Aun así la lista es vinculante porque `SELECT *` se expande a ella (R-3.4, D25):
        # una columna física del esquema que no esté acá es inalcanzable para el agente.
        "id", "nombre", "apellido", "legajo", "tipo_socio", "email", "fecha_alta",
    },
    # `estado` existe pero solo vale 'activo' o 'devuelto' (CHECK en el esquema): un préstamo
    # vencido sigue siendo 'activo' acá. El vencimiento se consulta en la vista (D64).
    "prestamos": {
        "id", "libro_id", "socio_id", "fecha_prestamo", "fecha_devolucion_prevista",
        "fecha_devolucion_real", "estado",
    },
    # Vista calculada (D7, R-3.12). `estado_calculado` es 'activo' | 'devuelto' | 'vencido'.
    "v_prestamos_estado": {
        "id", "libro_id", "socio_id", "fecha_prestamo", "fecha_devolucion_prevista",
        "fecha_devolucion_real", "estado", "estado_calculado", "dias_atraso",
    },
}

# Explícitamente fuera de la whitelist. `documentos_embeddings` no existe en el esquema; se lista
# para que el test no dependa de un olvido.
FORBIDDEN_TABLES: set[str] = {
    "agent_runs",
    "documentos",
    "documentos_chunks",
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
