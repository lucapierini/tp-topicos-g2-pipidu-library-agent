#!/bin/bash
# Inicialización de la base local (se ejecuta UNA vez, al crear el volumen).
#
# Orden: extensión y roles -> esquema -> agent_runs -> permisos -> datos de desarrollo (opcional).
# Las contraseñas llegan por variables de entorno (Art. 9): ninguna está en el repo.
# Los permisos sobre las tablas del dominio se conceden DESPUÉS de crear el esquema
# (db/post_restore.sql), porque las tablas no existen cuando se crean los roles.
set -euo pipefail

: "${AGENT_RO_PASSWORD:?falta AGENT_RO_PASSWORD}"
: "${AGENT_LOGGER_PASSWORD:?falta AGENT_LOGGER_PASSWORD}"

PSQL=(psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB")

# `-v` + `:'var'` entrecomilla el valor como literal: una contraseña con comillas no inyecta SQL.
"${PSQL[@]}" -v ro_password="$AGENT_RO_PASSWORD" -v logger_password="$AGENT_LOGGER_PASSWORD" <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS vector;

CREATE ROLE agent_ro LOGIN PASSWORD :'ro_password';
ALTER ROLE agent_ro SET statement_timeout = '10s';
ALTER ROLE agent_ro SET search_path = public;
ALTER ROLE agent_ro SET default_transaction_read_only = on;

CREATE ROLE agent_logger LOGIN PASSWORD :'logger_password';
ALTER ROLE agent_logger SET search_path = public;
EOSQL

echo "[init] esquema del dominio"
"${PSQL[@]}" -f /schema.sql

echo "[init] agent_runs (T7.4)"
"${PSQL[@]}" -f /migrations/001_agent_runs.sql

echo "[init] permisos de agent_ro"
"${PSQL[@]}" -f /post_restore.sql

if [[ "${DEV_SEED:-1}" == "1" ]]; then
  echo "[init] datos de desarrollo (db/dev_seed.sql)"
  "${PSQL[@]}" -f /dev_seed.sql
fi
