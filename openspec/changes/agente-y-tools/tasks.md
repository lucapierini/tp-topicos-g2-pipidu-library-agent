# Tasks

## Estado actual

Avanzado por la parte de agente/tools (2026-10-10): 1.1, 1.4, 2.3, 4.1, 4.2, 4.5, 5.2, el esqueleto del
golden set y el executor de SQL con la política de regeneración. `pytest -q` → 59 passed, 1 skipped,
9 deselected (los deselected son `integration` y `llm`: `pytest` pasa en una máquina limpia, Art. 6).

Los tests offline del executor usan una conexión inyectada: prueban clamp de filas, timeout,
regeneración y que una sentencia rechazada nunca abre conexión. La verificación contra la base real
está pendiente y se corre con `pytest -m integration`.

**Base local y trazabilidad (2026-10-10):** el esquema real compartido está en `db/schema.sql` (D64,
D65) y corre en Docker (`docker compose up -d --wait`) con los roles `agent_ro` y `agent_logger`,
`agent_runs` y datos de desarrollo. `pytest -q` → 354 passed; `pytest -m integration` → 28 passed contra
Postgres real (permisos por rol, CHECKs, esquema vs whitelist, flujo completo y pgvector). Medición con
base real y `gemini-3.1-flash-lite`: los 5 casos SQL (G1–G5) devuelven el contenido esperado y las 5
consultas quedan en `agent_runs`.

Lo que bloquea la continuación: el seed con volumen (T2.4, T2.5), los PDFs y la ingesta (T3.1–T3.5).
El resto del agente y las tools no depende de nadie.

**Orquestador (2026-10-10):** `agent/agent.py`, `classifier.py`, `tools/rag_tool.py`, los prompts y el
reintento ante 429 están implementados y probados offline (`pytest -q` → 322 passed). El flujo se valida
primero contra un **modelo local** (Strata, servidor OpenAI-compatible) y la **aceptación** se mide con
Gemini (R-2.8). Medición registrada: `gemini-3.1-flash-lite` → 13/13 clasificaciones, 3/3 híbridos con las
dos tools, 1/1 `none` sin tools, 0/8 SQL rechazado (`TP/evidencia/`), con backends falsos: el contenido
no se evalúa hasta que existan el seed y los PDFs. Pendiente: repetir con el modelo definitivo si cambia
(T6.7), verificar idioma y evidencia con casos reales (7.2, 7.3) y la UI (8.x).

**Verificación contra el enunciado (2026-10-11):** se cruzaron los criterios de aprobación, promoción y
entregables de `TP/Enunciado TP - 2026.pdf` con lo implementado. Quedaron cubiertos el agente, el
framework agéntico y SDD; se agregaron las tareas 2.9, 7.6, 7.7 y 9.6–9.9 (idioma inglés, export de
`agent_runs`, volumen de `documentos`, base en la nube, roles en la base compartida, entregables de datos
y coloquio) y se corrigió el README, que marcaba como cubiertos la UI y el despliegue. Medición con el
modelo definitivo (`gemini-3.1-flash-lite`, base local y RAG simulado): 13/13 en clasificación y en
contenido (D71, D72). `pytest -q` → 393 passed; `pytest -m integration` → 28 passed. Después: casos en inglés con idioma
instruido en el prompt (7.2, 7.6, D73) y export de `agent_runs` (7.7) hechos; 9.4 queda con las capturas.

## 1. Setup y entorno

- [x] 1.1 Crear la estructura de carpetas (`db/`, `rag/`, `agent/`, `ui/`, `tests/`, `docker/`) y verificar que `tree` muestra la estructura de `openspec/project.md`
- [x] 1.2 Definir dependencias y verificar que `pip install -r requirements.txt` instala `smolagents`, `psycopg2-binary`, `pypdf`, `google-genai`, `streamlit`, `pytest`, `faker`, `sqlglot`
- [x] 1.3 Crear `docker-compose.yml` con Postgres + pgvector y verificar que `docker compose up -d` levanta la base y que `CREATE EXTENSION vector` funciona
- [x] 1.4 Crear `.env.example` y `.gitignore` y verificar que `grep -rE "GEMINI_API_KEY\s*=\s*[\"']" --include="*.py"` no encuentra claves hardcodeadas (leer el nombre de la variable de `os.environ` no cuenta como hardcodeo)
- [ ] 1.5 Documentar el flujo de arranque en `README.md` y verificar que los comandos del README se ejecutan tal como están escritos
  _(parcial: el README solo lista comandos que existen; `pytest` y `ruff` verificados. Abierta porque faltan `seed`, `ingest` y la UI (T2.4, T3.3, T8.1) y los comandos de `docker compose` no se reejecutaron tal como están escritos)_

## 2. Modelo de datos y datos sintéticos

- [x] 2.1 Escribir `db/schema.sql` con las 7 tablas del dominio (`autores`, `categorias`, `editoriales`, `libros`, `libros_autores`, `socios`, `prestamos`) más `documentos` y `documentos_chunks` (D64) y verificar que `psql -f db/schema.sql` crea el esquema sin errores de FK
- [x] 2.2 Crear el usuario dedicado `agent_ro` con `GRANT SELECT` sobre las 6 tablas, `statement_timeout = 10000` y `search_path` restringido, y verificar que un `INSERT` con ese usuario es rechazado por PostgreSQL (D14, R-3.5)
- [x] 2.3 Crear `agent/config/__init__.py` con el rango de cuatrimestre (2026-08-01 a 2026-11-30), zona horaria única, top-k, umbral, límite de filas y máximo de intentos, y verificar que ningún valor queda hardcodeado en el código (D6, D12, D15, R-3.11)
- [ ] 2.4 Implementar `db/seed_data.py` con semilla fija y verificar que dos ejecuciones con `--seed 42` producen el mismo output
- [ ] 2.5 Verificar el volumen: `SELECT count(*)` ≥ 15 en cada una de las 7 tablas del dominio (el enunciado exige más de 15 registros por tabla); el caso de `documentos` se resuelve en 2.9
- [x] 2.6 Implementar el estado de vencimiento como vista o columna generada (no como valor escrito por el seed) y verificar que coincide con el caso G3 del golden set (D7, R-3.12)
- [ ] 2.7 Verificar las reglas de consistencia: ningún `ejemplares_disponibles > ejemplares_totales`, y todo préstamo vencido cumple `fecha_devolucion_real IS NULL AND CURRENT_DATE > fecha_devolucion_prevista`
- [ ] 2.8 Generar `db/dump.sql` como entregable y verificar que restaura el mismo conteo por tabla
- [ ] 2.9 Decidir y documentar el volumen de `documentos`: con 4–6 PDFs queda por debajo de 15 registros, y el enunciado pide "al menos 15 registros" en cada tabla del modelo. Opciones: cargar ≥ 15 documentos, o justificar en el informe que `documentos` es el índice del repositorio RAG y no una tabla del modelo relacional; verificar que la decisión figura en `TP/CHANGELOG.md` y en el informe (enunciado, criterios de aprobación 1)

## 3. Pipeline de ingesta RAG

- [ ] 3.1 Crear los 4–6 PDFs en `rag/documents/` (responsable: integrante de RAG y base de datos, D19) y verificar que `pypdf` extrae texto de cada uno y que el contenido cubre plazo de devolución, sinopsis, pasos del sistema y horario
- [ ] 3.2 Implementar `rag/chunking.py` por cláusula/párrafo con tope de 800 tokens y solapamiento de 150 desde configuración, y verificar que una cláusula de prueba de más de 800 tokens no queda cortada (D10, R-4.3)
- [ ] 3.3 Implementar `rag/ingest.py` (extracción → chunking → embeddings con `gemini-embedding-001` a 768 dimensiones → pgvector) y verificar que cada chunk guarda id, documento, ubicación, texto, hash y vector (D5, R-4.2)
- [ ] 3.4 Verificar que `documentos_chunks` (esquema compartido, D64) tiene `embedding vector(768)` e índice HNSW `vector_cosine_ops`, y verificar que el índice aparece al inspeccionar la tabla (D5, D13)
- [ ] 3.5 Verificar idempotencia con `sha256(contenido)` como unique: ejecutar la ingesta dos veces sobre el mismo PDF y comprobar que el conteo de chunks no cambia (D11, R-4.5)
- [ ] 3.6 Calibrar top-k = 5 y umbral de similitud = 0.35 según el procedimiento de `TP/05-validacion.md`, y verificar que el valor medido queda registrado en `TP/CHANGELOG.md` con la tabla de similitudes (D12, R-4.8)
- [ ] 3.7 Escribir `tests/test_rag_tool.py` para el retrieval y verificar que las preguntas R1–R3 del golden set devuelven el documento esperado en top-1 (R-4.4)
- [ ] 3.8 Verificar el caso de umbral: una pregunta sin cobertura devuelve "no se encontró información relevante" (R-4.6)

## 4. Tool `execute_sql`

- [x] 4.1 Definir la whitelist de tablas y columnas en `agent/config/schema_whitelist.py` y verificar que coincide con `db/schema.sql` (R-3.4)
- [x] 4.2 Implementar la validación estática con `sqlglot` (parseo con `error_level=RAISE`, statement raíz `SELECT`, extracción de tablas, columnas y funciones, expansión de `*` a la whitelist (R-3.14), normalización de identificadores a minúsculas (R-3.15), rechazo de `FOR UPDATE`) y verificar que los casos adversos S1–S22 de `TP/05-validacion.md` devuelven el error tipado esperado, sin ejecutar ninguna consulta (D4, R-3.2, R-3.3, R-3.4, R-3.7, R-3.13)
- [x] 4.3 Implementar `execute_sql(sql)` que recibe la sentencia ya formada por el agente, ejecuta con el usuario `agent_ro`, aplica límite de 50 filas y timeout de 10 s, y verificar que la tool corre sin credenciales de API (D1, R-3.1, R-3.5, R-3.6, R-3.16) — *implementado en `agent/tools/sql_tool.py`; verificado con Postgres real en `tests/test_sql_tool.py` y `tests/test_runs_integration.py` (`pytest -m integration`, rol `agent_ro`, D45, D46)*
- [x] 4.4 Implementar la regeneración limitada (máximo 2 intentos) y verificar el caso de rechazo-then-éxito y el caso de dos rechazos consecutivos, con reporte del error al usuario (D8, R-3.10, R-5.7) — *el tope lo aplica el orquestador (`ToolSession`, `SQL_MAX_ATTEMPTS`) y se verifica en `tests/test_agent.py` (regeneración con motivo, intentos agotados); `run_with_regeneration()` queda como utilidad de la tool para uso fuera del agente*
- [x] 4.5 Implementar el contrato `SqlResult` y verificar que `tests/test_sql_tool.py` pasa con los 5 casos SQL del golden set (R-3.1, R-3.9)
- [x] 4.6 Verificar el reporte de resultado vacío con un socio sin préstamos (R-3.8)

## 5. Tool `rag_search_tool`

- [x] 5.1 Implementar el retrieval top-k por similitud de coseno con umbral desde configuración y verificar que `tests/test_rag_tool.py` pasa (R-4.4). Embedder y store son protocolos: la política se prueba sin PDFs ni base; la calibración del umbral (R-4.8) queda para `scripts/calibrate_threshold.py` con los documentos reales
- [x] 5.2 Implementar el contrato `RagResult`/`Chunk` con documento y ubicación por fragmento y verificar que una prueba asserts la referencia de origen (R-4.7)

## 6. Orquestador y selección de fuente

- [x] 6.1 Escribir `agent/prompts/system_prompt.md` con rol, esquema resumido, semántica temporal configurada, reglas de selección de fuente y 8 few-shot NL→SQL, y verificar que el prompt exige emitir la clasificación antes de invocar herramientas (R-2.1, R-3.11, D3)
- [x] 6.2 Implementar la clasificación mediante salida estructurada obligatoria (function calling con campo `classification`) y verificar que la clasificación se resuelve antes de la primera invocación a herramienta (D3, R-2.7)
- [x] 6.3 Implementar el `ToolCallingAgent` de Smolagents con las dos tools, temperatura 0, `max_steps = 6` y timeout de API 30 s, y verificar que los 13 casos del golden set producen la clasificación esperada (≥11/13) (D2, D15, R-2.1)
- [x] 6.4 Verificar los 3 casos híbridos: invocan ambas herramientas (R-2.4)
- [x] 6.5 Verificar el caso `none`: no invoca herramientas y no inventa (R-2.5)
- [x] 6.6 Validar el flujo completo contra un **modelo local** (`LLM_MODEL`, `LLM_API_BASE`) con `scripts/measure_golden.py` y verificar clasificación previa a las tools, herramientas por fuente y SQL aceptado por el validador. No cuenta como aceptación (R-2.8)
- [x] 6.7 Repetir la medición con **Gemini** (`GEMINI_API_KEY`, sin cambios de código), versionar la corrida en `TP/evidencia/` consignando el modelo y verificar ≥ 11/13, 3/3 híbridos y 1/1 `none` (R-2.1, R-2.8, R-6.5)
  _(modelo definitivo `gemini-3.1-flash-lite` (D71): 13/13, 3/3 y 1/1, con la última corrida sobre base local y RAG simulado (`TP/05` §4.1). `gemini-3-flash-preview` no entra en la cuota gratuita de 20 requests por día (D70). Contenido 13/13 con el criterio de D72. Salvedades vigentes: el retrieval es simulado y las esperas por cuota inflan la latencia)_

## 7. Composición de respuesta y trazabilidad

- [x] 7.1 Implementar el contrato `AgentAnswer` y verificar que toda respuesta del golden set declara fuente (R-5.2)
  _(contrato y reglas en `agent/contracts.py` + `tests/test_contracts.py`; composición en `LibraryAgent._compose`, `agent/agent.py`; la medición con modelos reales, 13/13 con fuente declarada antes de tools, está en `TP/05` §4.1)_
- [x] 7.2 Verificar idioma de respuesta con un caso en inglés y uno en castellano (R-5.1)
  _(B1 y B2 (`tests/golden_set.py::BILINGUAL_SET`) con `gemini-3.1-flash-lite`: 2/2 con idioma declarado `en`, contenido y prosa en inglés; los 13 casos en castellano salen con la plantilla en castellano. Primera corrida 0/2 por respuesta en castellano; corregido en D73. `TP/05` §4.1)_
- [ ] 7.3 Verificar la evidencia exhibida: SQL muestra la sentencia, RAG muestra el fragmento citado (R-5.3, R-5.4)
- [x] 7.4 Crear la tabla `agent_runs` y verificar que una consulta exitosa genera una fila con los ocho campos (R-6.1, R-6.2)
- [x] 7.5 Verificar que una consulta rechazada también genera una fila con el motivo (R-6.3)
- [x] 7.6 Agregar al golden set dos casos en **inglés** (uno SQL y uno RAG, ids `B1` y `B2`), **fuera** de los 13 que miden R-2.1 para no cambiar el criterio ≥ 11/13, y verificar con el modelo definitivo que se clasifican bien y la respuesta sale en inglés. El enunciado pide "castellano o inglés" y los 13 casos actuales están en castellano; 7.2 depende de esto (R-5.1)
  _(B1 (SQL) y B2 (RAG), flag `--bilingual` en `measure_golden.py`, fuera del denominador de R-2.1; D73)_
- [x] 7.7 Implementar `scripts/export_runs.py` que vuelque `agent_runs` a un archivo versionado en `TP/evidencia/`, y verificar que contiene las 13 consultas del golden set con sus campos. El fixture de integración hace `TRUNCATE agent_runs` (`tests/test_runs_integration.py`), así que exportar **antes** de correr `pytest -m integration`; la tabla no es una evidencia durable (R-6.1, R-6.2)
  _(`scripts/export_runs.py` (`--last N`), 7 tests; exportadas las 15 consultas en `TP/evidencia/agent_runs_2026-10-11.json`)_

## 8. Interfaz Streamlit

- [ ] 8.1 Implementar `ui/app.py` con campo de texto, respuesta, fuente y evidencia, y verificar que una consulta de prueba muestra las tres secciones (R-5.3, R-5.4)
- [ ] 8.2 Verificar el rechazo de consulta vacía: no se invoca el agente (R-1.2)
- [ ] 8.3 Verificar que el historial en `st.session_state` es solo visual y no alimenta al agente, en una sesión de 3 consultas (D17)

## 9. Integración y despliegue

- [ ] 9.1 Ejecutar el golden set completo contra el sistema integrado y verificar que `tests/test_golden_set.py` pasa sin regresiones, con aserción sobre clasificación, SQL y filas (no sobre la prosa) y rúbrica manual de 3 criterios para el texto (D16)
  _(esqueleto con los 13 casos y los 4 de retrieval en `tests/golden_set.py`; las afirmaciones están marcadas `llm` y se saltan hasta que exista el agente)_
- [ ] 9.2 Crear `docker/Dockerfile` y verificar que la imagen se construye y corre localmente
- [ ] 9.3 Desplegar en Cloud Run + Cloud SQL con Secret Manager y verificar que las mismas 13 preguntas responden igual que en local
- [ ] 9.4 Exportar `agent_runs` con las 13 consultas (con 7.7) y capturas de funcionamiento como evidencias para el informe. El enunciado pide "capturas, logs": si la UI (8.x) no llega, las capturas son de la terminal con `scripts/measure_golden.py`
- [ ] 9.5 Redactar el informe técnico (máx. 10 páginas) con modelo de datos, arquitectura, consultas de ejemplo y evidencias, y verificar que cubre los 4 puntos exigidos por el enunciado

- [ ] 9.6 Decidir dónde vive la base en la nube: la de **Neon** que ya comparte el equipo o **Cloud SQL** (D18). El enunciado exige que el agente y la base estén en un servicio cloud; Neon ya cumple la parte de la base y evita el riesgo de pgvector en Cloud SQL. Verificar que la decisión queda en `TP/CHANGELOG.md` con su motivo y, si cambia D18, que se registra como reemplazo
- [ ] 9.7 Aplicar en la base compartida los roles `agent_ro` y `agent_logger`, sus permisos y `db/migrations/001_agent_runs.sql` (hoy solo existen en el Docker local), con `PGSSLMODE=require`, y verificar que `pytest -m integration` pasa contra esa base y que `agent_ro` no puede escribir ni leer `agent_runs` (D14, D63). Requiere al dueño de la base
- [ ] 9.8 Verificar los entregables de datos ("Datos empleados: bases de datos y archivos PDF"): `db/dump.sql` y `rag/documents/*.pdf` están versionados y ninguna regla de `.gitignore` los excluye; desde un clon limpio, `docker compose up -d --wait` y la ingesta reproducen la base (2.8, 3.1)
- [ ] 9.9 Preparar el coloquio (23 o 30/10/2026, criterio de aprobación): guion de demostración con una consulta SQL, una RAG, una híbrida y una sin cobertura; respuestas preparadas sobre las decisiones técnicas (`TP/CHANGELOG.md`), los límites del sistema (retrieval simulado hasta la ingesta, cuota de la API, modelo local vs definitivo) y qué mide cada evidencia

## Workflow follow-up

- Archivar el change con `openspec archive agente-y-tools` cuando las tareas estén completas.
- Correr `openspec validate --strict` antes de archivar.
