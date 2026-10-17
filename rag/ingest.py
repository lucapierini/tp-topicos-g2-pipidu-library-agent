"""Ingesta del RAG: documentos fuente -> `documentos` y `documentos_chunks` en la base local de Docker, donde
la corre `docker compose` (D19, R-4.7).

Para cada `rag/documents/*.md` (el PDF de `rag/documents/pdf/` se genera con su mismo texto, R-9.5):
1. se parte por secciones `## ...` (artículos o pasos numerados), que son lo que se cita;
2. cada fragmento se embebe con `RETRIEVAL_DOCUMENT`, 768 dimensiones, normalizado (D5, D13);
3. se guarda con `metadata.seccion` para que la respuesta pueda decir "Art. 2" (R-4.7).

Escribe, así que usa el dueño de la base. Destino, en este orden (Art. 9: nunca un literal en el repo):
`INGEST_DATABASE_URL` (del entorno o de `.env`) o las variables `PG*` de libpq
(así lo usa docker compose contra la base local). El agente en ejecución NO usa esta conexión: lee con `agent_ro`.

Es idempotente: si el `sha256` del PDF no cambió y la base ya tiene esa cantidad de fragmentos, se saltea
(`--force` lo rehace).
La carpeta `rag/documents/` es la fuente de verdad: los documentos ausentes de la carpeta se borran
de la base (`--keep-orphans` lo evita).

    python rag/ingest.py --dry-run     # muestra los fragmentos; sin red ni base
    python rag/ingest.py               # ingesta
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

DOCS_DIR = ROOT / "documents"
PDF_DIR = DOCS_DIR / "pdf"
BUCKET_PREFIX = "documents/"
EMBED_BATCH = 20

# prefijo del archivo -> `documentos.tipo` (CHECK documentos_tipo_ck)
TIPOS = {
    "reglamento": "reglamento",
    "manual": "manual",
    "politicas": "politica",
    "resenas": "resena",
}


@dataclass
class Fragment:
    index: int
    seccion: str
    contenido: str


def tipo_de(stem: str) -> str:
    return TIPOS[stem.split("_", 1)[0]]


def split_sections(markdown: str) -> list[Fragment]:
    """Un fragmento por sección `## `. El título del documento se antepone para dar contexto al embedding."""
    lines = markdown.splitlines()
    title = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), "")
    sections: list[tuple[str, list[str]]] = []
    for ln in lines:
        if ln.startswith("## "):
            sections.append((ln[3:].strip(), []))
        elif sections:
            sections[-1][1].append(ln)
    fragments = []
    for name, body in sections:
        text = "\n".join(body).strip()
        if not text:
            continue
        fragments.append(
            Fragment(len(fragments), name, f"{title}\n## {name}\n\n{text}" if title else f"## {name}\n\n{text}")
        )
    return fragments


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


def embed_documents(texts: list[str], dim: int, model: str, timeout_s: int, retries: int) -> list[list[float]]:
    from google import genai
    from google.genai import types

    from agent.retry import call_with_retry

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("Falta GEMINI_API_KEY (Art. 9: se lee del entorno)")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=timeout_s * 1000))
    config = types.EmbedContentConfig(output_dimensionality=dim, task_type="RETRIEVAL_DOCUMENT")
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        response = call_with_retry(
            lambda b=batch: client.models.embed_content(model=model, contents=b, config=config), retries=retries
        )
        out.extend(_normalize(list(e.values)) for e in response.embeddings)
    return out


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT.parent / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="muestra los fragmentos sin embeber ni escribir")
    parser.add_argument("--force", action="store_true", help="rehace los documentos aunque no hayan cambiado")
    parser.add_argument("--keep-orphans", action="store_true",
                        help="no borra de la base los documentos que ya no están en rag/documents/")
    args = parser.parse_args()
    load_env()

    mds = sorted(DOCS_DIR.glob("*.md"))
    plan = []
    for md in mds:
        pdf = PDF_DIR / f"{md.stem}.pdf"
        if not pdf.exists():
            raise SystemExit(f"Falta {pdf.name}: generalo con rag/build_pdfs.py")
        plan.append((md, pdf, split_sections(md.read_text(encoding="utf-8"))))

    if args.dry_run:
        for md, pdf, frags in plan:
            print(f"{pdf.name} [{tipo_de(md.stem)}] {len(frags)} fragmentos")
            for f in frags:
                print(f"  {f.index:>2}  {f.seccion}  ({len(f.contenido)} car.)")
        print(f"total: {sum(len(p[2]) for p in plan)} fragmentos")
        return 0

    url = os.environ.get("INGEST_DATABASE_URL") or ""
    if not url and not os.environ.get("PGHOST"):
        raise SystemExit("Falta el destino: definí INGEST_DATABASE_URL o PGHOST")

    import psycopg2

    from agent.config import load_config

    cfg = load_config()
    conn = psycopg2.connect(url, connect_timeout=cfg.api_timeout_s)
    try:
        for md, pdf, frags in plan:
            sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT d.id, d.sha256, (SELECT count(*) FROM documentos_chunks c WHERE c.documento_id = d.id) "
                    "FROM documentos d WHERE d.nombre_archivo = %s",
                    (pdf.name,),
                )
                row = cur.fetchone()
            if row and row[1] == sha and row[2] == len(frags) and not args.force:
                print(f"= {pdf.name}: sin cambios ({row[2]} fragmentos)")
                continue

            vectors = embed_documents(
                [f.contenido for f in frags],
                cfg.embedding_dim,
                cfg.embedding_model,
                cfg.api_timeout_s,
                cfg.api_max_retries,
            )
            with conn.cursor() as cur:  # una transacción por documento: o queda completo o no cambia
                cur.execute(
                    "INSERT INTO documentos (nombre_archivo, tipo, bucket_key, sha256) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (nombre_archivo) DO UPDATE SET tipo = EXCLUDED.tipo, "
                    "bucket_key = EXCLUDED.bucket_key, sha256 = EXCLUDED.sha256 RETURNING id",
                    (pdf.name, tipo_de(md.stem), BUCKET_PREFIX + pdf.name, sha),
                )
                doc_id = cur.fetchone()[0]
                cur.execute("DELETE FROM documentos_chunks WHERE documento_id = %s", (doc_id,))
                for f, vec in zip(frags, vectors, strict=True):
                    cur.execute(
                        "INSERT INTO documentos_chunks (documento_id, chunk_index, contenido, embedding, metadata) "
                        "VALUES (%s, %s, %s, %s::vector, %s::jsonb)",
                        (
                            doc_id,
                            f.index,
                            f.contenido,
                            "[" + ",".join(repr(x) for x in vec) + "]",
                            '{"seccion": ' + json.dumps(f.seccion, ensure_ascii=False) + "}",
                        ),
                    )
            conn.commit()
            print(f"+ {pdf.name}: {len(frags)} fragmentos")

        if not args.keep_orphans:
            # La carpeta es la fuente de verdad: lo que ya no está se borra (los fragmentos caen en cascada).
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM documentos WHERE nombre_archivo <> ALL(%s) RETURNING nombre_archivo",
                    ([pdf.name for _, pdf, _ in plan],),
                )
                for (name,) in cur.fetchall():
                    print(f"- {name}: eliminado (ya no está en rag/documents/)")
            conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM documentos")
            docs = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM documentos_chunks")
            chunks = cur.fetchone()[0]
        print(f"En la base: {docs} documentos, {chunks} fragmentos")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
