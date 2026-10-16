# Tasks

## 1. Setup y entorno

Agrupan la estructura del repo, las dependencias de ejecución y desarrollo, la base local en Docker y la
configuración por variables de entorno.

- [x] 1.1 Crear la estructura de carpetas (`db/`, `rag/`, `agent/`, `api/`, `tests/`, `docker/`) y verificar que `tree` muestra la estructura de `openspec/project.md`
- [x] 1.2 Definir dependencias y verificar que `pip install -r requirements.txt` instala `smolagents[litellm]`, `psycopg2-binary`, `pypdf`, `google-genai`, `sqlglot`, `python-dotenv`, `fastapi`, `uvicorn` y que `pip install -r requirements-dev.txt` agrega `pytest`, `faker`, `ruff` (la separación es D54)
- [x] 1.3 Crear `docker-compose.yml` con Postgres + pgvector y verificar que `docker compose up -d` levanta la base y que `CREATE EXTENSION vector` funciona
- [x] 1.4 Crear `.env.example` y `.gitignore` y verificar que `grep -rE "GEMINI_API_KEY\s*=\s*[\"']" --include="*.py"` no encuentra claves hardcodeadas (leer el nombre de la variable de `os.environ` no cuenta como hardcodeo)

## 2. Modelo de datos y datos sintéticos

El esquema compartido, los roles de acceso a la base y la configuración de los valores del sistema.

- [x] 2.1 Escribir `db/schema.sql` con las 7 tablas del dominio (`autores`, `categorias`, `editoriales`, `libros`, `libros_autores`, `socios`, `prestamos`) más `documentos` y `documentos_chunks` (D64) y verificar que `psql -f db/schema.sql` crea el esquema sin errores de FK
- [x] 2.2 Crear el usuario dedicado `agent_ro` con `GRANT SELECT` sobre las 7 tablas del dominio, la vista `v_prestamos_estado` y `documentos` + `documentos_chunks`, `statement_timeout = 10s` y `default_transaction_read_only`, y verificar que un `INSERT` con ese usuario es rechazado por PostgreSQL (D14, R-3.5, D64, D65; los permisos se aplican en `db/post_restore.sql:19-30`)
- [x] 2.3 Crear `agent/config/__init__.py` con el rango de cuatrimestre (2026-08-01 a 2026-11-30), zona horaria única, top-k, umbral, límite de filas y máximo de intentos, y verificar que ningún valor queda hardcodeado en el código (D6, D12, D15, R-3.11)
- [x] 2.6 Implementar el estado de vencimiento como vista o columna generada (no como valor escrito por el seed) y verificar que coincide con el caso G3 del golden set (D7, R-3.12)
- [x] 2.7 Verificar las reglas de consistencia: ningún `ejemplares_disponibles > ejemplares_totales`, y todo préstamo vencido cumple `fecha_devolucion_real IS NULL AND CURRENT_DATE > fecha_devolucion_prevista`
  _(medido contra la base local de Docker con el rol `agent_ro`: 0 filas con `ejemplares_disponibles > ejemplares_totales` y 0 vencidos que no cumplan la regla de la vista (`tests/test_seed_contract.py:171` y `:181`))_

## 4. Tool `execute_sql`

Validación estática de sentencias y ejecución de solo lectura sobre la base.

- [x] 4.1 Definir la whitelist de tablas y columnas en `agent/config/schema_whitelist.py` y verificar que coincide con `db/schema.sql` (R-3.4)
- [x] 4.2 Implementar la validación estática con `sqlglot` (parseo con `error_level=RAISE`, statement raíz `SELECT`, extracción de tablas, columnas y funciones, expansión de `*` a la whitelist (R-3.14), normalización de identificadores a minúsculas (R-3.15), rechazo de `FOR UPDATE`) y verificar que los casos adversos de `TP/05-validacion.md` §2 (S1–S20 en `tests/test_sql_validator.py` y los de endurecimiento B1–B31 en `tests/test_sql_validator_hardening.py`) devuelven el error tipado esperado, sin ejecutar ninguna consulta (D4, R-3.2, R-3.3, R-3.4, R-3.7, R-3.13)
- [x] 4.3 Implementar `execute_sql(sql)` que recibe la sentencia ya formada por el agente, ejecuta con el usuario `agent_ro`, aplica límite de 50 filas y timeout de 10 s, y verificar que la tool corre sin credenciales de API (D1, R-3.1, R-3.5, R-3.6, R-3.16) — *implementado en `agent/tools/sql_tool.py`; verificado con Postgres real en `tests/test_sql_tool.py` y `tests/test_runs_integration.py` (`pytest -m integration`, rol `agent_ro`, D45, D46)*
- [x] 4.4 Implementar la regeneración limitada (máximo 2 intentos) y verificar el caso de rechazo-then-éxito y el caso de dos rechazos consecutivos, con reporte del error al usuario (D8, R-3.10, R-5.7) — *el tope lo aplica el orquestador (`ToolSession`, `SQL_MAX_ATTEMPTS`) y se verifica en `tests/test_agent.py`; `run_with_regeneration()` queda como utilidad de la tool para uso fuera del agente*
- [x] 4.5 Implementar el contrato `SqlResult` y verificar que `tests/test_sql_tool.py` pasa con los 5 casos SQL del golden set (R-3.1, R-3.9)
- [x] 4.6 Verificar el reporte de resultado vacío con un socio sin préstamos (R-3.8)

## 5. Tool `rag_search_tool`

Retrieval vectorial sobre `documentos_chunks` con umbral configurable.

- [x] 5.1 Implementar el retrieval top-k por similitud de coseno con umbral desde configuración y verificar que `tests/test_rag_tool.py` pasa (R-4.4). Embedder y store son protocolos: la política se prueba sin PDFs ni base
- [x] 5.2 Implementar el contrato `RagResult`/`Chunk` con documento y ubicación por fragmento y verificar que una prueba asserts la referencia de origen (R-4.7)

## 6. Orquestador y selección de fuente

Prompt, clasificación y el agente que invoca las dos herramientas.

- [x] 6.1 Escribir `agent/prompts/system_prompt.md` con rol, esquema resumido, semántica temporal configurada, reglas de selección de fuente y 9 few-shot NL→SQL, y verificar que el prompt exige emitir la clasificación antes de invocar herramientas (R-2.1, R-3.11, D3)
- [x] 6.2 Implementar la clasificación mediante salida estructurada obligatoria (function calling con campo `classification`) y verificar que la clasificación se resuelve antes de la primera invocación a herramienta (D3, R-2.7)
- [x] 6.3 Implementar el `ToolCallingAgent` de Smolagents con las dos tools, temperatura 0, `max_steps = 6` y timeout de API 30 s, y verificar que los 13 casos del golden set producen la clasificación esperada (≥11/13) (D2, D15, R-2.1)
- [x] 6.4 Verificar los 3 casos híbridos: invocan ambas herramientas (R-2.4)
- [x] 6.5 Verificar el caso `none`: no invoca herramientas y no inventa (R-2.5)
- [x] 6.6 Validar el flujo completo contra un **modelo local** (`LLM_MODEL`, `LLM_API_BASE`) con `scripts/measure_golden.py` y verificar clasificación previa a las tools, herramientas por fuente y SQL aceptado por el validador. No cuenta como aceptación (R-2.8)
- [x] 6.7 Repetir la medición con **Gemini** (`GEMINI_API_KEY`, sin cambios de código), versionar la corrida en `TP/evidencia/` consignando el modelo y verificar ≥ 11/13, 3/3 híbridos y 1/1 `none` (R-2.1, R-2.8, R-6.5)
  _(modelo definitivo `gemini-3.1-flash-lite` (D71): 13/13 clasificaciones, 3/3 híbridos, 1/1 `none` y 13/13 de contenido sobre base local y RAG simulado (`TP/evidencia/golden_gemini-3.1-flash-lite_2026-10-11_db-mock.json`, `TP/05` §4.1))_

## 7. Composición de respuesta y trazabilidad

Contrato de la respuesta, idioma, evidencia exhibida, bitácora `agent_runs` y su export.

- [x] 7.1 Implementar el contrato `AgentAnswer` y verificar que toda respuesta del golden set declara fuente (R-5.2)
  _(contrato en `agent/contracts.py` y `tests/test_contracts.py`; composición en `LibraryAgent._compose` de `agent/agent.py`; la medición con modelos reales, 13/13 con fuente declarada antes de las tools, está en `TP/05` §4.1)_
- [x] 7.2 Verificar idioma de respuesta con un caso en inglés y uno en castellano (R-5.1)
  _(B1 y B2 (`tests/golden_set.py::BILINGUAL_SET`) con `gemini-3.1-flash-lite`: 2/2 con idioma declarado `en`, contenido y prosa en inglés; los 13 casos en castellano salen con la plantilla en castellano (`TP/05` §4.1))_
- [x] 7.3 Verificar la evidencia exhibida: SQL muestra la sentencia, RAG muestra el fragmento citado (R-5.3, R-5.4)
  _(`evidence.sql` con la sentencia ejecutada y `evidence.chunks` con documento, ubicación y texto de cada fragmento, verificado en `tests/test_agent.py`; el frontend que la exhibe es la SPA `web/` (D93), cuya verificación corresponde al cambio `frontend-web-vite`)_
- [x] 7.4 Crear la tabla `agent_runs` y verificar que una consulta exitosa genera una fila con los ocho campos (R-6.1, R-6.2)
  _(tabla en `db/migrations/001_agent_runs.sql`; la fila se verifica en `tests/test_runs_integration.py` (`-m integration`, rol `agent_logger`, D63) y está exportada en `TP/evidencia/agent_runs_2026-10-11.json` — 13 filas con `status: ok`)_
- [x] 7.5 Verificar que una consulta rechazada también genera una fila con el motivo (R-6.3)
  _(`status` `error`/`no_coverage` con `error_code` y `error_detail` en la misma tabla; verificado en `tests/test_runs_integration.py:220` (`-m integration`))_
- [x] 7.6 Agregar al golden set dos casos en **inglés** (uno SQL y uno RAG, ids `B1` y `B2`), **fuera** de los 13 que miden R-2.1 para no cambiar el criterio ≥ 11/13, y verificar con el modelo definitivo que se clasifican bien y la respuesta sale en inglés. El enunciado pide "castellano o inglés" y los 13 casos actuales están en castellano; 7.2 depende de esto (R-5.1)
  _(B1 (SQL) y B2 (RAG), flag `--bilingual` en `scripts/measure_golden.py`, fuera del denominador de R-2.1; D73)_
- [x] 7.7 Implementar `scripts/export_runs.py` que vuelque `agent_runs` a un archivo versionado en `TP/evidencia/`, y verificar que contiene las 13 consultas del golden set con sus campos. El fixture de integración hace `TRUNCATE agent_runs` (`tests/test_runs_integration.py`), así que exportar **antes** de correr `pytest -m integration`; la tabla no es una evidencia durable (R-6.1, R-6.2)
  _(`scripts/export_runs.py` con `--last N`, verificado en `tests/test_export_runs.py`; las 13 consultas exportadas en `TP/evidencia/agent_runs_2026-10-11.json` (`count: 13`))_
- [x] 7.8 Retirar la línea de fuente del texto de la respuesta y declararla solo en `sources` (R-5.2, R-2.6, D84), y verificar que `answer` no menciona la fuente (ni línea `Fuente: …` / `Source: …`, ni cita entre paréntesis, ni nombre de documento) en ningún caso (`sql`, `rag`, `hybrid`, `none`, error) y que la que escriba el modelo se retira
  _(`tests/test_agent.py`, `tests/test_prompts.py::test_the_prompt_forbids_naming_the_source_in_the_answer` y `tests/test_api.py::test_the_result_event_carries_the_complete_agent_answer`)_

## 8. API HTTP (único acceso al agente, sin interfaz gráfica propia)

La API es el único acceso al agente (D80); la SPA `web/` la consume por `POST /ask` (D93, cambio
`frontend-web-vite`) y sus tareas no están en esta sección.

- [x] 8.4 Exponer el agente por HTTP con streaming de progreso (`api/app.py`, `POST /ask`, `GET /health`) y verificar los eventos, el latido, el rechazo de la consulta vacía y el error inesperado (R-7.1 a R-7.4, R-7.6, R-7.7, D75)
  _(`tests/test_api.py`, 17 tests)_
- [x] 8.5 Implementar la cancelación cooperativa y la atención en serie, y verificar que una consulta cancelada no se registra y que dos simultáneas no se pisan (R-7.5, R-6.7, R-1.3, D76, D77)
  _(`tests/test_agent.py`, `tests/test_agent_smolagents.py` y `tests/test_api.py::test_closing_the_stream_cancels_the_agent`)_
- [x] 8.6 Retirar la interfaz Streamlit: eliminar `ui/`, la dependencia `streamlit` y el `CMD` de la imagen, y verificar que no queda ninguna referencia en el código ni en la imagen (R-7.0, D80)
  _(`tests/test_dockerfile.py::test_the_runtime_stage_serves_the_http_api_and_no_ui` y `::test_the_runtime_dependencies_do_not_include_a_ui_framework`)_

## 9. Integración y despliegue

Imagen de Docker, ejecución en entorno local (D81) y los mensajes fijos que recibe el usuario.

- [x] 9.2 Crear `docker/Dockerfile` y verificar que la imagen se construye y corre localmente
  _(etapas `base`, `measure` y `runtime` con `.dockerignore`, verificadas en `tests/test_dockerfile.py`; `runtime` corre sin `tests/` ni `.env` y sirve la API (9.10))_
- [x] 9.10 Ejecutar la API como único servicio en entorno local (D81): la imagen `runtime` copia `api/`, arranca `uvicorn api.app:app` en `$PORT` y no incluye ninguna UI (D80); verificar con `docker build` y `docker run` que `GET /health` responde
  _(verificado con Docker: `GET /health` → 200 `{"status":"ok"}`, consulta vacía → 422; la imagen no contiene `ui/`, `tests/`, `.env` ni `streamlit` (`tests/test_dockerfile.py`))_
- [x] 9.14 Rechazar los pedidos de escritura con un mensaje fijo y de tono cercano, dejar una sola nota del sistema en la respuesta y reescribir los mensajes fijos (R-2.9, R-5.8, R-5.9, D94)
  _(campo `write_request` en el clasificador, `_strip_model_notes` en `agent/agent.py` y `MESSAGES`; verificado en `tests/test_agent.py` y `tests/test_classifier.py`)_
