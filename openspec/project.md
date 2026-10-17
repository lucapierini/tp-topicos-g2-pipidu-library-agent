# Project — Pipidu Library Agent

## Purpose

Agente de IA para una biblioteca universitaria. Recibe consultas en lenguaje natural (castellano o inglés) y las
responde con una base de datos relacional, consultada con SQL, y un repositorio de documentos PDF, consultado con
RAG. En cada consulta decide qué fuente usar, o si usa las dos.

Proyecto de la materia Tópicos Avanzados de IA (UCSE, Ingeniería en Informática).

## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.12+ (el código usa sintaxis de 3.12) |
| Base de datos | PostgreSQL + pgvector |
| LLM | Google Gemini (modelo del sistema y de la medición de referencia, D71). En desarrollo puede apuntarse a un servidor local compatible con la API de OpenAI vía LiteLLM (`LLM_MODEL`, `LLM_API_BASE`): valida el flujo, pero no reemplaza esa medición (R-2.8) |
| Embeddings | Gemini Embeddings API |
| Recuperación | Coseno sobre pgvector con re-ranking del modelo por defecto (D100) |
| Framework agéntico | Smolagents |
| Acceso al agente | API HTTP con FastAPI + uvicorn (streaming SSE); el frontend (`web/`, Vite + shadcn/ui) es un cliente de la API (D80, D93) |
| Despliegue | Entorno local: Docker Compose (Postgres + pgvector, API, web) (D81, D93); la API también corre con `uvicorn api.app:app` |

## Estructura del repositorio

```
db/            schema.sql, seed.sql (catálogo completo), dev_seed.sql (seed mínimo), migrations/, init/ (roles y carga
               inicial), post_restore.sql
rag/           documents/ (.md y pdf/), ingest.py, build_pdfs.py, requirements.txt
agent/         agent.py, classifier.py, contracts.py, errors.py, retry.py, runs.py, sql_validator.py,
               config/, prompts/, tools/ (sql_tool.py, rag_tool.py, reranker.py, smol_tools.py)
scripts/       ask.py, measure_golden.py, measure_queue.py, measure_retrieval.py, evaluate_retrieval.py,
               calibrate_threshold.py, export_runs.py, probe_llm.py
api/           app.py (FastAPI: POST /ask con streaming SSE, GET /health): único acceso al agente
web/           SPA Vite + React + shadcn/ui: cliente de la API (D93)
tests/         ver el detalle en `TP/02` §8
docker/        Dockerfile, Dockerfile.web, nginx.conf (docker-compose.yml está en la raíz)
TP/            artefactos SDD legibles: constitución, especificaciones, validación, decisiones y evidencia
informe/       informe técnico (informe-tecnico.md y su PDF)
openspec/      raíz operativa de SDD (esta carpeta)
```

## Convenciones

- Idioma de los artefactos: español. Encabezados estructurales y `SHALL`/`MUST` en inglés.
- IDs de requisito: `R-<capacidad>.<n>`, declarados en cada `specs/<capacidad>/spec.md` del change y
  replicados en el nombre de cada `### Requirement:` para mantener trazabilidad.
- Criterios de aceptación en formato GIVEN / WHEN / THEN.
- Commits: `<tipo>(<ámbito>): <resumen> (IDs)`, con los IDs de la decisión y el requisito que motivan el
  cambio (ej. `feat(api): CORS para el frontend externo (R-7.8, D82)`).
- Cada tarea de `tasks.md` debe trazar a un requisito.

## Restricciones permanentes

Ver `TP/00-constitucion.md`. Las tres que condicionan el desarrollo:

1. **Read-only por diseño** — el agente nunca escribe en la base (prompt + validación estática + rol `agent_ro`).
2. **Proveniencia obligatoria** — toda respuesta declara la fuente usada; no se afirma nada sin fuente consultada.
3. **Trazabilidad de ejecución** — cada consulta se registra en la tabla `agent_runs`.
