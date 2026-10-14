# Design

## Context

Motivación en `proposal.md`; requisitos en `specs/interfaz-web/spec.md`. Estado actual observado:

- `docker-compose.yml` define solo `db` (`pgvector/pgvector:pg17`, puerto `127.0.0.1:5432`, healthcheck).
- La API (`api/app.py`) expone `POST /ask` (SSE, `text/event-stream`), `GET /health` y CORS por
  `API_ALLOWED_ORIGINS`; sin orígenes no agrega el middleware, y no usa `*` ni credenciales (R-7.8).
- `docker/Dockerfile` ya tiene la etapa `runtime` (Python 3.12, puerto `$PORT`=8080). Dentro de un contenedor,
  `POSTGRES_HOST=127.0.0.1` del `.env` no llega a la base: hay que sobrescribirlo.
- `web/` existe y está vacía. Node disponible: v24.
- `POST /ask` es un POST con cuerpo JSON: `EventSource` no sirve (solo GET).
- R-7.0 y D80 declaran que el repositorio no incluye interfaz gráfica; este change lo revierte en parte.

## Goals / Non-Goals

**Goals:**
- Una SPA que consuma el SSE existente sin tocar el contrato de la API.
- Un solo comando levanta todo; la persona solo necesita Docker y un `.env`.
- Que la interfaz respete las reglas de shadcn (composición, tokens semánticos, `FieldGroup`, etc.).

**Non-Goals:**
- Autenticación, multi-turno, historial persistente, i18n de la interfaz, modo producción en la nube (D81).
- Cambiar `agent/` o el formato de eventos.
- Hot reload dentro de Docker: el desarrollo de la SPA usa `npm run dev` fuera del contenedor.

## Decisions

**1. SPA con Vite + React + TypeScript, inicializada con la CLI de shadcn.** Se ejecuta
`npx shadcn@latest init --preset b1Vq8M9Q --template vite` dentro de `web/`. El preset decodifica a estilo
`luma`, base `neutral`, tema `sky`, íconos `hugeicons` y fuente Inter. Se usa `hugeicons` (no `lucide`) en
todo el código nuevo, tal como lo fija `components.json`. *Alternativa:* armar Vite a mano y agregar shadcn
después: más pasos y riesgo de divergir del preset.

**2. Cliente SSE con `fetch` + `ReadableStream`, no `EventSource`.** `POST /ask` lleva cuerpo, así que se
lee `response.body`, se decodifica UTF-8 y se parsea el formato `event:`/`data:` separado por línea en
blanco, tolerando eventos partidos entre chunks. Se aísla en un módulo `web/src/lib/ask-stream.ts` sin
dependencias de React, testeable con `vitest`. *Alternativa:* librería `@microsoft/fetch-event-source`: una
dependencia más para ~40 líneas, y menos control sobre la cancelación.

**3. Cancelación con `AbortController`.** Abortar el `fetch` cierra la conexión; Starlette cierra el
generador y la API marca `cancel` (R-7.5). No hace falta un endpoint nuevo.

**4. Estado de la consulta como máquina explícita** (`idle → running → done | failed | cancelled`) en un
hook `useAsk`. Los eventos de progreso se acumulan en una lista; `result` reemplaza el estado de progreso.
La UI deriva todo del estado, así que R-8.2 (sin fuente anticipada) se cumple porque `sources` solo existe
en el estado `done`.

**5. UI con componentes shadcn y primitivas de chat.** Conversación y progreso con `MessageScroller`,
`Message` y `Bubble`; entrada con `FieldGroup` + `Field` + `Textarea` (o `InputGroup`); fuentes con `Badge`;
evidencia SQL con `Table` dentro de `Collapsible`/`Accordion`; errores con `Alert`; carga con `Spinner` y
`Skeleton`; vacío con `Empty`. Cada componente se instala con `npx shadcn@latest add` y se revisa tras
agregarlo (regla del skill). v1 es de un solo turno (R-7.0): se muestra la consulta actual y la respuesta,
no un historial acumulado.

**6. Un único origen con nginx como proxy.** La imagen `web` construye la SPA y la sirve con nginx; nginx
reenvía `/api/` a `http://api:8080/` con `proxy_buffering off`, `proxy_http_version 1.1`, `proxy_read_timeout`
alto y `X-Accel-Buffering` respetado, para que el SSE no se almacene en buffer. El navegador llama a
`/api/ask`, así que en Docker no hay CORS. *Alternativa:* que el navegador llame directo a
`localhost:8080` con `API_ALLOWED_ORIGINS`: funciona, pero exige configurar el origen exacto y expone el
puerto de la API al navegador. Se mantiene `API_ALLOWED_ORIGINS=http://localhost:5173` solo para
`npm run dev` (Vite también puede proxear `/api` y evitarlo; ver tarea 2.4).

**7. Compose con tres servicios.** `db` (sin cambios), `api` (`build: docker/Dockerfile`, `target: runtime`,
`env_file: .env`, `POSTGRES_HOST: db`, `POSTGRES_PORT: 5432`, `depends_on: db: service_healthy`, healthcheck
sobre `/health`) y `web` (`build: docker/Dockerfile.web`, `depends_on: api: service_healthy`, puerto
`127.0.0.1:${WEB_PORT:-3000}:80`). La API no publica puerto al host salvo `127.0.0.1:${API_PORT:-8080}` para
depurar y para `measure_golden`/curl. *Alternativa:* un perfil de compose para la web: agrega un flag y
contradice "levantar todo junto".

**8. Contexto de build separado.** `.dockerignore` ya excluye `.env`, `TP/` y `openspec/`; se agrega
`web/node_modules`, `web/dist` y se verifica que el contexto de la web no incluya `.env` (R-8.9). Si el
contexto compartido complica la imagen de la API, se usa `context: ./web` para la web.

**9. Reformulación de R-7.0.** La API sigue siendo el único punto de acceso *al agente* y el servidor
Python no sirve interfaz; la SPA es un cliente en su propio servicio. Se edita el delta
`consulta-por-api` del change `agente-y-tools` (que aún no está archivado) y se registra en
`TP/CHANGELOG.md` como D84, que matiza D80. Ya aplicado en `consulta-por-api`, `TP/01`, `TP/02`, `TP/05`,
`README.md`, `openspec/project.md` y el `design.md`/`proposal.md` de `agente-y-tools`.

## Risks / Trade-offs

- [SSE cortado por buffering en nginx] → `proxy_buffering off`, cabecera `X-Accel-Buffering: no` ya enviada
  por la API, y una verificación manual del progreso en vivo (tarea 4.3).
- [Cambio de postura sobre D80/R-7.0 frente a la cátedra y al otro change] → la reformulación se hace en
  el mismo PR y se marca en el CHANGELOG; el criterio "Interfaz gráfica" del README solo se tilda tras la
  verificación.
- [Conflictos con `agente-y-tools` en `README.md` y `docker-compose.yml`] → cambios acotados y rebase
  frecuente; no se toca `docker/Dockerfile`.
- [Consultas de minutos y timeouts del proxy] → `proxy_read_timeout` de 10 minutos; el latido de la API cada
  5 segundos mantiene viva la conexión.
- [`npx shadcn init` interactivo o con prompts que cambian entre versiones] → se ejecuta una vez, se
  versiona `components.json` y se fija la versión de la CLI en la tarea 1.1.
- [`GEMINI_API_KEY` ausente hace que la API falle al responder, no al arrancar] → el healthcheck solo mira
  `/health`; la interfaz muestra el error de R-8.3.

## Open Questions

- Puerto publicado de la web (`3000` por defecto). Se puede cambiar con `WEB_PORT` sin tocar specs.
