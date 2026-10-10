# Tasks

## 1. Setup y entorno

- [ ] 1.1 Crear la estructura de carpetas (`db/`, `rag/`, `agent/`, `ui/`, `tests/`, `docker/`) y verificar que `tree` muestra la estructura de `openspec/project.md`
- [ ] 1.2 Definir dependencias y verificar que `pip install -r requirements.txt` instala `smolagents`, `psycopg2-binary`, `pypdf`, `google-genai`, `streamlit`, `pytest`, `faker`
- [ ] 1.3 Crear `docker-compose.yml` con Postgres + pgvector y verificar que `docker compose up -d` levanta la base y que `CREATE EXTENSION vector` funciona
- [ ] 1.4 Crear `.env.example` y `.gitignore` y verificar que `grep -r "GEMINI_API_KEY" --include="*.py"` no encuentra claves hardcodeadas
- [ ] 1.5 Documentar el flujo de arranque en `README.md` y verificar que los comandos del README se ejecutan tal como están escritos

## 2. Modelo de datos y datos sintéticos

- [ ] 2.1 Escribir `db/schema.sql` con las 6 tablas y verificar que `psql -f db/schema.sql` crea el esquema sin errores de FK
- [ ] 2.2 Crear el usuario dedicado `agent_ro` con `GRANT SELECT` sobre las 6 tablas, `statement_timeout = 10000` y `search_path` restringido, y verificar que un `INSERT` con ese usuario es rechazado por PostgreSQL (D14, R-3.5)
- [ ] 2.3 Crear `agent/config.py` con el rango de cuatrimestre (2026-08-01 a 2026-11-30), zona horaria única, top-k, umbral, límite de filas y máximo de intentos, y verificar que ningún valor queda hardcodeado en el código (D6, D12, D15, R-3.11)
- [ ] 2.4 Implementar `db/seed_data.py` con semilla fija y verificar que dos ejecuciones con `--seed 42` producen el mismo output
- [ ] 2.5 Verificar el volumen: `SELECT count(*)` ≥ 15 en cada una de las 6 tablas
- [ ] 2.6 Implementar el estado de vencimiento como vista o columna generada (no como valor escrito por el seed) y verificar que coincide con el caso G3 del golden set (D7, R-3.12)
- [ ] 2.7 Verificar las reglas de consistencia: ningún `ejemplares_disponibles > ejemplares_totales`, y todo préstamo vencido cumple `fecha_devolucion_real IS NULL AND CURRENT_DATE > fecha_devolucion_prevista`
- [ ] 2.8 Generar `db/dump.sql` como entregable y verificar que restaura el mismo conteo por tabla

## 3. Pipeline de ingesta RAG

- [ ] 3.1 Crear los 4–6 PDFs en `rag/documents/` (responsable: integrante de RAG y base de datos, D19) y verificar que `pypdf` extrae texto de cada uno y que el contenido cubre plazo de devolución, sinopsis, pasos del sistema y horario
- [ ] 3.2 Implementar `rag/chunking.py` por cláusula/párrafo con tope de 800 tokens y solapamiento de 150 desde configuración, y verificar que una cláusula de prueba de más de 800 tokens no queda cortada (D10, R-4.3)
- [ ] 3.3 Implementar `rag/ingest.py` (extracción → chunking → embeddings con `gemini-embedding-001` a 768 dimensiones → pgvector) y verificar que cada chunk guarda id, documento, ubicación, texto, hash y vector (D5, R-4.2)
- [ ] 3.4 Crear la tabla `documentos_embeddings` con `vector(768)` e índice HNSW `vector_cosine_ops`, y verificar que el índice aparece al inspeccionar la tabla (D5, D13)
- [ ] 3.5 Verificar idempotencia con `sha256(contenido)` como unique: ejecutar la ingesta dos veces sobre el mismo PDF y comprobar que el conteo de chunks no cambia (D11, R-4.5)
- [ ] 3.6 Calibrar top-k = 5 y umbral de similitud = 0.35 según el procedimiento de `TP/05-validacion.md`, y verificar que el valor medido queda registrado en `TP/CHANGELOG.md` con la tabla de similitudes (D12, R-4.8)
- [ ] 3.7 Escribir `tests/test_rag_tool.py` para el retrieval y verificar que las preguntas R1–R3 del golden set devuelven el documento esperado en top-1 (R-4.4)
- [ ] 3.8 Verificar el caso de umbral: una pregunta sin cobertura devuelve "no se encontró información relevante" (R-4.6)

## 4. Tool `execute_sql`

- [ ] 4.1 Definir la whitelist de tablas y columnas en `agent/config/schema_whitelist.py` y verificar que coincide con `db/schema.sql` (R-3.4)
- [ ] 4.2 Implementar la validación estática con `sqlglot` (parseo del statement raíz, extracción de tablas y columnas) y verificar que los 10 casos adversos de `TP/05-validacion.md` devuelven el error tipado esperado, sin ejecutar ninguna consulta (D4, R-3.2, R-3.3, R-3.7)
- [ ] 4.3 Implementar `execute_sql(sql)` que recibe la sentencia ya formada por el agente, ejecuta con el usuario `agent_ro`, aplica límite de 50 filas y timeout de 10 s, y verificar que la tool corre sin credenciales de API (D1, R-3.1, R-3.5, R-3.6)
- [ ] 4.4 Implementar la regeneración limitada (máximo 2 intentos) y verificar el caso de rechazo-then-éxito y el caso de dos rechazos consecutivos, con reporte del error al usuario (D8, R-3.10, R-5.7)
- [ ] 4.5 Implementar el contrato `SqlResult` y verificar que `tests/test_sql_tool.py` pasa con los 5 casos SQL del golden set (R-3.1, R-3.9)
- [ ] 4.6 Verificar el reporte de resultado vacío con un socio sin préstamos (R-3.8)

## 5. Tool `rag_search_tool`

- [ ] 5.1 Implementar el retrieval top-k por similitud de coseno con umbral desde configuración y verificar que `tests/test_rag_tool.py` pasa (R-4.4)
- [ ] 5.2 Implementar el contrato `RagResult`/`Chunk` con documento y ubicación por fragmento y verificar que una prueba asserts la referencia de origen (R-4.7)

## 6. Orquestador y selección de fuente

- [ ] 6.1 Escribir `agent/prompts/system_prompt.md` con rol, esquema resumido, semántica temporal configurada, reglas de selección de fuente y 8 few-shot NL→SQL, y verificar que el prompt exige emitir la clasificación antes de invocar herramientas (R-2.1, R-3.11, D3)
- [ ] 6.2 Implementar la clasificación mediante salida estructurada obligatoria (function calling con campo `classification`) y verificar que la clasificación se resuelve antes de la primera invocación a herramienta (D3, R-2.7)
- [ ] 6.3 Implementar el `ToolCallingAgent` de Smolagents con las dos tools, temperatura 0, `max_steps = 6` y timeout de API 30 s, y verificar que los 13 casos del golden set producen la clasificación esperada (≥11/13) (D2, D15, R-2.1)
- [ ] 6.4 Verificar los 3 casos híbridos: invocan ambas herramientas (R-2.4)
- [ ] 6.5 Verificar el caso `none`: no invoca herramientas y no inventa (R-2.5)

## 7. Composición de respuesta y trazabilidad

- [ ] 7.1 Implementar `agent/response.py` con el contrato `AgentAnswer` y verificar que toda respuesta del golden set declara fuente (R-5.2)
- [ ] 7.2 Verificar idioma de respuesta con un caso en inglés y uno en castellano (R-5.1)
- [ ] 7.3 Verificar la evidencia exhibida: SQL muestra la sentencia, RAG muestra el fragmento citado (R-5.3, R-5.4)
- [ ] 7.4 Crear la tabla `agent_runs` y verificar que una consulta exitosa genera una fila con los ocho campos (R-6.1, R-6.2)
- [ ] 7.5 Verificar que una consulta rechazada también genera una fila con el motivo (R-6.3)

## 8. Interfaz Streamlit

- [ ] 8.1 Implementar `ui/app.py` con campo de texto, respuesta, fuente y evidencia, y verificar que una consulta de prueba muestra las tres secciones (R-5.3, R-5.4)
- [ ] 8.2 Verificar el rechazo de consulta vacía: no se invoca el agente (R-1.2)
- [ ] 8.3 Verificar que el historial en `st.session_state` es solo visual y no alimenta al agente, en una sesión de 3 consultas (D17)

## 9. Integración y despliegue

- [ ] 9.1 Ejecutar el golden set completo contra el sistema integrado y verificar que `tests/test_golden_set.py` pasa sin regresiones, con aserción sobre clasificación, SQL y filas (no sobre la prosa) y rúbrica manual de 3 criterios para el texto (D16)
- [ ] 9.2 Crear `docker/Dockerfile` y verificar que la imagen se construye y corre localmente
- [ ] 9.3 Desplegar en Cloud Run + Cloud SQL con Secret Manager y verificar que las mismas 13 preguntas responden igual que en local
- [ ] 9.4 Exportar `agent_runs` con las 13 consultas y capturas de la UI como evidencias para el informe
- [ ] 9.5 Redactar el informe técnico (máx. 10 páginas) con modelo de datos, arquitectura, consultas de ejemplo y evidencias, y verificar que cubre los 4 puntos exigidos por el enunciado

## Workflow follow-up

- Archivar el change con `openspec archive agente-y-tools` cuando las tareas estén completas.
- Correr `openspec validate --strict` antes de archivar.
