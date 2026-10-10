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
db/            schema.sql, seed_data.py, dump.sql
rag/           documents/ (PDFs), ingest.py, chunking.py
agent/         agent.py, prompts/, tools/sql_tool.py, tools/rag_tool.py, response.py
ui/            app.py
tests/         test_sql_tool.py, test_rag_tool.py, test_golden_set.py
docker/        Dockerfile
```

## Estado

Etapa SDD completa (`Requirement → Spec → Plan → Tasks → Validation`). Implementación pendiente.
El change activo es [`agente-y-tools`](openspec/changes/agente-y-tools/), validado con
`openspec validate --strict`.

## Instalación y ejecución

_(se completa con la tarea 1.5 de `openspec/changes/agente-y-tools/tasks.md`)_

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
make seed                     # datos sintéticos (semilla 42)
make ingest                   # chunking + embeddings
make ui                       # Streamlit
make test                     # golden set + sanitización
```

## Criterios de promoción cubiertos

- [x] Despliegue en la nube (GCP)
- [x] Interfaz gráfica (Streamlit)
- [x] Framework agéntico (Smolagents)
- [x] SDD (artefactos en `TP/` y `openspec/`)
- [ ] Observabilidad (LangSmith) — excluido explícitamente
