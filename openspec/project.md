# Project — Pipidu Library Agent

## Purpose

SQL AI Agent para un dominio de biblioteca universitaria: recibe consultas en lenguaje natural
(castellano o inglés) y responde usando una base de datos relacional (SQL) y un repositorio
documental vía RAG, decidiendo autónomamente qué fuente usar en cada consulta.

Materia: Tópicos Avanzados de IA — Trabajo Práctico Integrador (AI Engineering), UCSE.
Entrega: 16/10/2026 23:59 (GMT-03). Coloquio: 23/10 o 30/10/2026.

## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Base de datos | PostgreSQL + pgvector |
| LLM | Google Gemini (aceptación y despliegue). En desarrollo puede apuntarse a un servidor local compatible con la API de OpenAI vía LiteLLM (`LLM_MODEL`, `LLM_API_BASE`): valida el flujo, no reemplaza la medición de aceptación (R-2.8) |
| Embeddings | Gemini Embeddings API |
| Framework agéntico | Smolagents |
| Acceso al agente | API HTTP con FastAPI + uvicorn (streaming SSE); el frontend es un cliente externo (D80) |
| Despliegue | GCP (Cloud Run + Cloud SQL + Secret Manager) |

## Estructura del repositorio

```
db/            schema.sql, seed_data.py, dump.sql
rag/           documents/ (PDFs), ingest.py, chunking.py
agent/         agent.py, classifier.py, contracts.py, errors.py, retry.py, runs.py, sql_validator.py,
               config/, prompts/, tools/ (sql_tool.py, rag_tool.py, smol_tools.py)
scripts/       measure_golden.py, export_runs.py, calibrate_threshold.py, probe_llm.py, replicate_neon.sh
api/           app.py (FastAPI: POST /ask con streaming SSE, GET /health): único acceso al agente
tests/         test_sql_tool.py, test_rag_tool.py, test_golden_set.py
docker/        Dockerfile
TP/            artefactos SDD adjuntables al informe
openspec/      raíz operativa de SDD (esta carpeta)
```

## Convenciones

- Idioma de los artefactos: español. Encabezados estructurales y `SHALL`/`MUST` en inglés.
- IDs de requisito: `R-<capacidad>.<n>`, declarados en cada `specs/<capacidad>/spec.md` del change y
  replicados en el nombre de cada `### Requirement:` para mantener trazabilidad.
- Criterios de aceptación en formato GIVEN / WHEN / THEN.
- Commits: `T<n>: <resumen>`.
- Cada tarea de `tasks.md` debe trazar a un requisito.

## Restricciones permanentes

Ver `TP/00-constitucion.md`. Las tres que condicionan este change:

1. **Read-only por diseño** — el agente nunca escribe en la base (prompt + validación estática + rol `readonly`).
2. **Proveniencia obligatoria** — toda respuesta declara la fuente usada; no se afirma nada sin fuente consultada.
3. **Trazabilidad de ejecución** — cada consulta se registra en la tabla `agent_runs`.
