# Pipidu Library Agent

SQL AI Agent para un dominio de biblioteca universitaria. Recibe consultas en lenguaje natural
(castellano o inglés) y responde usando una base de datos relacional (SQL) y un repositorio documental
vía RAG, decidiendo autónomamente qué fuente consultar en cada caso.

**Materia:** Tópicos Avanzados de IA — Trabajo Práctico Integrador (AI Engineering), UCSE.
**Entrega:** 16/10/2026 23:59 (GMT-03) · **Coloquio:** 23/10 o 30/10/2026.

## Stack

Python 3.11+ · PostgreSQL + pgvector · Gemini · Smolagents · Streamlit · GCP (Cloud Run + Cloud SQL)

## Estructura

```
TP/            artefactos SDD (constitución, specs, validación, changelog, enunciado)
openspec/      raíz operativa de SDD (project.md, config.yaml, changes/)
db/            schema.sql, seed.sql (catálogo real en Neon), dev_seed.sql, migrations/, init/, post_restore.sql
               (+ seed_data.py, dump.sql: pendientes)
rag/           documents/ (.md fuente + pdf/), build_pdfs.py, upload_to_bucket.py; ingest.py, chunking.py (pendientes)
agent/         agent.py, classifier.py, contracts.py, errors.py, retry.py, runs.py, sql_validator.py,
               config/, prompts/, tools/ (sql_tool.py, rag_tool.py, smol_tools.py)
scripts/       measure_golden.py, export_runs.py, calibrate_threshold.py, probe_llm.py, replicate_neon.sh
ui/            app.py (pendiente)
tests/         test_sql_tool.py, test_rag_tool.py, test_golden_set.py, test_agent.py, test_runs.py, ...
docker/        Dockerfile (pendiente)
docker-compose.yml   Postgres + pgvector local
```

## Estado

Etapa SDD completa (`Requirement → Spec → Plan → Tasks → Validation`). El agente y sus tools están
implementados (validador y executor de SQL, tool de RAG, clasificador, orquestador, `agent_runs`).
Pendiente: la medición de aceptación con el modelo definitivo (T6.7), la ingesta de PDFs y el seed
entregable, la UI y el despliegue. El detalle está en
[`tasks.md`](openspec/changes/agente-y-tools/tasks.md).
El change activo es [`agente-y-tools`](openspec/changes/agente-y-tools/), validado con
`openspec validate --strict`. El change [`base-de-datos-neon`](openspec/changes/base-de-datos-neon/)
justifica el esquema, el seed y los documentos fuente del RAG (rama `feature/database`).

## Instalación y ejecución

El flujo de arranque cubre hasta lo implementado. `seed`, `ingest` y la UI se agregan cuando existan
(T2.4, T3.3, T8.1); la tarea 1.5 de `openspec/changes/agente-y-tools/tasks.md` sigue abierta por eso.

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
docker build -f docker/Dockerfile -t pipidu-agent .                    # imagen del agente (etapa runtime)
docker build -f docker/Dockerfile --target measure -t pipidu-measure . # + scripts de medición (sin secretos)
python -m pytest -q                      # suite offline: sin base ni credenciales
python -m ruff check .                   # lint
# Pendientes (no existen todavía): seed sintético (T2.4), ingesta RAG (T3.3), UI Streamlit (T8.1)
```

## Criterios de promoción

El enunciado pide al menos dos de cinco. Estado real:

- [x] Framework agéntico (Smolagents): implementado
- [x] SDD (artefactos en `TP/` y `openspec/`): implementados
- [ ] Interfaz gráfica (Streamlit): planificada, pendiente (tareas 8.x)
- [ ] Despliegue en la nube (GCP): planificado, pendiente (tareas 9.2, 9.3, 9.6, 9.7)
- [ ] Observabilidad (LangSmith): excluida explícitamente
