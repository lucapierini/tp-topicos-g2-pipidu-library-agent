"""Smoke test de API (R-2.7, D5).

Marcado `llm`: se deselecciona por defecto y se corre con `pytest -m llm`.
Necesita `GEMINI_API_KEY` en `.env` (Art. 9).
"""
from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.llm

pytest.importorskip("google.genai")
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from agent.config import load_config  # noqa: E402


def client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY no está definida (Art. 9: se lee del entorno)")
    return genai.Client(api_key=key)


def test_clasificacion_estructurada_devuelve_el_enum() -> None:
    # R-2.7: la clasificación se emite como salida estructurada antes de invocar la tool.
    cfg = load_config()
    # El cliente se mantiene en una variable: `genai.Client(...).models.generate_content(...)`
    # lo recolecta antes de la llamada y el httpx queda cerrado (el `__del__` de Client lo cierra).
    c = client()
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "classification": types.Schema(
                type=types.Type.STRING, enum=["sql", "rag", "sql+rag", "none"]
            ),
            "question": types.Schema(type=types.Type.STRING),
        },
        required=["classification", "question"],
    )
    r = c.models.generate_content(
        model=cfg.model,
        contents="¿Cuántos libros tiene la biblioteca?",
        config=types.GenerateContentConfig(
            temperature=cfg.temperature,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    out = json.loads(r.text)
    assert out["classification"] == "sql"
    assert out["question"]


def test_embedding_con_768_dimensiones() -> None:
    # D5: define vector(768) en documentos_embeddings.
    cfg = load_config()
    c = client()
    e = c.models.embed_content(
        model=cfg.embedding_model,
        contents="prueba de dimensión",
        config=types.EmbedContentConfig(output_dimensionality=cfg.embedding_dim),
    )
    assert len(e.embeddings[0].values) == cfg.embedding_dim
