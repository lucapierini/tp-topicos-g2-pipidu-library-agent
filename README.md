# Pipidu Library Agent

SQL AI Agent para un dominio de biblioteca universitaria. Recibe consultas en lenguaje natural
(castellano o inglés) y responde usando una base de datos relacional (SQL) y un repositorio documental
vía RAG, decidiendo autónomamente qué fuente consultar en cada caso.

**Materia:** Tópicos Avanzados de IA — Trabajo Práctico Integrador (AI Engineering), UCSE.
**Entrega:** 16/10/2026 23:59 (GMT-03) · **Coloquio:** 23/10 o 30/10/2026.

## Stack

Python 3.12+ · PostgreSQL + pgvector · Gemini · Smolagents · FastAPI · ejecución local (D81)

## Estructura

```
TP/            artefactos SDD (constitución, specs, validación, changelog, enunciado)
openspec/      raíz operativa de SDD (project.md, config.yaml, changes/)
db/            schema.sql, dev_seed.sql, migrations/, init/, post_restore.sql (+ seed_data.py, dump.sql: pendientes)
rag/           documents/ (PDFs), ingest.py, chunking.py (pendientes)
agent/         agent.py, classifier.py, contracts.py, errors.py, retry.py, runs.py, sql_validator.py,
               config/, prompts/, tools/ (sql_tool.py, rag_tool.py, smol_tools.py)
scripts/       measure_golden.py, measure_queue.py, export_runs.py, calibrate_threshold.py, probe_llm.py, replicate_neon.sh
api/           app.py (FastAPI: POST /ask con streaming SSE, GET /health): único acceso al agente
tests/         test_sql_tool.py, test_rag_tool.py, test_golden_set.py, test_agent.py, test_runs.py, ...
docker/        Dockerfile (etapas runtime y measure, verificado en T9.2 y T9.10)
docker-compose.yml   Postgres + pgvector local
```

## Estado

Etapa SDD completa (`Requirement → Spec → Plan → Tasks → Validation`). El agente y sus tools están
implementados (validador y executor de SQL, tool de RAG, clasificador, orquestador, `agent_runs`), junto
con la API HTTP con streaming de progreso y cancelación, que es el **único acceso** al agente: no hay
interfaz gráfica en este repositorio, el frontend es un cliente externo que la consume (D80). La
aceptación con el modelo definitivo está medida (T6.7, `gemini-3.1-flash-lite`, 13/13).
Pendiente: la ingesta de PDFs, el seed entregable y el informe. El sistema se ejecuta en entorno local
(D81). El detalle está en [`tasks.md`](openspec/changes/agente-y-tools/tasks.md).
El change activo es [`agente-y-tools`](openspec/changes/agente-y-tools/), validado con
`openspec validate --strict`.

## Instalación y ejecución

El flujo de arranque cubre hasta lo implementado. `seed` e `ingest` se agregan cuando existan
(T2.4, T3.3); la tarea 1.5 de `openspec/changes/agente-y-tools/tasks.md` sigue abierta por eso.

```bash
cp .env.example .env          # GEMINI_API_KEY y credenciales de BD
# Desarrollo sin cuota: apuntar a un servidor local OpenAI-compatible (R-2.8). Validar el flujo con
# LLM_MODEL=openai/<id> y LLM_API_BASE=http://127.0.0.1:<puerto>/v1; la aceptación se mide después con
# Gemini (dejar LLM_MODEL y LLM_API_BASE vacíos). Los resultados locales no cuentan como aceptación.
python scripts/measure_golden.py --out TP/evidencia/<corrida>.json   # mide R-2.1 con el modelo configurado
docker compose up -d --wait   # Postgres + pgvector + esquema + roles + agent_runs + datos de desarrollo
# (opcional) traer la base compartida de Neon: definir NEON_DATABASE_URL en .env y
bash scripts/replicate_neon.sh --check   # versión y objetos de Neon; sin --check vuelca y restaura
python -m pytest -m integration          # permisos por rol, esquema vs whitelist, flujo con datos reales
python scripts/measure_golden.py --db    # golden set contra la base local (registra en agent_runs)
python scripts/measure_golden.py --db --rag-mock   # + recuperación simulada: contenido de los 13 casos, sin PDFs
python scripts/measure_golden.py --db --rag-mock --bilingual   # + 2 casos en inglés (no cuentan para R-2.1)
python scripts/export_runs.py --last 15  # agent_runs -> TP/evidencia/ (antes de pytest -m integration, que la trunca)
uvicorn api.app:app --port 8000          # API del agente (único acceso); el frontend apunta a http://127.0.0.1:8000
# El frontend necesita su origen en `API_ALLOWED_ORIGINS` (.env), separado por comas; sin él, el
# navegador rechaza la respuesta (R-7.8, D82). Sin autenticación: el servicio corre en local (D81).
# Consulta de prueba (JSON en UTF-8; en Windows conviene un cliente HTTP en vez de curl por el cuoteo):
#   curl -N -X POST localhost:8000/ask -H "content-type: application/json" -d '{"question":"..."}'
docker build -f docker/Dockerfile -t pipidu-agent .                    # imagen del agente (etapa runtime)
docker build -f docker/Dockerfile --target measure -t pipidu-measure . # + scripts de medición (sin secretos)
# Corrida local (D81): solo se expone el puerto de la API ($PORT, 8080 por defecto).
# Dentro del contenedor, POSTGRES_HOST=127.0.0.1 de `.env` apunta al propio contenedor: hay que
# overridearlo con host.docker.internal para llegar a la base del host, si no la conexión se rechaza.
# API_ALLOWED_ORIGINS es un ejemplo: poner el origen real del frontend externo (R-7.8, D82).
docker run --env-file .env -e POSTGRES_HOST=host.docker.internal -e API_ALLOWED_ORIGINS=http://localhost:5173 -p 8080:8080 pipidu-agent
python -m pytest -q                      # suite offline: sin base ni credenciales
python -m ruff check .                   # lint
# Pendientes (no existen todavía): seed sintético (T2.4), ingesta RAG (T3.3)
```

## Criterios de promoción

El enunciado pide al menos dos de cinco. Estado real:

- [x] Framework agéntico (Smolagents): implementado
- [x] SDD (artefactos en `TP/` y `openspec/`): implementados
- [ ] Interfaz gráfica: la provee un frontend externo que consume la API (D80); no está en este repositorio
- [ ] Despliegue en la nube (GCP): **descartado por D81** (decisión del equipo, 2026-10-13): el sistema se prepara para correr en entorno local. Queda cubierto solo con `framework agéntico` y `SDD`; hay que confirmarlo con la cátedra (T9.13, riesgo D83). La imagen `runtime` sigue siendo válida para correr local con `uvicorn`
- [ ] Observabilidad (LangSmith): excluida explícitamente
