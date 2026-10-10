"""Regresión de la auditoría del 2026-10-10 sobre el validador (D38–D44, D51, D53).

Verificado contra el validador de `HEAD` (antes del fix): de los 28 casos de `REJECTED`, 17 se
aceptaban (B1, B2, B5–B7, B9, B10, B13, B14, B20), se rechazaban con otro código (B3, B8, B15, B16,
B19) o lanzaban una excepción (B22, B26). Los otros 11 ya se rechazaban —varios por coincidencia
de columnas, no por diseño— y quedan como regresión preventiva. Corren sin base ni credenciales.
"""
from __future__ import annotations

import pytest
from sqlglot import parse_one

from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_FUNCTIONS, ALLOWED_TABLES
from agent.errors import (
    COLUMN_NOT_ALLOWED,
    FUNCTION_NOT_ALLOWED,
    QUERY_TOO_COMPLEX,
    SQL_NOT_READONLY,
    TABLE_NOT_ALLOWED,
)
from agent.sql_validator import ValidationResult, validate_sql

_TOO_MANY_TABLES = "SELECT a.id FROM " + ", ".join(
    f"libros {alias}" for alias in "abcdefghi"
)

REJECTED = [
    # --- #1: una CTE homónima en otra subquery ocultaba la tabla prohibida del FROM externo ---
    ("B1", "SELECT l.id FROM libros l, (WITH agent_runs AS (SELECT id FROM libros) "
           "SELECT id FROM agent_runs) t, agent_runs", TABLE_NOT_ALLOWED),
    ("B2", "SELECT l.id FROM libros l CROSS JOIN agent_runs, (WITH agent_runs AS "
           "(SELECT id FROM libros) SELECT id FROM agent_runs) t", TABLE_NOT_ALLOWED),
    ("B3", "SELECT 1 AS a FROM libros, (WITH documentos_embeddings AS (SELECT 1 AS x) "
           "SELECT x FROM documentos_embeddings) t, documentos_embeddings", TABLE_NOT_ALLOWED),
    ("B4", "SELECT 1 AS a FROM (WITH pg_class AS (SELECT 1) SELECT 1 FROM pg_class) t, pg_class",
     TABLE_NOT_ALLOWED),
    # --- DML dentro de una CTE: la raíz es SELECT pero la sentencia escribe (Art. 3) ---
    ("B5", "WITH d AS (DELETE FROM prestamos WHERE id > 0 RETURNING id) SELECT id FROM d",
     SQL_NOT_READONLY),
    ("B6", "WITH u AS (UPDATE libros SET titulo = 'x' RETURNING id) SELECT id FROM u",
     SQL_NOT_READONLY),
    ("B7", "WITH i AS (INSERT INTO autores (id) VALUES (1) RETURNING id) SELECT id FROM i",
     SQL_NOT_READONLY),
    ("B8", "SELECT id INTO nueva FROM libros", SQL_NOT_READONLY),
    # --- #2: columnas sin calificar o inexistentes en consultas con varias tablas ---
    ("B9", "SELECT secreto FROM socios s JOIN prestamos p ON p.socio_id = s.id", COLUMN_NOT_ALLOWED),
    ("B10", "SELECT id FROM libros l JOIN autores a ON a.id = l.autor_id", COLUMN_NOT_ALLOWED),
    ("B11", "SELECT s.secreto FROM socios s", COLUMN_NOT_ALLOWED),
    ("B12", "SELECT x FROM (SELECT secreto AS x FROM socios) t", COLUMN_NOT_ALLOWED),
    # --- #3: schema distinto de `public` ---
    ("B13", "SELECT id FROM otro_schema.libros", TABLE_NOT_ALLOWED),
    ("B14", "SELECT id FROM otra_db.public.libros", TABLE_NOT_ALLOWED),
    # --- funciones de tabla y funciones de efecto en cualquier posición ---
    ("B15", "SELECT * FROM libros, generate_series(1, 10)", FUNCTION_NOT_ALLOWED),
    ("B16", "SELECT l.id FROM libros l, pg_sleep(5)", FUNCTION_NOT_ALLOWED),
    ("B17", "SELECT id FROM libros WHERE pg_sleep(1) IS NOT NULL", FUNCTION_NOT_ALLOWED),
    ("B18", "SELECT set_config('statement_timeout', '0', false) FROM libros", FUNCTION_NOT_ALLOWED),
    # el nombre entre comillas no esconde la función; los niladicos también pasan por la allowlist
    ("B26", 'SELECT "pg_sleep"(1) FROM libros', FUNCTION_NOT_ALLOWED),
    ("B27", "SELECT current_user FROM libros", FUNCTION_NOT_ALLOWED),
    ("B28", "SELECT id FROM libros WHERE titulo = 'x' AND pg_sleep(1) IS NOT NULL", FUNCTION_NOT_ALLOWED),
    # --- complejidad acotada (R-3.17) ---
    ("B19", "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r) SELECT n FROM r",
     QUERY_TOO_COMPLEX),
    ("B20", _TOO_MANY_TABLES, QUERY_TOO_COMPLEX),
    # --- #13: el estado se lee de la vista calculada, no de una columna almacenada ---
    ("B21", "SELECT estado FROM prestamos", COLUMN_NOT_ALLOWED),
    # --- el validador no lanza: entradas rotas se rechazan ---
    ("B22", "SELECT 'abc FROM libros", SQL_NOT_READONLY),
    ("B23", "", SQL_NOT_READONLY),
    ("B24", "   \n  ", SQL_NOT_READONLY),
    ("B25", ";", SQL_NOT_READONLY),
]


@pytest.mark.parametrize("case_id, sql, expected", REJECTED, ids=[c[0] for c in REJECTED])
def test_audit_regressions_are_rejected(case_id: str, sql: str, expected: str) -> None:
    result = validate_sql(sql)
    assert not result.ok, f"{case_id} debería rechazarse: {result.normalized_sql}"
    assert result.error == expected, f"{case_id}: {result.error} ({result.detail})"
    assert result.detail
    assert result.normalized_sql is None


ACCEPTED = [
    # `AND`/`OR` son `Func` para sqlglot: la versión intermedia del fix los rechazaba
    "SELECT id FROM libros WHERE titulo = 'x' AND ejemplares_disponibles > 0",
    "SELECT id FROM libros WHERE ejemplares_disponibles = 0 OR anio_publicacion < 1900",
    "SELECT id FROM libros WHERE (anio_publicacion > 2000 AND isbn IS NOT NULL) OR id = 1",
    # #5: construcciones de control que no son funciones
    "SELECT CASE WHEN ejemplares_disponibles > 0 THEN 'disponible' ELSE 'agotado' END AS d FROM libros",
    "SELECT id FROM socios s WHERE EXISTS (SELECT 1 FROM prestamos p WHERE p.socio_id = s.id)",
    "SELECT id FROM socios s WHERE NOT EXISTS (SELECT 1 FROM prestamos p WHERE p.socio_id = s.id)",
    # #6 del informe: sin FROM (D42) y `;` final (D43)
    "SELECT now()",
    "SELECT CURRENT_DATE",
    "SELECT id FROM libros;",
    # `*` sobre CTEs y subqueries (#4)
    "WITH top AS (SELECT libro_id, count(*) AS c FROM prestamos GROUP BY libro_id) SELECT * FROM top",
    "SELECT t.* FROM (SELECT id FROM libros) t",
    "SELECT * FROM (SELECT id FROM libros) t",
    "WITH x AS (SELECT id FROM libros) SELECT x.* FROM x",
    # una CTE con nombre de tabla prohibida es inofensiva: no lee la tabla real
    "WITH agent_runs AS (SELECT id FROM libros) SELECT id FROM agent_runs",
    "SELECT id FROM public.libros",
    'SELECT "Id" FROM LIBROS',
    "SELECT id FROM libros UNION SELECT id FROM socios",
    "SELECT l.titulo FROM libros l WHERE l.titulo ILIKE '%a%' ORDER BY l.titulo LIMIT 10 OFFSET 5",
    "SELECT a.nombre, count(l.id) AS libros FROM autores a JOIN libros l ON l.autor_id = a.id "
    "GROUP BY a.nombre ORDER BY libros DESC",
]


@pytest.mark.parametrize("sql", ACCEPTED)
def test_legitimate_queries_are_accepted(sql: str) -> None:
    result = validate_sql(sql)
    assert result.ok, f"falso rechazo: {result.error} ({result.detail})"
    assert result.normalized_sql


# --- #5: cada función de la allowlist es alcanzable (el test que hubiera cazado el defecto) ---

FUNCTION_SAMPLES = {
    "count": "count(*)", "sum": "sum(id)", "avg": "avg(id)", "min": "min(id)", "max": "max(id)",
    "bool_and": "bool_and(id > 0)", "bool_or": "bool_or(id > 0)",
    "string_agg": "string_agg(titulo, ',')", "array_agg": "array_agg(id)",
    "row_number": "row_number() over (order by id)", "rank": "rank() over (order by id)",
    "dense_rank": "dense_rank() over (order by id)", "ntile": "ntile(4) over (order by id)",
    "lag": "lag(id) over (order by id)", "lead": "lead(id) over (order by id)",
    "first_value": "first_value(id) over (order by id)", "last_value": "last_value(id) over (order by id)",
    "round": "round(id::numeric, 2)", "floor": "floor(id)", "ceil": "ceil(id)", "abs": "abs(id)",
    "sign": "sign(id)", "lower": "lower(titulo)", "upper": "upper(titulo)", "initcap": "initcap(titulo)",
    "length": "length(titulo)", "trim": "trim(titulo)", "ltrim": "ltrim(titulo)", "rtrim": "rtrim(titulo)",
    "replace": "replace(titulo, 'a', 'b')", "split_part": "split_part(titulo, ' ', 1)",
    "substring": "substring(titulo, 1, 3)", "left": "left(titulo, 3)", "right": "right(titulo, 3)",
    "position": "position('a' in titulo)", "starts_with": "starts_with(titulo, 'a')",
    "concat": "concat(titulo, 'x')", "concat_ws": "concat_ws(',', titulo, isbn)",
    "coalesce": "coalesce(isbn, '')", "nullif": "nullif(id, 0)", "greatest": "greatest(id, 1)",
    "least": "least(id, 1)", "cast": "cast(id as text)",
    "current_date": "current_date", "current_timestamp": "current_timestamp", "now": "now()",
    "clock_timestamp": "clock_timestamp()", "date_trunc": "date_trunc('month', current_date)",
    "date_part": "date_part('day', current_date)", "extract": "extract(day from current_date)",
    "to_char": "to_char(current_date, 'YYYY')", "to_date": "to_date('2026-01-01', 'YYYY-MM-DD')",
    "age": "age(current_date)", "make_date": "make_date(2026, 1, 1)",
}


def test_every_allowed_function_has_a_sample() -> None:
    # Si alguien agrega una función a la allowlist sin probar que llega a la base, falla acá.
    assert set(FUNCTION_SAMPLES) == ALLOWED_FUNCTIONS


@pytest.mark.parametrize("name", sorted(FUNCTION_SAMPLES))
def test_every_allowed_function_is_reachable(name: str) -> None:
    result = validate_sql(f"SELECT {FUNCTION_SAMPLES[name]} FROM libros")
    assert result.ok, f"{name} está en la allowlist pero se rechaza: {result.error} ({result.detail})"


# --- `SELECT *` (#4) ---


def _projection_names(sql: str) -> list[str]:
    return [e.alias_or_name for e in parse_one(sql, read="postgres").expressions]


def test_star_over_cte_expands_to_the_cte_columns() -> None:
    result = validate_sql(
        "WITH top AS (SELECT libro_id, count(*) AS c FROM prestamos GROUP BY libro_id) SELECT * FROM top"
    )
    assert result.ok
    assert _projection_names(result.normalized_sql) == ["libro_id", "c"]


def test_qualified_star_over_subquery_does_not_raise() -> None:
    result = validate_sql("SELECT t.* FROM (SELECT id, titulo FROM libros) t")
    assert result.ok
    assert _projection_names(result.normalized_sql) == ["id", "titulo"]


def test_star_over_join_yields_unique_output_names() -> None:
    # `dict(zip(columns, row))` pisaría el segundo `id` en silencio (viola Art. 4).
    result = validate_sql("SELECT * FROM libros l JOIN autores a ON a.id = l.autor_id")
    assert result.ok
    names = _projection_names(result.normalized_sql)
    assert len(names) == len(set(names))
    assert {"l_id", "a_id"} <= set(names)


def test_unnamed_aggregates_keep_their_natural_name() -> None:
    result = validate_sql("SELECT count(*), max(fecha_prestamo) FROM prestamos")
    assert result.ok
    assert _projection_names(result.normalized_sql) == ["count", "max"]


def test_star_never_exposes_columns_outside_the_whitelist() -> None:
    for table, columns in ALLOWED_TABLES.items():
        result = validate_sql(f"SELECT * FROM {table}")
        assert result.ok, f"{table}: {result.detail}"
        assert set(_projection_names(result.normalized_sql)) == columns


# --- el validador nunca lanza ---

HOSTILE_INPUTS = [
    "\x00", "SELECT", "SELECT (", "select * from", "WITH", "((((", "SELECT 1 FROM libros WHERE",
    "'; DROP TABLE libros; --", "SELECT $$x$$", "/* */", "-- x", "SELECT * FROM libros l JOIN",
    "SELECT * FROM libros WHERE titulo = 'a' ||", "(" * 300 + "SELECT 1" + ")" * 300,
    "SELECT 1 FROM libros WHERE id = ANY(ARRAY[1,2,3])", "VALUES (1)", "TABLE libros",
]


@pytest.mark.parametrize("sql", HOSTILE_INPUTS)
def test_validate_sql_never_raises(sql: str) -> None:
    result = validate_sql(sql)
    assert isinstance(result, ValidationResult)
    if not result.ok:
        assert result.error and result.detail


# --- las consultas de referencia del golden set pasan (D16: SQL esperado, no prosa) ---

REFERENCE_QUERIES = {
    "G1": "SELECT l.titulo, p.fecha_prestamo FROM prestamos p JOIN socios s ON s.id = p.socio_id "
          "JOIN libros l ON l.id = p.libro_id "
          "WHERE s.nombre = 'Juan' AND s.apellido = 'Pérez' AND p.fecha_devolucion_real IS NULL",
    "G2": "SELECT l.titulo, count(*) AS total FROM prestamos p JOIN libros l ON l.id = p.libro_id "
          "WHERE p.fecha_prestamo BETWEEN '2026-08-01' AND '2026-11-30' "
          "GROUP BY l.titulo ORDER BY total DESC LIMIT 5",
    "G3": "SELECT DISTINCT s.id, s.nombre, s.apellido FROM prestamos_estado pe "
          "JOIN socios s ON s.id = pe.socio_id WHERE pe.estado = 'vencido'",
    "G4": "SELECT coalesce(sum(l.ejemplares_disponibles), 0) AS disponibles FROM libros l "
          "JOIN categorias c ON c.id = l.categoria_id WHERE c.nombre = 'Ciencias de la Computación'",
    "G5": "SELECT a.nombre, a.apellido, count(*) AS libros FROM libros l "
          "JOIN autores a ON a.id = l.autor_id JOIN editoriales e ON e.id = l.editorial_id "
          "WHERE e.nombre = 'Sudamericana' GROUP BY a.id, a.nombre, a.apellido "
          "ORDER BY libros DESC LIMIT 1",
    "G10": "SELECT p.fecha_prestamo, p.fecha_devolucion_prevista, CURRENT_DATE - p.fecha_prestamo AS dias "
           "FROM prestamos p JOIN socios s ON s.id = p.socio_id "
           "WHERE s.apellido = 'Pérez' AND p.fecha_devolucion_real IS NULL "
           "AND p.fecha_prestamo <= CURRENT_DATE - INTERVAL '20 days'",
    "G11": "SELECT s.id, s.nombre, count(*) AS prestamos FROM prestamos p JOIN socios s ON s.id = p.socio_id "
           "GROUP BY s.id, s.nombre ORDER BY prestamos DESC LIMIT 1",
    "G12": "SELECT s.tipo_socio, count(*) AS prestamos FROM prestamos p JOIN socios s ON s.id = p.socio_id "
           "WHERE p.libro_id = (SELECT libro_id FROM prestamos GROUP BY libro_id "
           "ORDER BY count(*) DESC LIMIT 1) GROUP BY s.tipo_socio",
}


@pytest.mark.parametrize("case_id", sorted(REFERENCE_QUERIES))
def test_golden_reference_queries_pass_validation(case_id: str) -> None:
    result = validate_sql(REFERENCE_QUERIES[case_id])
    assert result.ok, f"{case_id}: {result.error} ({result.detail})"


def test_table_ref_cap_comes_from_config() -> None:
    assert load_config().max_table_refs == 8
