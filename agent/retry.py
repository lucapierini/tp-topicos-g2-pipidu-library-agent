"""Reintento ante límite de cuota (429) de las APIs de Gemini.

La cuenta gratuita permite unas pocas requests por minuto y la API informa cuánto esperar
(`Please retry in 17.9s`). Reintentar respetando esa espera, con un tope, es mejor que fallar la
consulta: pero sin pasarse de `AGENT_API_TIMEOUT_S` por llamada (Art. 7) ni reintentar errores que
no son de cuota (una clave inválida no mejora esperando).
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable

_RETRY_IN = re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE)
MAX_WAIT_S = 60.0


def is_rate_limited(exc: BaseException) -> bool:
    """429 / RESOURCE_EXHAUSTED, sin depender de la clase concreta de `google-genai` o `litellm`."""
    if getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429:
        return True
    text = str(exc)
    return "429" in text and "RESOURCE_EXHAUSTED" in text.upper() or "rate limit" in text.lower()


def retry_delay(exc: BaseException, attempt: int) -> float:
    """Lo que pide la API; si no lo dice, backoff exponencial. Siempre acotado."""
    match = _RETRY_IN.search(str(exc))
    wait = float(match.group(1)) + 1.0 if match else 2.0 ** (attempt + 1)
    return min(wait, MAX_WAIT_S)


def call_with_retry[T](
    fn: Callable[[], T], *, retries: int, sleep: Callable[[float], None] | None = None
) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if attempt >= retries or not is_rate_limited(exc):
                raise
            (sleep or time.sleep)(retry_delay(exc, attempt))  # resuelto al llamar: es parcheable
            attempt += 1
