# Imagen del agente (T9.2, D74, D81). Se construye desde la raíz del repo:
#
#   docker build -f docker/Dockerfile -t pipidu-agent .                   # runtime (por defecto)
#   docker build -f docker/Dockerfile --target measure -t pipidu-measure . # + scripts de medición
#
# No lleva secretos: GEMINI_API_KEY y POSTGRES_* se inyectan en tiempo de ejecución con variables de
# entorno o `docker run --env-file .env` (Art. 9). El `.env` queda fuera del contexto (`.dockerignore`).

# --- base: Python 3.12 (el código usa sintaxis de 3.12) + dependencias de ejecución -----------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Solo las dependencias de ejecución, con cotas (Art. 8): pytest, faker y ruff no entran.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Usuario sin privilegios: el agente solo lee la base y llama a la API.
RUN useradd --create-home --uid 10001 agent
COPY agent/ agent/
USER agent

# --- measure: agrega los scripts de medición y lo que importan (dobles y golden set) ----------------
# `scripts/measure_golden.py` y `scripts/export_runs.py` no son parte del servicio: esta etapa existe
# para correr la validación dentro de la imagen, no para correr el servicio.
FROM base AS measure
USER root
COPY scripts/ scripts/
COPY tests/ tests/
RUN chown -R agent:agent /app
USER agent
CMD ["python", "scripts/measure_golden.py", "--help"]

# --- runtime: lo que se ejecuta (última etapa = destino por defecto) ------------------------------
# Un solo servicio: la API HTTP del agente (D80). El frontend (`web/`, D84) es un cliente de la API con
# su propia imagen (`docker/Dockerfile.web`); esta imagen no sirve ninguna interfaz gráfica.
FROM base AS runtime
COPY api/ api/
ENV PORT=8080
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT}"]
