"""Configuración central del agente.

Ningún valor de comportamiento queda hardcodeado en el código (T2.3, D6, D12, D15).
Todos se leen de variables de entorno con defaults explícitos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


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

    # Orquestador (D15)
    max_steps: int
    temperature: float
    api_timeout_s: int
    model: str

    # Embeddings (D5)
    embedding_model: str
    embedding_dim: int


def load_config() -> Config:
    return Config(
        cuatrimestre_start=_env_date("CUATRIMESTRE_START", "2026-08-01"),
        cuatrimestre_end=_env_date("CUATRIMESTRE_END", "2026-11-30"),
        timezone=_env("TZ", "America/Argentina/Buenos_Aires"),
        top_k=_env_int("RAG_TOP_K", "5"),
        similarity_threshold=_env_float("RAG_SIMILARITY_THRESHOLD", "0.35"),
        max_rows=_env_int("SQL_MAX_ROWS", "50"),
        statement_timeout_ms=_env_int("SQL_STATEMENT_TIMEOUT_MS", "10000"),
        max_sql_attempts=_env_int("SQL_MAX_ATTEMPTS", "2"),
        max_steps=_env_int("AGENT_MAX_STEPS", "6"),
        temperature=_env_float("AGENT_TEMPERATURE", "0"),
        api_timeout_s=_env_int("AGENT_API_TIMEOUT_S", "30"),
        model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
        embedding_model=_env("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        embedding_dim=_env_int("EMBEDDING_DIM", "768"),
    )
