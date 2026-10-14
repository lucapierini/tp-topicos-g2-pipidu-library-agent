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
db/            esquema, init y datos de desarrollo (seed_data.py y dump.sql: pendientes)
rag/           documentos fuente y recuperación (ingest.py y chunking.py: pendientes)
agent/         orquestador, clasificador, validador de SQL, configuración, prompts y tools
scripts/       scripts de medición y de exportación de evidencia
api/           app.py (FastAPI: POST /ask con streaming SSE, GET /health): único acceso al agente
tests/         suite offline, golden set y casos de integración
docker/        Dockerfile (etapas base, measure y runtime, D74; verificado en T9.2 y T9.10)
docker-compose.yml   Postgres + pgvector local
```

El detalle de cada archivo está en `TP/02` §8 (D20): acá solo van los directorios de primer nivel.

## Estado

Etapa SDD completa (`Requirement → Spec → Plan → Tasks → Validation`). El agente y sus tools están
implementados (validador y executor de SQL, tool de RAG, clasificador, orquestador, `agent_runs`), junto
con la API HTTP con streaming de progreso y cancelación, que es el **único acceso** al agente (D80). La
interfaz gráfica (`web/`, Vite + shadcn/ui) es un cliente de esa API y se levanta junto con ella (D84). La
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
docker compose up -d --wait   # todo junto: db (Postgres + pgvector, roles, agent_runs, datos de desarrollo) + api + web (D84)
# (opcional) traer la base compartida de Neon: definir NEON_DATABASE_URL en .env y
bash scripts/replicate_neon.sh --check   # versión y objetos de Neon; sin --check vuelca y restaura
python -m pytest -m integration          # permisos por rol, esquema vs whitelist, flujo con datos reales
python scripts/measure_golden.py --db    # golden set contra la base local (registra en agent_runs)
python scripts/measure_golden.py --db --rag-mock   # + recuperación simulada: contenido de los 13 casos, sin PDFs
python scripts/measure_golden.py --db --rag-mock --bilingual   # + 2 casos en inglés (no cuentan para R-2.1)
python scripts/export_runs.py --last 15  # agent_runs -> TP/evidencia/ (antes de pytest -m integration, que la trunca)
uvicorn api.app:app --port 8000          # API del agente (único acceso); el frontend apunta a http://127.0.0.1:8000
# Consulta de prueba (JSON en UTF-8; en Windows conviene un cliente HTTP en vez de curl por el cuoteo):
#   curl -N -X POST localhost:8000/ask -H "content-type: application/json" -d '{"question":"..."}'
docker build -f docker/Dockerfile -t pipidu-agent .                    # imagen del agente (etapa runtime)
docker build -f docker/Dockerfile --target measure -t pipidu-measure . # + scripts de medición (sin secretos)
# Corrida local (D81): solo se expone el puerto de la API ($PORT, 8080 por defecto).
# Dentro del contenedor, POSTGRES_HOST=127.0.0.1 de `.env` apunta al propio contenedor: hay que
# overridearlo con host.docker.internal para llegar a la base del host, si no la conexión se rechaza.
# API_ALLOWED_ORIGINS es un ejemplo: el origen real del frontend y el procedimiento, en TP/02 §6.2 (R-7.8, D82).
docker run --env-file .env -e POSTGRES_HOST=host.docker.internal -e API_ALLOWED_ORIGINS=http://localhost:5173 -p 8080:8080 pipidu-agent
python -m pytest -q                      # suite offline: sin base ni credenciales
python -m ruff check .                   # lint
# Pendientes (no existen todavía): seed sintético (T2.4), ingesta RAG (T3.3)
```

## Interfaz web (D84)

`docker compose up -d --wait` levanta la base, la API y la interfaz, en ese orden (cada servicio espera a que el
anterior esté sano). Requiere el `.env` completo (`GEMINI_API_KEY` y las contraseñas de la base).

| Servicio | URL (solo loopback) | Qué es |
|---|---|---|
| `web` | http://localhost:3000 | SPA de `web/` (Vite + React + shadcn/ui) servida por nginx; reenvía `/api/` a la API |
| `api` | http://localhost:8080 | API del agente (`POST /ask` SSE, `GET /health`); es el único acceso al agente |
| `db` | `127.0.0.1:5432` | Postgres + pgvector |

Puertos configurables con `WEB_PORT` y `API_PORT` en `.env`. La web no lleva secretos y, al llamar a la API por
el mismo origen, no necesita `API_ALLOWED_ORIGINS`.

Desarrollo de la SPA con recarga en caliente, usando la API local (`uvicorn api.app:app --port 8000`):

```bash
cd web && npm install
npm run dev      # http://localhost:5173; /api se reenvía a http://127.0.0.1:8000 (VITE_API_TARGET lo cambia)
npm test         # vitest
npm run build    # tsc + vite build
```

## Criterios de promoción

El enunciado pide al menos dos de cinco. Estado real:

- [x] Framework agéntico (Smolagents): implementado
- [x] SDD (artefactos en `TP/` y `openspec/`): implementados
- [ ] Interfaz gráfica: SPA en `web/` (Vite + shadcn/ui) que consume la API (D80, D84); en curso (change `frontend-web-vite`)
- [ ] Despliegue en la nube (GCP): **descartado por D81** (decisión del equipo, 2026-10-13): el sistema se prepara para correr en entorno local. Queda cubierto solo con `framework agéntico` y `SDD`; hay que confirmarlo con la cátedra (T9.13, riesgo D83). La imagen `runtime` sigue siendo válida para correr local con `uvicorn`
- [ ] Observabilidad (LangSmith): excluida explícitamente
