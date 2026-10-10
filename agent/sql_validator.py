"""Validación estática de sentencias antes de ejecutarlas (T4.2, R-3.2, R-3.3, R-3.4, R-3.7).

Se parsea con `sqlglot` en lugar de regex (D4): regex no distingue CTEs, subqueries
ni identificadores entre comillas, así que la whitelist no sería verificable.

La validación ocurre **antes** de tocar la conexión: si falla, no se ejecuta nada
(R-3.7).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlglot import errors as sqlglot_errors
from sqlglot import exp, parse

from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_TABLES
from agent.errors import SQL_NOT_READONLY, TABLE_NOT_ALLOWED

ALLOWED_ROOTS = (exp.Select,)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str | None
    detail: str | None
    sql: str
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()


def _fail(sql: str, error: str, detail: str, tables=(), columns=()) -> ValidationResult:
    return ValidationResult(False, error, detail, sql, tuple(tables), tuple(columns))


def _has_comments(tree: exp.Expression) -> bool:
    for node in tree.walk():
        if getattr(node, "comments", None):
            return True
    return False


def _cte_names(tree: exp.Expression) -> set[str]:
    return {cte.alias_or_name for cte in tree.find_all(exp.CTE)}


def _alias_map(tree: exp.Expression) -> dict[str, str]:
    """`socios s` -> {'s': 'socios'}; una tabla sin alias se mapea a sí misma."""
    return {(t.alias or t.name): t.name for t in tree.find_all(exp.Table)}


def validate_sql(sql: str, config=None) -> ValidationResult:
    """Devuelve un `ValidationResult`. Nunca ejecuta la sentencia."""
    config = config or load_config()

    try:
        statements = parse(sql, read="postgres")
    except sqlglot_errors.ParseError as exc:
        return _fail(sql, SQL_NOT_READONLY, f"no se puede parsear: {exc}")

    if not statements:
        return _fail(sql, SQL_NOT_READONLY, "sentencia vacía")

    if len(statements) > 1:
        return _fail(sql, SQL_NOT_READONLY, "se esperaba una única sentencia")

    tree = statements[0]
    if not isinstance(tree, ALLOWED_ROOTS):
        return _fail(
            sql, SQL_NOT_READONLY,
            f"statement raíz es {type(tree).__name__}, se esperaba SELECT",
        )

    if _has_comments(tree):
        return _fail(sql, SQL_NOT_READONLY, "comentarios no permitidos")

    ctes = _cte_names(tree)
    aliases = _alias_map(tree)
    tables = sorted({t.name for t in tree.find_all(exp.Table)} - ctes)
    if not tables:
        return _fail(sql, TABLE_NOT_ALLOWED, "no se identifica ninguna tabla del modelo")

    for table in tables:
        if table not in ALLOWED_TABLES:
            return _fail(sql, TABLE_NOT_ALLOWED, f"tabla no permitida: {table}")

    for column in tree.find_all(exp.Column):
        name = column.name
        if column.table:
            origin = aliases.get(column.table, column.table)
            if origin in ctes:
                continue  # columna proyectada por una CTE: no es una tabla física
        else:
            origin = tables[0] if len(tables) == 1 else None
        if origin and origin in ALLOWED_TABLES and name not in ALLOWED_TABLES[origin]:
            return _fail(sql, TABLE_NOT_ALLOWED, f"columna no permitida: {origin}.{name}")

    columns = sorted({c.name for c in tree.find_all(exp.Column)})
    return ValidationResult(True, None, None, sql, tuple(tables), tuple(columns))
