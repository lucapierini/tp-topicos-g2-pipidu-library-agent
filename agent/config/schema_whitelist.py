"""Whitelist de tablas y columnas (T4.1, R-3.4).

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
        "id", "nombre", "apellido", "legajo", "tipo_socio", "email", "fecha_alta",
    },
    "prestamos": {
        "id", "libro_id", "socio_id", "fecha_prestamo", "fecha_devolucion_prevista",
        "fecha_devolucion_real", "estado",
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
    "pg_tables",
    "pg_catalog",
    "information_schema",
}
