"""Re-ranking de los fragmentos candidatos del RAG con el modelo (R-4.11, D100).

La similitud de coseno mide cercanía temática, no que el fragmento *conteste*: «¿me puedo conectar al wifi con mi
legajo?» puntúa 0.70 contra el reglamento aunque ningún documento hable de wifi. El re-ranking le pregunta al modelo,
para cada uno de los candidatos, si **contiene** lo que se pide (0 = nada, 1 = mismo tema, 2 = parte de la respuesta,
3 = la contesta). El puntaje de la consulta combina esa relevancia con la similitud (el coseno desempata):

    puntaje = 0.7 * (mejor relevancia / 3) + 0.3 * coseno_normalizado

Medido con 126 consultas de calibración y 63 de validación fuera de muestra (`scripts/evaluate_retrieval.py`), llevó
el AUC de 0.912 a 0.986 y los falsos positivos de 9/28 a 1/28 sobre la validación.

Una llamada al modelo por consulta documental, con temperatura 0 y salida estructurada validada.
"""
from __future__ import annotations

import json
import os
import time
from typing import Protocol

from agent.config import Config, load_config
from agent.retry import call_with_retry

RERANK_MAX = 3                      # escala del re-ranking: 0 = no se relaciona … 3 = contesta directo
DENSE_LOW, DENSE_HIGH = 0.50, 0.85  # rango observado del coseno: se lleva a [0, 1] antes de combinar
DENSE_WEIGHT = 0.3                  # peso del coseno; el de la relevancia es 1 - DENSE_WEIGHT

# (documento, ubicación, texto) de cada fragmento candidato
Item = tuple[str, str, str]

SYSTEM_PROMPT = """Sos un evaluador de relevancia para un buscador de documentos de una biblioteca universitaria.
Dada una pregunta y unos fragmentos numerados, puntuá cada fragmento de 0 a 3 según si CONTIENE la información que
la pregunta pide:

0 = no tiene relación con la pregunta.
1 = es del mismo tema general, pero no contiene lo que se pregunta.
2 = contiene parte de la respuesta.
3 = contesta la pregunta de forma directa.

Compartir el tema o el vocabulario (biblioteca, salas, libros, préstamos) NO alcanza para más de 1: hay que
encontrar el dato pedido. No inventes ni supongas lo que no está escrito. Devolvé solo JSON:
{"scores": [<un entero por fragmento, en el mismo orden>]}"""


class Reranker(Protocol):
    def relevances(self, question: str, items: list[Item]) -> list[int]: ...


# --------------------------------------------------------------------------- puro


def normalize_dense(similarity: float) -> float:
    return min(1.0, max(0.0, (similarity - DENSE_LOW) / (DENSE_HIGH - DENSE_LOW)))


def build_prompt(question: str, items: list[Item]) -> str:
    body = "\n\n".join(f"[{i}] ({doc}, {loc})\n{text}" for i, (doc, loc, text) in enumerate(items))
    return f"Pregunta: {question}\n\nFragmentos:\n\n{body}"


def parse_relevance(raw: str | None, n: int) -> list[int]:
    """Valida la salida: `n` enteros en 0..RERANK_MAX; cualquier otra cosa es un error."""
    try:
        data = json.loads(raw or "")
        scores = [int(round(float(s))) for s in data["scores"]]
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"salida de re-ranking inválida: {exc}") from exc
    if len(scores) != n:
        raise ValueError(f"se esperaban {n} puntajes y llegaron {len(scores)}")
    return [min(RERANK_MAX, max(0, s)) for s in scores]


def rerank_score(relevances: list[int]) -> float:
    return max(relevances) / RERANK_MAX if relevances else 0.0


def combined_score(relevances: list[int], best_similarity: float, dense_weight: float = DENSE_WEIGHT) -> float:
    """La relevancia manda; la similitud desempata entre consultas con la misma relevancia."""
    return (1 - dense_weight) * rerank_score(relevances) + dense_weight * normalize_dense(best_similarity)


# --------------------------------------------------------------------------- modelo


class GeminiReranker:
    """Una llamada a Gemini por consulta. `call_with_retry` cubre la cuota (429); acá se suman los 5xx transitorios."""

    TRANSIENT_ATTEMPTS = 8

    def __init__(self, config: Config | None = None, client=None) -> None:
        self.cfg = config or load_config()
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("GEMINI_API_KEY no está definida (Art. 9: se lee del entorno)")
            self._client = genai.Client(
                api_key=key, http_options=types.HttpOptions(timeout=self.cfg.api_timeout_s * 1000)
            )
        return self._client

    def _generate(self, client, prompt: str, config):
        for attempt in range(self.TRANSIENT_ATTEMPTS):
            try:
                return call_with_retry(
                    lambda: client.models.generate_content(model=self.cfg.model, contents=prompt, config=config),
                    retries=self.cfg.api_max_retries,
                )
            except Exception as exc:  # noqa: BLE001
                code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if not (isinstance(code, int) and 500 <= code < 600) or attempt == self.TRANSIENT_ATTEMPTS - 1:
                    raise
                time.sleep(min(60, 5 * 2 ** attempt))

    def relevances(self, question: str, items: list[Item]) -> list[int]:
        from google.genai import types

        client = self._get_client()  # en una variable: encadenarlo cierra el httpx (D37)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, temperature=0, response_mime_type="application/json",
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={"scores": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.INTEGER))},
                required=["scores"],
            ),
        )
        response = self._generate(client, build_prompt(question, items), config)
        return parse_relevance(response.text, len(items))
