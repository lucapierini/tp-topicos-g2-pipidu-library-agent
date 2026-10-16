# Pipidu Library Agent

SQL AI Agent para un dominio de biblioteca universitaria. Recibe consultas en lenguaje natural
(castellano o inglés) y responde usando una base de datos relacional (SQL) y un repositorio documental
vía RAG, decidiendo autónomamente qué fuente consultar en cada caso.

**Materia:** Tópicos Avanzados de IA — Trabajo Práctico Integrador (AI Engineering), UCSE.
**Entrega:** 16/10/2026 23:59 (GMT-03) · **Coloquio:** 23/10 o 30/10/2026.

## Stack

Python 3.12+ · PostgreSQL + pgvector · Gemini · Smolagents · FastAPI · React 19 + Vite + shadcn/ui (Tailwind v4) · ejecución local con Docker Compose (D81, D93)

## Cómo funciona

```
navegador ──► web (nginx, :3000) ──/api/──► api (FastAPI, :8080) ──► agente ──► clasificador (Gemini)
                                                                          ├─► execute_sql ──► PostgreSQL (rol agent_ro, solo lectura)
                                                                          └─► retrieve_documents ──► pgvector (fragmentos de rag/documents/)
```

Cada consulta se clasifica (`sql`, `rag`, `hybrid` o `none`), se resuelve con las herramientas que corresponden y
se registra en la tabla `agent_runs`. La respuesta declara su fuente en el campo `sources`, no en el texto.
La API (`POST /ask` con streaming SSE, `GET /health`) es el único acceso al agente (D80).

## Estructura

```
TP/            artefactos SDD (constitución, especificación funcional y técnica, validación, changelog, evidencia, enunciado)
openspec/      raíz operativa de SDD (project.md, config.yaml, changes/)
db/            schema.sql, seed.sql (catálogo completo), dev_seed.sql (seed mínimo), migrations/, init/ (roles y carga inicial)
rag/           documentos fuente (.md y pdf/), ingest.py (ingesta a pgvector) y build_pdfs.py
agent/         orquestador, clasificador, validador de SQL, configuración, prompts y tools
api/           app.py: POST /ask (SSE) y GET /health
web/           SPA de consulta (Vite + React + shadcn/ui): cliente de la API
scripts/       medición (golden set, calibración), exportación de evidencia y ask.py
tests/         suite offline, golden set y casos de integración
docker/        Dockerfile (etapas base, measure, local y runtime), Dockerfile.web y nginx.conf
docker-compose.yml   db, ingest, api y web (perfil `tools`: agent)
```

El detalle de cada archivo está en `TP/02` §8 (D20).

## Guía paso a paso: levantar el proyecto desde cero

Hay dos caminos. El **A (todo con Docker)** es el que debe usar quien evalúe el trabajo: no hace falta instalar
Python, Node ni PostgreSQL. El **B (desarrollo local)** es para modificar el código con recarga en caliente.

### Camino A — Todo con Docker

**Paso 1. Instalar los requisitos**

- **Docker Desktop** (incluye `docker compose`), abierto y con el motor en marcha.
- **Git**.
- Una **API key de Gemini** (https://aistudio.google.com/apikey). Se usa para el agente y para los embeddings del RAG.

**Paso 2. Clonar el repositorio**

```bash
git clone https://github.com/lucapierini/tp-topicos-g2-pipidu-library-agent.git
cd tp-topicos-g2-pipidu-library-agent
```

**Paso 3. Crear el archivo `.env`**

```bash
cp .env.example .env              # PowerShell: Copy-Item .env.example .env
```

**Paso 4. Completar cuatro variables en `.env`**

El resto tiene valores por defecto. Las contraseñas las inventás vos; usá solo letras y números, para evitar
problemas con caracteres especiales en el archivo.

| Variable | Qué poner |
|---|---|
| `GEMINI_API_KEY` | tu clave de Gemini |
| `POSTGRES_PASSWORD` | contraseña para el rol de lectura `agent_ro` |
| `POSTGRES_LOG_PASSWORD` | contraseña para el rol `agent_logger` (escribe `agent_runs`) |
| `POSTGRES_ADMIN_PASSWORD` | contraseña del superusuario local `postgres` |

**Paso 5. Levantar todo**

```bash
docker compose up -d --build --wait
```

La primera vez construye las imágenes de la API y de la web, y descarga las de Postgres y nginx. El comando espera
a que cada servicio esté sano y no devuelve el control hasta entonces. En orden, hace esto:

1. **`db`**: PostgreSQL + pgvector. Crea el esquema, los roles `agent_ro` y `agent_logger`, la tabla `agent_runs` y
   carga el catálogo completo (`db/seed.sql`: 70 libros, 20 socios y 28 préstamos).
2. **`ingest`**: toma los 6 documentos de `rag/documents/*.md`, los parte por sección, calcula los embeddings con
   Gemini y los guarda en pgvector (44 fragmentos). Corre una vez y termina; es idempotente.
3. **`api`**: la API del agente, que arranca cuando la ingesta terminó bien.
4. **`web`**: la interfaz, que arranca cuando la API está sana.

**Paso 6. Verificar que quedó funcionando**

```bash
docker compose ps -a
```

Deben figurar `db`, `api` y `web` como `healthy` y `ingest` como `Exited (0)`. Dos comprobaciones más:

```bash
docker compose logs ingest        # la última línea: «En la base: 6 documentos, 44 fragmentos»
```

Y la API responde (en PowerShell, `Invoke-RestMethod http://localhost:8080/health`):

```bash
curl http://localhost:8080/health   # {"status":"ok"}
```

**Paso 7. Usar la interfaz**

Abrir **http://localhost:3000** y preguntar, por ejemplo:

- «¿Cuántos cómics de Marvel hay?» (SQL)
- «¿De qué trata El Hobbit?» (RAG: cita `resenas_tolkien.pdf`)
- «¿Cuántos días puedo tener un libro prestado siendo alumno?» (RAG: el reglamento)

Debajo de cada respuesta aparecen las fuentes usadas (SQL, RAG o ambas) y el botón «Ver evidencia» con la
sentencia SQL, las filas y los fragmentos citados.

**Paso 8. Apagar**

```bash
docker compose down        # apaga todo y conserva los datos
docker compose down -v     # apaga todo y BORRA la base: el próximo `up` la recarga de cero
```

| Servicio | URL (solo loopback) | Qué es |
|---|---|---|
| `web` | http://localhost:3000 | SPA de `web/` servida por nginx; reenvía `/api/` a la API sin buffering |
| `api` | http://localhost:8080 | API del agente (`POST /ask`, `GET /health`) |
| `db` | `127.0.0.1:5432` | Postgres + pgvector |

Los puertos se cambian con `WEB_PORT`, `API_PORT` y `POSTGRES_PORT` en `.env`. La web llama a la API por el mismo
origen, así que no necesita `API_ALLOWED_ORIGINS`.

**Comandos útiles**

```bash
docker compose logs -f api              # logs de la API
docker compose run --rm ingest          # re-ingesta manual del RAG (normalmente no hace falta)
docker compose run --rm agent "¿Qué libros de Borges hay?"   # el agente por línea de comandos, sin la web
```

### Camino B — Desarrollo local (Python y Node en tu máquina)

Para modificar el código con recarga en caliente. La base y la ingesta siguen corriendo en Docker; la API y la
interfaz corren en tu máquina. Requisitos: los del camino A más **Python 3.12+** y **Node 24** (la versión con la que se construye la imagen de la web).

**Paso 1.** Repetir los pasos 2, 3 y 4 del camino A (clonar y completar `.env`). Con los valores por defecto,
`POSTGRES_HOST=127.0.0.1` apunta a la base publicada por Docker.

**Paso 2. Levantar la base y cargar el RAG**

```bash
docker compose up -d --build --wait db
docker compose run --rm ingest
```

**Paso 3. Crear el entorno de Python e instalar las dependencias**

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (PowerShell: .venv\Scripts\Activate.ps1) · Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

**Paso 4. Levantar la API**

```bash
uvicorn api.app:app --port 8000
```

Comprobar con `curl http://127.0.0.1:8000/health`. El código se lee al arrancar: tras cambiar `.env` o el código hay
que reiniciar `uvicorn`.

**Paso 5. Levantar la interfaz** (otra terminal)

```bash
cd web
npm install
npm run dev
```

Abrir **http://localhost:5173**. Vite reenvía `/api` a `http://127.0.0.1:8000`, así que no hace falta CORS
(`VITE_API_TARGET` cambia el destino). Detalles del desarrollo de la SPA en [`web/README.md`](web/README.md).

### Pruebas

```bash
python -m pytest -q          # suite offline: sin base ni credenciales
python -m ruff check .       # lint
openspec validate --all --strict   # specs bien formadas; requiere la CLI: npm install -g @fission-ai/openspec
cd web && npm test           # tests de la interfaz
```

Los tests marcados `integration` necesitan la base en marcha; los de `tests/test_runs_integration.py` **truncan
`agent_runs`**, así que no corras `pytest -m integration` completo sobre una base con historial que quieras conservar. Los `llm`
llaman al modelo real. Ninguno corre por defecto. Para los de contrato del seed (solo lectura):
`python -m pytest tests/test_seed_contract.py -m integration`.

### Problemas frecuentes

- **`docker compose up` falla en `ingest`**: falta o es inválida `GEMINI_API_KEY`, o se alcanzó la cuota de Gemini (reintentar con `docker compose run --rm ingest`).
- **`variable is not set`**: falta alguna de las cuatro variables del paso 4.
- **El puerto 5432, 3000 u 8080 está ocupado**: cambiar `POSTGRES_PORT`, `WEB_PORT` o `API_PORT` en `.env`.
- **El chat dice que no tiene información de los documentos**: `docker compose logs ingest` debe terminar con «En la base: 6 documentos, 44 fragmentos».
- **Cambié `.env` y no se nota**: la API lee el archivo al arrancar; `docker compose up -d` recrea el contenedor con los valores nuevos.
- **Cambié `DEV_SEED`**: solo aplica al crear el volumen; hay que hacer `docker compose down -v` y volver a levantar.
- **Si `.env` apunta a Neon** (`NEON_DATABASE_URL` completo), `docker compose` igual usa la base local para `api`, `ingest` y `agent`.

`DEV_SEED` (opcional, en `.env`): `full` (por defecto) carga el catálogo completo; `1` carga el seed mínimo de pruebas
(`db/dev_seed.sql`, lo que esperan los tests de integración); `0` deja la base vacía.

## Interfaz web (D93)

SPA de una sola pantalla en `web/` (Vite + React 19 + TypeScript + shadcn/ui, preset `base-luma`, íconos Hugeicons). Es un
cliente de la API: llama a `POST /ask` y no tiene acceso directo al agente ni a la base (R-7.0). Cada consulta viaja sola, sin
el historial (D17).

- **Consulta** (R-8.1): campo de texto con Enter para enviar (Shift+Enter, salto de línea). No envía consultas vacías ni una nueva
  mientras otra está en curso, pero deja escribir la siguiente mientras el agente responde.
- **Progreso en vivo** (R-8.2): clasificación, herramienta invocada y su resultado a medida que llegan los eventos SSE, con indicador
  *shimmer* y segundos de espera por `heartbeat`. No muestra ninguna fuente antes del evento `result`.
- **Respuesta con proveniencia** (R-8.3, R-8.11): `answer` como Markdown (listas, énfasis, tablas, código; el HTML no se interpreta)
  con las fuentes declaradas como `Badge`. `no_coverage` y `error` se muestran aparte, como `Alert`.
- **Evidencia** (R-8.4): botón «Ver evidencia» con la sentencia SQL, las filas en una tabla y los fragmentos citados, tal como llegan.
- **Cancelación y fallas** (R-8.5, R-8.6): corta la conexión para cancelar al agente; distingue «API no disponible», consulta
  rechazada y corte antes del resultado, con reintento.
- **Historial de la sesión** (R-8.10): conserva las consultas y respuestas anteriores en pantalla; vive en el navegador y se pierde al recargar.

Estructura de `web/src`:

```
App.tsx                  pantalla: encabezado, lista de turnos (MessageScroller) y formulario
components/ask/          ask-form, progress-panel, answer-view, markdown, evidence-view, failure-alert
components/ui/           componentes de shadcn/ui
hooks/use-ask.ts         estado de la consulta (idle/running/done/failed), cancelación e historial
lib/ask-stream.ts        cliente SSE de POST /ask y tipos de los eventos y del resultado
lib/progress.ts          eventos de progreso -> pasos visibles
```

## Usar la API directamente

`POST /ask` recibe `{"question": "..."}` y responde `text/event-stream`: `start`, `classified`, `tool_call`, `tool_result`,
`step`, `composing`, `heartbeat` (cada 5 s) y, al final, `result` (o `error`). `GET /health` responde `{"status":"ok"}`.
El contrato completo está en `TP/02` §6.1. Un cliente web de otro origen necesita `API_ALLOWED_ORIGINS` en `.env`:
procedimiento en `TP/02` §6.2 (R-7.8, D82). No hay autenticación: el servicio es para ejecución local (D81).

```bash
curl -N -X POST http://localhost:8080/ask -H "content-type: application/json" -d '{"question":"¿Cuántos libros de Tolkien hay?"}'
```

(En PowerShell, `curl` es un alias de otro comando: usar `curl.exe`, y escapar las comillas dobles del JSON o armar el cuerpo con `ConvertTo-Json`.)

## Medición y evidencia

```bash
python scripts/measure_golden.py --out TP/evidencia/<corrida>.json   # mide R-2.1 con el modelo configurado
python scripts/measure_golden.py --db --rag-mock                      # golden set contra la base local, recuperación simulada
python scripts/export_runs.py --last 15                               # agent_runs -> TP/evidencia/
docker build -f docker/Dockerfile --target measure -t pipidu-measure . # imagen con los scripts de medición
```

Desarrollo sin cuota: apuntar a un servidor local OpenAI-compatible con `LLM_MODEL=openai/<id>` y
`LLM_API_BASE=http://127.0.0.1:<puerto>/v1` (R-2.8); valida el flujo pero no cuenta como aceptación.
Opcional: traer la base compartida de Neon con `NEON_DATABASE_URL` en `.env` y `bash scripts/replicate_neon.sh --check`.
Las variables de entorno están documentadas una por una en `.env.example`.

## Estado

Etapa SDD completa (`Requirement → Spec → Plan → Tasks → Validation`): todas las tareas de los cuatro changes están terminadas. El agente, la API con streaming y cancelación, y la
interfaz web (D93) están implementados. La clasificación con el modelo definitivo (`gemini-3.1-flash-lite`, D71) midió 13/13 casos correctos el 2026-10-10 y el 2026-10-11, sobre el
mínimo de 11 (R-2.1); las dos corridas, la exportación de `agent_runs` y la calibración del umbral están en `TP/evidencia/`. Las specs se validan con
`openspec validate --all --strict` y los cuatro changes están en [`openspec/changes/`](openspec/changes/): `agente-y-tools`, `base-de-datos-neon`,
`frontend-web-vite` y `frontend-markdown-answer`.
