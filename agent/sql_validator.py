"""Validación estática de sentencias antes de ejecutarlas (T4.2, R-3.2, R-3.3, R-3.4, R-3.7, R-3.13).

Se parsea con `sqlglot` en lugar de regex (D4): regex no distingue CTEs, subqueries
ni identificadores entre comillas, así que la whitelist no sería verificable.

La validación ocurre **antes** de tocar la conexión: si falla, no se ejecuta nada
(R-3.7).

Fixes aplicados sobre la versión inicial (2026-10-10, ver `TP/CHANGELOG.md`):
1. `SELECT *` se expande a las columnas de la whitelist → la whitelist de columnas
   deja de ser evadible (R-3.4).
2. Allowlist de funciones → `pg_sleep`, `pg_read_file`, `dblink` se rechazan (R-3.13).
3. `FOR UPDATE` se rechaza: es lock de fila, no lectura (R-3.2).
4. Identificadores normalizados a minúsculas → `FROM "Libros"` ya no se rechaza
   falsamente.
5. `error_level=RAISE` → un SQL mal formado falla en vez de degradar a `Command`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot import ErrorLevel, errors as sqlglot_errors
from sqlglot import exp, parse

from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_FUNCTIONS, ALLOWED_TABLES
from agent.errors import (
    COLUMN_NOT_ALLOWED,
    FUNCTION_NOT_ALLOWED,
    SQL_NOT_READONLY,
    TABLE_NOT_ALLOWED,
)

# Sentencias de lectura admitidas: SELECT, CTE sobre SELECT y operaciones de conjunto.
ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str | None
    detail: str | None
    sql: str
    normalized_sql: str | None = None
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    functions: tuple[str, ...] = ()


def _fail(sql: str, error: str, detail: str, **kw) -> ValidationResult:
    return ValidationResult(False, error, detail, sql, **kw)


def _has_comments(tree: exp.Expression) -> bool:
    for node in tree.walk():
        if getattr(node, "comments", None):
            return True
    return False


def _cte_names(tree: exp.Expression) -> set[str]:
    return {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}


def _normalize_identifiers(tree: exp.Expression) -> None:
    """Identificadores a minúsculas antes de aplicar la whitelist.

    `FROM "Libros"` se rechaza falsamente si la comparación es case-sensitive:
    Postgres resuelve la tabla como `libros`. Normalizar antes de comparar evita el
    falso rechazo y que la sentencia normalizada se ejecute con un nombre distinto.
    """
    for identifier in tree.find_all(exp.Identifier):
        identifier.set("this", identifier.this.lower())


def _alias_map(tree: exp.Expression) -> dict[str, str]:
    """`socios s` -> {'s': 'socios'}; una tabla sin alias se mapea a sí misma."""
    return {(t.alias or t.name).lower(): t.name.lower() for t in tree.find_all(exp.Table)}


def _func_name(node: exp.Expression) -> str:
    # `exp.Anonymous` es la clase genérica de sqlglot: `sql_name()` devuelve
    # "ANONYMOUS", así que hay que leer el nombre real del nodo.
    if isinstance(node, exp.Anonymous):
        return (node.this or "").lower()
    return node.sql_name().lower()


def _is_star_projection(node: exp.Expression) -> bool:
    return isinstance(node, exp.Star) or (isinstance(node, exp.Column) and isinstance(node.this, exp.Star))


def _expand_stars(tree: exp.Expression, aliases: dict[str, str], ctes: set[str]) -> str:
    """`SELECT *` se reescribe a las columnas de la whitelist (R-3.4).

    Sin esto, la whitelist de columnas es evadible: `SELECT * FROM socios` devuelve
    cualquier columna física del esquema, incluidas las que no están en la whitelist.
    """
    for select in tree.find_all(exp.Select):
        tables = sorted({t.name.lower() for t in select.find_all(exp.Table)} - ctes)
        new_exprs = []
        for e in select.expressions:
            if _is_star_projection(e):
                if isinstance(e, exp.Column) and e.table:
                    targets = [aliases.get(e.table.lower(), e.table.lower())]
                else:
                    targets = tables
                for table in targets:
                    for column in sorted(ALLOWED_TABLES[table]):
                        new_exprs.append(exp.column(column, table))
            else:
                new_exprs.append(e)
        select.set("expressions", new_exprs)
    return tree.sql(dialect="postgres")


def validate_sql(sql: str, config=None) -> ValidationResult:
    """Devuelve un `ValidationResult`. Nunca ejecuta la sentencia."""
    config = config or load_config()

    try:
        statements = parse(sql, read="postgres", error_level=ErrorLevel.RAISE)
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

    _normalize_identifiers(tree)

    if _has_comments(tree):
        return _fail(sql, SQL_NOT_READONLY, "comentarios no permitidos")

    if list(tree.find_all(exp.Lock)):
        return _fail(sql, SQL_NOT_READONLY, "SELECT ... FOR UPDATE no es lectura")

    ctes = _cte_names(tree)
    aliases = _alias_map(tree)
    tables = sorted({t.name.lower() for t in tree.find_all(exp.Table)} - ctes)
    if not tables:
        return _fail(sql, TABLE_NOT_ALLOWED, "no se identifica ninguna tabla del modelo")

    for table in tables:
        if table not in ALLOWED_TABLES:
            return _fail(sql, TABLE_NOT_ALLOWED, f"tabla no permitida: {table}")

    functions = sorted({_func_name(f) for f in tree.find_all(exp.Func)})
    for fn in functions:
        if fn not in ALLOWED_FUNCTIONS:
            return _fail(sql, FUNCTION_NOT_ALLOWED, f"función no permitida: {fn}")

    explicit_columns = sorted({c.name.lower() for c in tree.find_all(exp.Column) if c.name != "*"})
    for column in tree.find_all(exp.Column):
        name = column.name.lower()
        if name == "*":
            continue
        if column.table:
            origin = aliases.get(column.table.lower(), column.table.lower())
            if origin in ctes:
                continue  # columna proyectada por una CTE: no es una tabla física
        else:
            origin = tables[0] if len(tables) == 1 else None
        if origin and origin in ALLOWED_TABLES and name not in ALLOWED_TABLES[origin]:
            return _fail(sql, COLUMN_NOT_ALLOWED, f"columna no permitida: {origin}.{name}",
                         tables=tuple(tables), columns=tuple(explicit_columns), functions=tuple(functions))

    normalized = _expand_stars(tree, aliases, ctes)
    effective_columns = sorted({c.name.lower() for c in tree.find_all(exp.Column)})
    return ValidationResult(
        True, None, None, sql, normalized, tuple(tables), tuple(effective_columns), tuple(functions)
    )
