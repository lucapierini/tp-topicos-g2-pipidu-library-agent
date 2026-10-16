# Proposal

## Why

Hoy el agente solo se accede por la API HTTP (R-7.0, D80) y no hay interfaz gráfica en el repositorio: el
criterio de promoción "Interfaz gráfica" está sin cumplir y no hay forma de que una persona use el agente sin
un cliente HTTP. La API ya transmite el progreso por SSE (R-7.1 a R-7.3), así que lo que falta es un
cliente que lo consuma. Además, el sistema solo corre en local (D81) y hoy `docker compose` levanta
únicamente la base: hacen falta tres pasos manuales (compose, uvicorn, frontend) para ver algo andando.

## What Changes

- Se agrega una SPA en `web/` con Vite + React + TypeScript + Tailwind + shadcn/ui, inicializada con
  `npx shadcn@latest init --preset b1Vq8M9Q --template vite` (estilo `base-luma`, color base `neutral`, tema
  `sky`, íconos `hugeicons`, fuente Inter) desde dentro de `web/`.
- La SPA permite escribir una consulta, ver el progreso en vivo (`classified`, `tool_call`, `tool_result`,
  `composing`, `heartbeat`), y mostrar la respuesta final con su fuente (`sources`), el tipo
  (`answer_kind`) y la evidencia (`evidence`: SQL y filas, o fragmentos citados). Permite cancelar una consulta en curso.
- `docker-compose.yml` pasa a levantar todo junto con `docker compose up -d --wait`: `db`, `ingest` (la ingesta
  del RAG), `api` (imagen `runtime` existente) y `web` (build de la SPA servida por nginx), con healthchecks y
  orden de arranque.
- Se agrega `docker/Dockerfile.web` (build multi-etapa de Node a estáticos servidos por nginx, que además
  hace de proxy hacia la API para que el navegador use un único origen).
- Se reformula R-7.0 en `consulta-por-api` (change `agente-y-tools`) y se actualizan las specs y docs que
  decían "sin interfaz gráfica" (`TP/01`, `TP/02`, `TP/05`, `TP/CHANGELOG.md` con D93, `README.md`,
  `openspec/project.md`): la API sigue siendo el único acceso *al agente*; la interfaz es un cliente.
- Se actualizan `README.md`, `.env.example` y `.dockerignore` (arranque único, `API_ALLOWED_ORIGINS`).

No hay cambios en `agent/` ni en el contrato de la API: el frontend no recibe historial ni mantiene sesión
en el servidor (v1 de un solo turno).

## Capabilities

### New Capabilities
- `interfaz-web`: la SPA que consume `POST /ask` por SSE, muestra progreso, respuesta, fuente y evidencia,
  y permite cancelar; y su arranque conjunto con el resto del sistema por Docker Compose.

### Modified Capabilities
<!-- `consulta-por-api` aún no está en `openspec/specs/`: vive como delta del change `agente-y-tools`.
     Su R-7.0 se reformula editando ese delta (tarea 5.1), no con un delta de este change. -->

## Impact

- **Código nuevo**: `web/` (SPA), `docker/Dockerfile.web`, `docker/nginx.conf`.
- **Código modificado**: `docker-compose.yml` (servicios `api` y `web`), `.env.example`, `.dockerignore`,
  `README.md`.
- **Specs/decisiones**: `openspec/changes/agente-y-tools/specs/consulta-por-api/spec.md` (R-7.0) y la
  documentación `TP/` que cite D80 / R-7.0 (coordinar con ese change, que sigue abierto).
- **Dependencias**: Node 24 y npm para construir `web/`; imagen `nginx:1.29-alpine`; en runtime del usuario,
  solo Docker.
- **Riesgos**: el compose necesita `GEMINI_API_KEY` y credenciales en `.env`; el `agente-y-tools` sigue en
  curso (38/60 tareas), por lo que hay que evitar conflictos en `README.md` y `docker/Dockerfile`.
- **Fuera de alcance**: autenticación, historial persistente de conversaciones, multi-turno, despliegue en
  la nube (descartado por D81) y cambios al agente.
