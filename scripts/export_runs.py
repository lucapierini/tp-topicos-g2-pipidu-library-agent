"""Exporta `agent_runs` a un JSON versionable en `TP/evidencia/` (T7.7; R-6.1, R-6.2, R-6.5).

La tabla no es una evidencia durable: `pytest -m integration` la trunca. El informe exige "capturas,
logs" y las 13 consultas del golden set; este script las vuelca a un archivo del repo, con el modelo y el
endpoint de cada corrida para que una corrida local no se confunda con evidencia de aceptación (R-2.8).

Lee con el rol administrador (`POSTGRES_ADMIN_USER` / `POSTGRES_ADMIN_PASSWORD`, del `.env`): ni
`agent_ro` ni `agent_logger` pueden leer la tabla a propósito (D21, D63).

Uso (después de `scripts/measure_golden.py --db`, **antes** de `pytest -m integration`):

    .venv/Scripts/python scripts/export_runs.py --last 13 [--out TP/evidencia/agent_runs_<fecha>.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.config import load_config  # noqa: E402


def fetch_runs(conn, last: int | None = None) -> list[dict]:
    """Filas de `agent_runs` en orden cronológico; `last=N` toma las N más recientes."""
    if last is None:
        sql, params = "SELECT * FROM agent_runs ORDER BY id", None
    else:
        sql = ("SELECT * FROM (SELECT * FROM agent_runs ORDER BY id DESC LIMIT %s) latest "
               "ORDER BY id")
        params = (int(last),)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.rollback()
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_payload(runs: list[dict]) -> dict:
    if not runs:
        raise ValueError(
            "agent_runs está vacía: no hay nada que exportar (¿se truncó con pytest -m integration?)"
        )
    return {
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "count": len(runs),
        "by_classification": dict(Counter(r["classification"] for r in runs)),
        "by_status": dict(Counter(r["status"] for r in runs)),
        "models": sorted({r["model_id"] for r in runs}),
        "endpoints": sorted({r["endpoint"] for r in runs}),
        # R-2.8, R-6.5: una corrida contra un servidor local valida el flujo, no la aceptación.
        "counts_as_acceptance_evidence": all(r["endpoint"] == "api" for r in runs),
        "runs": [{key: _jsonable(value) for key, value in run.items()} for run in runs],
    }


def write_payload(payload: dict, out: Path) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _connect():
    import psycopg2  # diferido: los tests offline no requieren el paquete

    cfg = load_config()
    password = os.environ.get("POSTGRES_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("POSTGRES_ADMIN_PASSWORD no está definida en .env (Art. 9: no va en el código)")
    return psycopg2.connect(
        dbname=cfg.db_name, user=os.environ.get("POSTGRES_ADMIN_USER", "postgres"),
        host=cfg.db_host, port=cfg.db_port, password=password, connect_timeout=5,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last", type=int, help="solo las N consultas más recientes (p. ej. 13)")
    parser.add_argument("--out", help="archivo de salida (por defecto TP/evidencia/agent_runs_<fecha>.json)")
    args = parser.parse_args()

    conn = _connect()
    try:
        payload = build_payload(fetch_runs(conn, last=args.last))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        conn.close()

    default_name = f"agent_runs_{date.today().isoformat()}.json"
    out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "TP" / "evidencia" / default_name
    write_payload(payload, out)
    print(f"{payload['count']} consultas exportadas a {out}")
    print(f"clasificación: {payload['by_classification']} | estado: {payload['by_status']}")
    print(f"modelos: {payload['models']} | endpoint: {payload['endpoints']} | "
          f"cuenta como aceptación: {payload['counts_as_acceptance_evidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
