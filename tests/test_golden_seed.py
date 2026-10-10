"""El seed contiene las entidades que el golden set nombra (T2.x, G1–G13).

Marcado `integration`: se salta si no hay base. Sin esto, un caso G1–G5 que falla por falta de
datos se confunde con un fallo del agente.
"""
from __future__ import annotations

import os

import pytest

from agent.config import load_config
from tests.golden_set import SEED_ENTITIES

pytestmark = pytest.mark.integration


@pytest.fixture()
def cursor():
    psycopg2 = pytest.importorskip("psycopg2")

    cfg = load_config()
    try:
        conn = psycopg2.connect(
            dbname=cfg.db_name, user=cfg.db_user, host=cfg.db_host, port=cfg.db_port,
            password=os.environ.get("POSTGRES_PASSWORD"), connect_timeout=3,
        )
    except psycopg2.OperationalError as exc:
        pytest.skip(f"sin base de datos: {exc}")
    conn.set_session(readonly=True)
    with conn.cursor() as cur:
        yield cur
    conn.close()


def _exists(cur, sql: str, *params) -> bool:
    cur.execute(sql, params)
    return cur.fetchone() is not None


def test_socio_del_golden_set_existe(cursor) -> None:
    assert _exists(
        cursor, "SELECT 1 FROM socios WHERE nombre = %s AND apellido = %s LIMIT 1",
        SEED_ENTITIES["socio_nombre"], SEED_ENTITIES["socio_apellido"],
    )


def test_categoria_y_editorial_del_golden_set_existen(cursor) -> None:
    assert _exists(cursor, "SELECT 1 FROM categorias WHERE nombre = %s LIMIT 1", SEED_ENTITIES["categoria"])
    assert _exists(cursor, "SELECT 1 FROM editoriales WHERE nombre = %s LIMIT 1", SEED_ENTITIES["editorial"])


def test_los_libros_del_golden_set_existen(cursor) -> None:
    for key in ("libro_con_resena", "libro_sin_precio"):
        assert _exists(cursor, "SELECT 1 FROM libros WHERE titulo = %s LIMIT 1", SEED_ENTITIES[key]), key


def test_hay_al_menos_un_prestamo_vencido_para_g3(cursor) -> None:
    assert _exists(cursor, "SELECT 1 FROM v_prestamos_estado WHERE estado_calculado = 'vencido' LIMIT 1")
