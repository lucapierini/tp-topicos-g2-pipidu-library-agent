"""Configuración central del agente.

Ningún valor de comportamiento queda hardcodeado en el código (T2.3, D6, D12, D15).
Todos se leen de variables de entorno con defaults explícitos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv es dependencia de desarrollo
    load_dotenv = None

# Path explícito: `find_dotenv()` falla al ejecutar desde stdin o desde otro cwd.
# `.env` está en .gitignore (Art. 9). `override=False`: el entorno real gana sobre el archivo.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

if load_dotenv is not None:
    load_dotenv(ENV_FILE, override=False)


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_date(name: str, default: str) -> date:
    return date.fromisoformat(os.environ.get(name, default))


@dataclass(frozen=True)
class Config:
    # Semántica temporal (D6, R-3.11)
    cuatrimestre_start: date
    cuatrimestre_end: date
    timezone: str

    # RAG (D12, R-4.4, R-4.8)
    top_k: int
    similarity_threshold: float

    # Herramienta SQL (R-3.6, D8, D15)
    max_rows: int
    statement_timeout_ms: int
    max_sql_attempts: int
    max_table_refs: int  # R-3.17: cota de complejidad (producto cartesiano accidental)

    # Orquestador (D15)
    max_steps: int
    temperature: float
    api_timeout_s: int
    api_max_retries: int  # reintentos ante 429 (cuota gratuita); ver agent/retry.py
    model: str
    # Proveedor del LLM en formato LiteLLM (`gemini/<modelo>`, `openai/<modelo>` + `llm_api_base` para
    # un servidor local OpenAI-compatible). Por defecto, Gemini con `GEMINI_MODEL`: cambiar de proveedor
    # es configuración, no código (D56).
    llm_model: str
    llm_api_base: str

    # Embeddings (D5)
    embedding_model: str
    embedding_dim: int

    # Conexión (R-3.5, D14). El rol es de solo lectura; la contraseña se lee del entorno (Art. 9).
    db_user: str
    # Rol que escribe `agent_runs` (solo INSERT). Distinto de `db_user`, que es de solo lectura (R-3.5).
    log_db_user: str
    # Dónde se registra cada consulta (R-6.2): `pg`, `memory` (mediciones y tests) u `off`.
    runs_backend: str
    db_name: str
    db_host: str
    db_port: int
    # `require` para Neon (TLS obligatorio); vacío = el valor por defecto de libpq (base local).
    db_sslmode: str


def load_config() -> Config:
    gemini_model = _env("GEMINI_MODEL", "gemini-3.1-flash-lite")
    return Config(
        cuatrimestre_start=_env_date("CUATRIMESTRE_START", "2026-08-01"),
        cuatrimestre_end=_env_date("CUATRIMESTRE_END", "2026-11-30"),
        # `APP_TIMEZONE` y no `TZ`: `TZ` es una variable estándar del sistema (Cloud Run la fija
        # en UTC) y el cuatrimestre se razona en hora argentina (D6, D47).
        timezone=_env("APP_TIMEZONE", "America/Argentina/Buenos_Aires"),
        top_k=_env_int("RAG_TOP_K", "5"),
        similarity_threshold=_env_float("RAG_SIMILARITY_THRESHOLD", "0.67"),
        max_rows=_env_int("SQL_MAX_ROWS", "50"),
        statement_timeout_ms=_env_int("SQL_STATEMENT_TIMEOUT_MS", "10000"),
        max_sql_attempts=_env_int("SQL_MAX_ATTEMPTS", "2"),
        max_table_refs=_env_int("SQL_MAX_TABLE_REFS", "8"),
        max_steps=_env_int("AGENT_MAX_STEPS", "6"),
        temperature=_env_float("AGENT_TEMPERATURE", "0"),
        api_timeout_s=_env_int("AGENT_API_TIMEOUT_S", "30"),
        api_max_retries=_env_int("AGENT_API_MAX_RETRIES", "3"),
        model=gemini_model,
        # `or`: la plantilla `.env.example` deja `LLM_MODEL=` vacío y un vacío significa "no definido".
        llm_model=os.environ.get("LLM_MODEL") or f"gemini/{gemini_model}",
        llm_api_base=_env("LLM_API_BASE", ""),
        embedding_model=_env("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        embedding_dim=_env_int("EMBEDDING_DIM", "768"),
        db_user=_env("POSTGRES_USER", "agent_ro"),
        log_db_user=_env("POSTGRES_LOG_USER", "agent_logger"),
        runs_backend=os.environ.get("AGENT_RUNS_BACKEND") or "pg",
        db_name=_env("POSTGRES_DB", "pipidu"),
        # `127.0.0.1` y no `localhost`: en Windows `localhost` intenta primero IPv6 y cada conexión pierde
        # ~2 s (medido); Docker publica el puerto solo en IPv4 loopback.
        db_host=_env("POSTGRES_HOST", "127.0.0.1"),
        db_port=_env_int("POSTGRES_PORT", "5432"),
        db_sslmode=os.environ.get("POSTGRES_SSLMODE", ""),
    )
