#!/usr/bin/env bash
# Replica la base de Neon en el contenedor local (T1.3, T2.x).
#
#   NEON_DATABASE_URL=postgresql://usuario:clave@ep-xxx.<region>.aws.neon.tech/<db>?sslmode=require
#
# La URL se lee del entorno o de `.env` (gitignoreado). Nunca se imprime ni se escribe en el repo
# (Art. 9). Solo LEE de Neon (`pg_dump`): no modifica la base compartida.
#
# Uso:  bash scripts/replicate_neon.sh [--check]
#   --check   solo informa la versión de Neon y qué imagen usar; no vuelca ni restaura.
#
# No requiere `pg_dump` ni `psql` instalados: corre dentro de contenedores.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- URL de Neon: entorno o .env, sin imprimirla ------------------------------------------------
if [[ -z "${NEON_DATABASE_URL:-}" && -f .env ]]; then
  # `|| true`: sin esa línea en .env, `grep` sale con 1 y `set -e` cortaba el script sin decir nada.
  NEON_DATABASE_URL="$(grep -E '^NEON_DATABASE_URL=' .env | head -1 | cut -d= -f2- | tr -d '\r' \
    | sed -e 's/^"//' -e 's/"$//' || true)"
fi
if [[ -z "${NEON_DATABASE_URL:-}" ]]; then
  echo "Falta NEON_DATABASE_URL: definila en .env (copiá la connection string desde el panel de Neon)." >&2
  exit 2
fi

# `--env` pasa la variable al contenedor sin que aparezca en la línea de comandos ni en el historial.
export NEON_DATABASE_URL
psql_neon() { docker run --rm --env NEON_DATABASE_URL postgres:17 sh -c 'psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 "$@"' sh "$@"; }

echo "→ consultando la versión de PostgreSQL de Neon…"
VERSION_NUM="$(psql_neon -Atc 'SHOW server_version_num' | tr -d '\r')"
MAJOR=$(( VERSION_NUM / 10000 ))
echo "  Neon usa PostgreSQL ${MAJOR}."

IMAGE="pgvector/pgvector:pg${MAJOR}"
echo "  Imagen local recomendada: PG_IMAGE=${IMAGE}"

if [[ "${1:-}" == "--check" ]]; then
  echo "→ extensiones y tablas en Neon:"
  psql_neon -c "SELECT extname, extversion FROM pg_extension ORDER BY 1" -c "\dt public.*" -c "\dv public.*"
  exit 0
fi

mkdir -p db/dumps
DUMP="db/dumps/neon_$(date +%Y%m%d_%H%M%S).sql"

echo "→ volcando esquema y datos de Neon (solo lectura)…"
# --no-owner/--no-privileges: los roles de Neon no existen localmente; los permisos los da post_restore.sql.
docker run --rm --env NEON_DATABASE_URL "postgres:${MAJOR}" \
  sh -c 'pg_dump "$NEON_DATABASE_URL" --schema=public --no-owner --no-privileges --format=plain' > "$DUMP"
echo "  volcado en ${DUMP} ($(wc -c < "$DUMP") bytes)"

echo "→ levantando la base local (${IMAGE})…"
PG_IMAGE="$IMAGE" docker compose up -d --wait db

CONTAINER="pipidu-db"
DB_NAME="${POSTGRES_DB:-pipidu}"

echo "→ recreando el esquema public y restaurando…"
docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -v ON_ERROR_STOP=1 \
  -c 'DROP SCHEMA IF EXISTS public CASCADE' -c 'CREATE SCHEMA public' -c 'CREATE EXTENSION IF NOT EXISTS vector'
docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -v ON_ERROR_STOP=1 < "$DUMP"

echo "→ permisos de agent_ro y tabla agent_runs…"
docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -v ON_ERROR_STOP=1 < db/migrations/001_agent_runs.sql
docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -v ON_ERROR_STOP=1 < db/post_restore.sql

echo "→ conteo por tabla:"
docker exec -i "$CONTAINER" psql -U postgres -d "$DB_NAME" -At -c \
  "SELECT relname || ': ' || n_live_tup FROM pg_stat_user_tables ORDER BY relname"
echo "Listo. Probá con:  .venv/Scripts/python -m pytest -m integration"
