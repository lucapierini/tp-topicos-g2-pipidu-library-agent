"""Contrato de datos que lee el agente (`TP/02` §3.4; T2.5, T2.7).

Qué agrega y qué reutiliza, para no duplicar:

- `tests/test_schema_whitelist.py` ya verifica esquema ↔ whitelist (bidireccional). Acá se verifica el
  **documento** del contrato (`TP/02` §3.4.1) contra la whitelist y contra `db/schema.sql`: el contrato no
  puede nombrar una columna ausente del esquema, ni omitir una que el agente lee. Se reusa el parser
  `_table_columns` de ese módulo.
- `tests/test_golden_seed.py` ya verifica que el seed contiene las entidades que nombran G1–G5. Acá se
  agrega lo que ese test no cubre: el volumen por tabla (T2.5) y las reglas de consistencia (T2.7).
- La conexión de integración reusa el patrón de `tests/test_runs_integration.py` (rol `agent_ro`,
  `set_session(readonly=True)`). Esta suite **no escribe ni trunca nada**.

La parte offline corre siempre (`pytest -q`, Art. 6). La parte marcada `integration` se salta sin base.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from agent.config import load_config
from agent.config.schema_whitelist import ALLOWED_TABLES, FORBIDDEN_TABLES
from tests.test_schema_whitelist import _NOT_COLUMNS, SCHEMA, _table_columns

ROOT = Path(__file__).resolve().parents[1]
TP02 = ROOT / "TP" / "02-especificacion-tecnica.md"

# Las 7 tablas del dominio (T2.5). La vista no cuenta: se calcula, no se siembra.
DOMAIN_TABLES = ("autores", "editoriales", "categorias", "libros", "libros_autores", "socios", "prestamos")
MIN_ROWS = 15  # mínimo de registros por tabla del dominio (T2.5)
DOCUMENT_TABLES = {"documentos", "documentos_chunks"}


def _contract_block() -> str:
    doc = TP02.read_text(encoding="utf-8")
    block = re.search(r"### 3\.4 Contrato de datos que lee el agente.*?(?=\n## 4\.)", doc, re.S)
    assert block, "TP/02 no tiene el apartado 3.4 (contrato de datos que lee el agente)"
    return block.group(0)


def _contract_rows() -> dict[str, set[str]]:
    r"""Filas `| `objeto` | `columna`, `columna` | vía |` del contrato de §3.4.1."""
    rows: dict[str, set[str]] = {}
    for line in _contract_block().splitlines():
        match = re.match(r"^\|\s*`(\w+)`\s*\|\s*(.+?)\s*\|\s*[^|]*\|\s*$", line)
        if not match:
            continue
        rows[match.group(1)] = set(re.findall(r"`(\w+)`", match.group(2)))
    return rows


def _defined_columns(table: str) -> set[str]:
    """Columnas del objeto según `db/schema.sql`: tabla, o select de la vista (D64)."""
    text = SCHEMA.read_text(encoding="utf-8")
    if re.search(rf"CREATE TABLE(?: IF NOT EXISTS)?\s+{table}\b", text, re.I):
        return _table_columns(text, table)
    view = re.search(rf"CREATE VIEW\s+{table}\s+AS\s+(.*?)\bFROM\b", text, re.I | re.S)
    assert view, f"{table} no aparece en schema.sql como tabla ni como vista"
    return {word for word in re.findall(r"\w+", view.group(1)) if word.upper() not in _NOT_COLUMNS}


# ---------------------------------------------------------------- offline (sin base)


def test_contract_names_every_object_the_agent_reads() -> None:
    """El contrato nombra exactamente los objetos que el agente puede leer (R-3.4, D21)."""
    objects = set(_contract_rows())
    expected = set(ALLOWED_TABLES) | DOCUMENT_TABLES
    assert objects == expected, f"el contrato de TP/02 §3.4.1 nombra {sorted(objects)} != {sorted(expected)}"


def test_contract_columns_match_the_whitelist_and_the_schema() -> None:
    """Ninguna columna del contrato está ausente del esquema, y no omite las que la whitelist permite."""
    for table, columns in _contract_rows().items():
        actual = _defined_columns(table)
        missing = columns - actual
        assert not missing, f"{table}: columnas del contrato ausentes del esquema: {sorted(missing)}"
        if table in ALLOWED_TABLES:
            assert columns == ALLOWED_TABLES[table], (
                f"{table}: el contrato y la whitelist difieren; en la whitelist {sorted(ALLOWED_TABLES[table] - columns)}"
            )
        else:
            # Las tablas documentales siguen fuera de la whitelist SQL (D21): el contrato las lista
            # solo como vía de la herramienta de recuperación.
            assert table in FORBIDDEN_TABLES, f"{table} no debería estar fuera de la vía SQL"


def test_embedding_model_in_the_stack_table_matches_D5() -> None:
    """La fila 'Embeddings' de `TP/02` §2 dice `gemini-embedding-001` con 768 (D5).

    `text-embedding-004` queda deprecado: solo puede aparecer en la nota "Descartado" del propio D5,
    que es la que registra el descarte. Cualquier otra mención en un `.md` es una línea desactualizada.
    """
    row = next(line for line in TP02.read_text(encoding="utf-8").splitlines() if line.startswith("| Embeddings |"))
    assert "gemini-embedding-001" in row and "768" in row and "D5" in row, row

    stale = []
    for path in ROOT.rglob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "text-embedding-004" in line and not line.startswith("**Descartado:**"):
                stale.append(f"{path.relative_to(ROOT)}: {line}")
    assert not stale, f"menciones desactualizadas a text-embedding-004: {stale}"


def test_contract_document_prefixes_match_the_golden_set() -> None:
    """Los prefijos que el contrato exige a la ingesta son los que asertan los casos RAG (D55)."""
    source = (ROOT / "tests" / "golden_set.py").read_text(encoding="utf-8")
    prefixes = set(re.findall(r'_document\("([^"]+)"\)', source))
    assert prefixes, "golden_set.py no compara documentos por prefijo"
    block = _contract_block()
    missing = {prefix for prefix in prefixes if prefix not in block}
    assert not missing, f"el contrato no fija el prefijo {sorted(missing)} que aserta el golden set"


# ---------------------------------------------------------------- integration (base local, solo lectura)


def _ro_connection():
    """Conexión con el rol de solo lectura, como en `tests/test_runs_integration.py`.

    El import es diferido: la parte offline de este archivo corre en una máquina limpia (Art. 6).
    """
    psycopg2 = pytest.importorskip("psycopg2")

    cfg = load_config()
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        pytest.skip("POSTGRES_PASSWORD no está definida en .env")
    try:
        conn = psycopg2.connect(dbname=cfg.db_name, user=cfg.db_user, host=cfg.db_host, port=cfg.db_port,
                                password=password, connect_timeout=3)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"sin base de datos local (docker compose up -d): {exc}")
    conn.set_session(readonly=True)
    return conn


@pytest.fixture()
def ro_cursor():
    conn = _ro_connection()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.xfail(
    reason="con DEV_SEED=1 (dev_seed.sql) las tablas tienen menos de 15 filas; con seed.sql se cumple",
    strict=False,
)
def test_volume_min_rows_per_domain_table(ro_cursor) -> None:
    """T2.5: >= 15 filas en cada tabla del dominio. Se cumple con db/seed.sql; con db/dev_seed.sql no.
    """
    counts: dict[str, int] = {}
    for table in DOMAIN_TABLES:
        ro_cursor.execute(f"SELECT count(*) FROM {table}")  # nombres de una constante fija
        counts[table] = ro_cursor.fetchone()[0]
    short = {table: count for table, count in counts.items() if count < MIN_ROWS}
    assert not short, f"volumen insuficiente (T2.5): {sorted(short.items())}; conteo completo {sorted(counts.items())}"


@pytest.mark.integration
def test_available_copies_never_exceed_total(ro_cursor) -> None:
    """T2.7, primera regla: `ejemplares_disponibles <= ejemplares_totales`."""
    ro_cursor.execute(
        "SELECT id, titulo, ejemplares_totales, ejemplares_disponibles FROM libros "
        "WHERE ejemplares_disponibles > ejemplares_totales ORDER BY id"
    )
    assert ro_cursor.fetchall() == []


@pytest.mark.integration
def test_every_overdue_loan_satisfies_the_overdue_rule(ro_cursor) -> None:
    """T2.7, segunda regla: el vencimiento se calcula, no se escribe (D7, R-3.12)."""
    ro_cursor.execute(
        "SELECT id FROM v_prestamos_estado "
        "WHERE estado_calculado = 'vencido' "
        "AND NOT (fecha_devolucion_real IS NULL AND CURRENT_DATE > fecha_devolucion_prevista) ORDER BY id"
    )
    assert ro_cursor.fetchall() == []


@pytest.mark.integration
def test_agent_ro_can_read_the_document_tables(ro_cursor) -> None:
    """El contrato (§3.4.1) exige SELECT sobre `documentos` y `documentos_chunks` para el JOIN de la tool."""
    for table in sorted(DOCUMENT_TABLES):
        ro_cursor.execute("SELECT has_table_privilege(('public.' || %s)::regclass, 'SELECT')", (table,))
        assert ro_cursor.fetchone()[0], f"agent_ro no tiene SELECT sobre {table}"
