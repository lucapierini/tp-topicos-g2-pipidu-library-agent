"""Validación estática de sentencias antes de ejecutarlas (T4.2, R-3.2, R-3.3, R-3.4, R-3.7, R-3.13).

Se parsea con `sqlglot` en lugar de regex (D4): regex no distingue CTEs, subqueries
ni identificadores entre comillas, así que la whitelist no sería verificable.

La validación ocurre **antes** de tocar la conexión: si falla, no se ejecuta nada
(R-3.7). Nunca lanza: cualquier fallo interno se reporta como rechazo (falla cerrado).

La resolución de tablas y columnas es **por scope** (`traverse_scope` + `qualify_columns` con la
whitelist como schema, D38–D44): una CTE homónima en otra subquery no oculta una tabla prohibida,
las columnas sin calificar en un JOIN se validan y `*` se expande también sobre CTEs y subqueries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlglot import ErrorLevel, exp, parse
from sqlglot import errors as sqlglot_errors
from sqlglot.optimizer.qualify_columns import qualify_columns, validate_qualify_columns
from sqlglot.optimizer.scope import traverse_scope

from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_FUNCTIONS, ALLOWED_TABLES, sqlglot_schema
from agent.errors import (
    COLUMN_NOT_ALLOWED,
    FUNCTION_NOT_ALLOWED,
    QUERY_TOO_COMPLEX,
    SQL_NOT_READONLY,
    TABLE_NOT_ALLOWED,
)

# Sentencias de lectura admitidas: SELECT, CTE sobre SELECT y operaciones de conjunto.
ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# Nodos que modifican estado o no son lectura, en **cualquier** posición del árbol:
# `WITH d AS (DELETE ... RETURNING id) SELECT id FROM d` tiene raíz SELECT y escribe (D39).
_WRITE_NODE_NAMES = (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "Command", "Into",
    "Copy", "TruncateTable", "Grant", "Set", "Transaction", "Commit", "Rollback", "Use",
    "Analyze", "Kill", "LoadData", "Declare",
)
WRITE_NODES = tuple(getattr(exp, name) for name in _WRITE_NODE_NAMES if hasattr(exp, name))

# Construcciones de control: sqlglot las modela como `Func`, pero no son llamadas a función
# (D41). Sus subexpresiones sí se validan por separado.
_CONTROL_NODES = (exp.Case, exp.If, exp.Exists)

# `nombre(`: llamada a función. Los niladicos de SQL (`CURRENT_DATE`, `USER`) se emiten sin
# paréntesis y hay que reconocerlos para aplicarles la allowlist.
_CALL_AT_START = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_NILADIC_AT_START = re.compile(
    r"(current_[a-z_]+|localtime|localtimestamp|session_user|user)\b", re.IGNORECASE
)


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


class _Reject(Exception):
    """Rechazo con código tipado. Interno: `validate_sql` lo convierte en `ValidationResult`."""

    def __init__(self, error: str, detail: str) -> None:
        super().__init__(detail)
        self.error = error
        self.detail = detail


def _fail(sql: str, error: str, detail: str) -> ValidationResult:
    return ValidationResult(False, error, detail, sql)


# --------------------------------------------------------------------------- helpers


def _has_comments(tree: exp.Expression) -> bool:
    return any(getattr(node, "comments", None) for node in tree.walk())


def _normalize_identifiers(tree: exp.Expression) -> None:
    """Identificadores a minúsculas antes de aplicar la whitelist (D28, R-3.15).

    `FROM "Libros"` se rechaza falsamente si la comparación es case-sensitive:
    Postgres resuelve la tabla como `libros`. Los literales de texto no son
    `exp.Identifier`, así que no se tocan (D31).
    """
    for identifier in tree.find_all(exp.Identifier):
        identifier.set("this", identifier.this.lower())


def _func_name(node: exp.Expression) -> str | None:
    """Nombre de la función **tal como la emite el dialecto postgres** (D41).

    `sql_name()` devuelve el nombre interno de sqlglot (`group_concat` para `string_agg`,
    `ANONYMOUS` para las funciones desconocidas). Lo que se ejecuta es el SQL generado,
    así que se valida el nombre que contiene.

    Devuelve `None` si el nodo no es una llamada: sqlglot modela como `Func` operadores
    (`And`, `Or`) que se emiten como `a AND b`. Sus operandos se validan por separado porque
    `find_all` recorre todo el árbol.
    """
    if isinstance(node, exp.Anonymous):
        # Función desconocida para sqlglot: el nombre real está en `this`, y puede venir
        # entre comillas (`"pg_sleep"(1)`), que el texto generado no deja leer.
        return str(node.this).strip('"').lower()
    text = node.sql(dialect="postgres").lstrip()
    match = _CALL_AT_START.match(text) or _NILADIC_AT_START.match(text)
    return match.group(1).lower() if match else None


def _physical_tables(tree: exp.Expression) -> list[exp.Table]:
    """Referencias a tablas físicas, resueltas **por scope** (D38).

    Una referencia sin schema cuyo nombre coincide con una CTE visible en su scope es una
    referencia a esa CTE, no a una tabla. Resolverlo globalmente permitía que una CTE
    homónima, definida en otra subquery, ocultara una tabla prohibida.
    """
    found: list[exp.Table] = []
    for scope in traverse_scope(tree):
        for table in scope.tables:
            if not table.db and not table.catalog and table.name in scope.cte_sources:
                continue
            found.append(table)
    return found


def _output_select(tree: exp.Expression) -> exp.Select | None:
    node: exp.Expression | None = tree
    while node is not None and not isinstance(node, exp.Select):
        node = node.args.get("this")
        if isinstance(node, exp.Subquery):
            node = node.this
    return node


def _friendly_aliases(select: exp.Select) -> None:
    """`qualify_columns` nombra `_col_0` a lo que Postgres llamaría `count`, `sum`, `extract`.

    Se restaura el nombre natural para que las filas devueltas y la sentencia exhibida
    (R-3.9) sean legibles. Si el nombre ya está en uso se deja `_col_N`.
    """
    taken = {e.alias_or_name.lower() for e in select.expressions}
    for projection in select.expressions:
        if not isinstance(projection, exp.Alias) or not re.fullmatch(r"_col_\d+", projection.alias):
            continue
        inner = projection.this
        if isinstance(inner, exp.Window):
            inner = inner.this
        name = ""
        if isinstance(inner, exp.Case):
            name = "case"
        elif isinstance(inner, exp.Func) and not isinstance(inner, _CONTROL_NODES):
            name = _func_name(inner)
        if name and name not in taken:  # `None` o vacío: se deja `_col_N`
            projection.set("alias", exp.to_identifier(name))
            taken.add(name)


def _disambiguate_outputs(tree: exp.Expression) -> None:
    """`SELECT * FROM libros JOIN autores` produce `id` dos veces; `dict(zip(...))` pisaría una.

    Las columnas repetidas se renombran `<tabla>_<columna>` (D44).
    """
    select = _output_select(tree)
    if select is None:
        return
    _friendly_aliases(select)
    names = [e.alias_or_name.lower() for e in select.expressions]
    duplicated = {n for n in names if names.count(n) > 1}
    for projection in select.expressions:
        name = projection.alias_or_name.lower()
        inner = projection.unalias()
        if name in duplicated and isinstance(inner, exp.Column) and inner.table:
            new_name = f"{inner.table}_{inner.name}"
            if isinstance(projection, exp.Alias):
                projection.set("alias", exp.to_identifier(new_name))
            else:
                projection.replace(exp.alias_(inner.copy(), new_name))


# --------------------------------------------------------------------------- checks


def _check_structure(tree: exp.Expression, max_table_refs: int) -> tuple[list[exp.Table], list[str]]:
    """Reglas que no dependen del esquema. Lanza `_Reject`. Devuelve (tablas, funciones)."""
    if not isinstance(tree, ALLOWED_ROOTS):
        raise _Reject(SQL_NOT_READONLY, f"statement raíz es {type(tree).__name__}, se esperaba SELECT")

    for node in tree.walk():
        if isinstance(node, WRITE_NODES):
            raise _Reject(SQL_NOT_READONLY, f"{type(node).__name__} no es lectura")

    if list(tree.find_all(exp.Lock)):
        raise _Reject(SQL_NOT_READONLY, "SELECT ... FOR UPDATE no es lectura")

    # Una CTE recursiva es un generador de carga arbitraria: el timeout la corta, pero ocupa
    # la base los 10 s. El dominio no necesita recursión (R-3.17).
    if any(with_.args.get("recursive") for with_ in tree.find_all(exp.With)):
        raise _Reject(QUERY_TOO_COMPLEX, "WITH RECURSIVE no está permitido")

    tables = _physical_tables(tree)
    for table in tables:
        if isinstance(table.this, exp.Func) or not table.name:
            name = (_func_name(table.this) if isinstance(table.this, exp.Func) else None) or "?"
            raise _Reject(FUNCTION_NOT_ALLOWED, f"función de tabla no permitida: {name}")
        if table.catalog or (table.db and table.db.lower() != "public"):
            qualified = ".".join(p for p in (table.catalog, table.db, table.name) if p)
            raise _Reject(TABLE_NOT_ALLOWED, f"schema no permitido: {qualified}")
        if table.name.lower() not in ALLOWED_TABLES:
            raise _Reject(TABLE_NOT_ALLOWED, f"tabla no permitida: {table.name.lower()}")

    if len(tables) > max_table_refs:
        raise _Reject(QUERY_TOO_COMPLEX, f"{len(tables)} referencias a tablas (máximo {max_table_refs})")

    names = (_func_name(f) for f in tree.find_all(exp.Func) if not isinstance(f, _CONTROL_NODES))
    functions = sorted({name for name in names if name is not None})
    for name in functions:
        if name not in ALLOWED_FUNCTIONS:
            raise _Reject(FUNCTION_NOT_ALLOWED, f"función no permitida: {name or '?'}")

    return tables, functions


def _validate(sql: str, config) -> ValidationResult:
    try:
        statements = parse(sql, read="postgres", error_level=ErrorLevel.RAISE)
    except sqlglot_errors.SqlglotError as exc:  # ParseError y TokenError (D29)
        raise _Reject(SQL_NOT_READONLY, f"no se puede parsear: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if not statements:
        raise _Reject(SQL_NOT_READONLY, "sentencia vacía")
    if len(statements) > 1:
        raise _Reject(SQL_NOT_READONLY, "se esperaba una única sentencia")

    tree = statements[0]
    _normalize_identifiers(tree)

    if _has_comments(tree):
        raise _Reject(SQL_NOT_READONLY, "comentarios no permitidos")

    tables, functions = _check_structure(tree, config.max_table_refs)

    # Columnas: se resuelven por scope contra la whitelist. Una columna sin calificar en un
    # JOIN, una columna inexistente o una ambigua fallan acá (R-3.4). `SELECT *` se expande
    # a la whitelist, también sobre CTEs y subqueries (R-3.14).
    try:
        qualified = qualify_columns(tree, schema=sqlglot_schema(), dialect="postgres")
        validate_qualify_columns(qualified)
    except sqlglot_errors.OptimizeError as exc:
        raise _Reject(COLUMN_NOT_ALLOWED, f"columna no permitida o ambigua: {exc}") from exc

    _disambiguate_outputs(qualified)
    normalized = qualified.sql(dialect="postgres")

    # Defensa en profundidad: lo que se ejecuta es `normalized`, así que se vuelve a verificar
    # la sentencia reparseada y no el árbol que produjo la reescritura.
    try:
        reparsed = parse(normalized, read="postgres", error_level=ErrorLevel.RAISE)
    except sqlglot_errors.SqlglotError as exc:
        raise _Reject(SQL_NOT_READONLY, f"la sentencia normalizada no es reparseable: {exc}") from exc
    if len(reparsed) != 1:
        raise _Reject(SQL_NOT_READONLY, "la sentencia normalizada no es única")
    _check_structure(reparsed[0], config.max_table_refs)

    columns = sorted({c.name.lower() for c in qualified.find_all(exp.Column)})
    return ValidationResult(
        True,
        None,
        None,
        sql,
        normalized,
        tuple(sorted({t.name.lower() for t in tables})),
        tuple(columns),
        tuple(functions),
    )


def validate_sql(sql: str, config=None) -> ValidationResult:
    """Devuelve un `ValidationResult`. Nunca ejecuta la sentencia ni lanza excepciones."""
    config = config or load_config()
    try:
        return _validate(sql, config)
    except _Reject as rejection:
        return _fail(sql, rejection.error, rejection.detail)
    except Exception as exc:  # noqa: BLE001 - falla cerrado: lo no verificable no se ejecuta
        return _fail(sql, SQL_NOT_READONLY, f"no se pudo validar: {type(exc).__name__}: {exc}")
