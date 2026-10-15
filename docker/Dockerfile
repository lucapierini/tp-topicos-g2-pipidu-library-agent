# Imagen del agente (T9.2, D18). Se construye desde la raíz del repo:
#
#   docker build -f docker/Dockerfile -t pipidu-agent .                   # runtime (por defecto)
#   docker build -f docker/Dockerfile --target measure -t pipidu-measure . # + scripts de medición
#   docker build -f docker/Dockerfile --target local -t pipidu-local .     # + ingesta del RAG (docker compose)
#
# No lleva secretos: GEMINI_API_KEY y POSTGRES_* se inyectan en tiempo de ejecución (Art. 9; en
# Cloud Run, desde Secret Manager). El `.env` queda fuera del contexto (`.dockerignore`).

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
# para correr la validación dentro de la imagen, no para desplegarla.
FROM base AS measure
USER root
COPY scripts/ scripts/
COPY tests/ tests/
RUN chown -R agent:agent /app
USER agent
CMD ["python", "scripts/measure_golden.py", "--help"]

# --- local: todo lo necesario para correr la infraestructura con `docker compose` ---------------------
# Agrega la ingesta del RAG y sus documentos a la etapa `measure` (que ya trae scripts/ask.py y tests/).
# Es la imagen de los servicios `agent` e `ingest` de docker-compose.yml: no se despliega.
FROM measure AS local
USER root
COPY rag/ingest.py rag/ingest.py
COPY rag/documents/ rag/documents/
RUN chown -R agent:agent /app
USER agent
ENTRYPOINT ["python"]
CMD ["scripts/ask.py"]

# --- runtime: lo que se despliega (última etapa = destino por defecto) ------------------------------
# Todavía no hay UI (tarea 8.1): hasta entonces la imagen solo verifica que el agente importa. Cuando
# exista `ui/app.py`, agregar `COPY ui/ ui/` y reemplazar el CMD por:
#   CMD ["sh", "-c", "streamlit run ui/app.py --server.port=${PORT:-8080} --server.address=0.0.0.0"]
FROM base AS runtime
CMD ["python", "-c", "import agent.agent; print('agent importable')"]
