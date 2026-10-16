"""Prueba qué modelos de Gemini aceptan la clasificación con esquema JSON forzado (D50, D71).

Llama a la API real una vez por modelo con una pregunta del dominio y un `response_schema`
`{classification, question}`; imprime el JSON devuelto o el error. No escribe archivos ni abre base.

Requiere `GEMINI_API_KEY`: `.env` se carga con `load_dotenv` al importar `agent.config`.

    .venv/Scripts/python scripts/probe_llm.py
"""
import json
import os

from google import genai
from google.genai import types

from agent.config import ENV_FILE  # carga `.env` con path explícito
from agent.contracts import CLASSIFICATIONS

assert ENV_FILE  # el import ya ejecutó load_dotenv(ENV_FILE)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

schema = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "classification": types.Schema(type=types.Type.STRING, enum=sorted(CLASSIFICATIONS)),
        "question": types.Schema(type=types.Type.STRING),
    },
    required=["classification", "question"],
)

for model in ("gemini-3-flash-preview", "gemini-3.8-flash"):
    try:
        r = client.models.generate_content(
            model=model,
            contents="¿Cuántos libros tiene la biblioteca?",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        print(model, "->", json.dumps(json.loads(r.text), ensure_ascii=False))
    except Exception as e:
        print(model, "->", type(e).__name__, str(e)[:160])
