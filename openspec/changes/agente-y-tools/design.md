# Design

## Context

El change cubre el agente, sus tools y la API HTTP. El estado de lo implementado se sigue en
`tasks.md`, que es el lugar canónico. La motivación está en `proposal.md`. Las
restricciones que condicionan el diseño son las de `TP/00-constitucion.md` (read-only por diseño,
proveniencia obligatoria, trazabilidad de ejecución) y los criterios de promoción elegidos: el de
despliegue en la nube queda descartado por D81; siguen cubiertos framework agéntico y SDD, y el de interfaz
gráfica la provee la SPA de `web/`, un cliente de la API (D80, D93).

Condición de contorno: tres integrantes trabajando en paralelo, lo que exige contratos de interfaz
definidos antes de implementar, para que las tools se puedan desarrollar y testear de forma aislada.

## Goals / Non-Goals

**Goals:**
- Un orquestador que clasifique la consulta y seleccione la herramienta adecuada.
- Tools independientes, testeables sin el orquestador.
- Seguridad de SQL en tres capas.
- Evidencia automática de funcionamiento (registro por consulta).

**Non-Goals:**
- Memoria conversacional multi-turno (v1 es single-turn).
- Observabilidad con LangSmith ni evaluación automática de calidad de respuestas.
- Fine-tuning.
- Escritura sobre la base de datos.
- Autenticación de usuarios y streaming de **tokens** del modelo. Sí hay streaming de **progreso** de la
  consulta (D75) y reintentos ante límite de cuota (D57).

## Decisions

La justificación completa (alternativa descartada y motivo) vive en `TP/CHANGELOG.md`, que es el
registro canónico y el entregable del informe. Acá queda solo el índice, para no mantener dos copias
del mismo contenido.

| ID | Decisión | Traza |
|---|---|---|
| D1 | El agente genera el SQL; `execute_sql` solo valida y ejecuta | R-3.1 |
| D2 | `ToolCallingAgent`, no `CodeAgent` | `02 §5.1` |
| D3 | Clasificación en salida estructurada obligatoria | R-2.7 |
| D4 | Validación estática con `sqlglot`, no regex | R-3.2–R-3.4 |
| D5 | `gemini-embedding-001` con `output_dimensionality = 768` | R-4.2 |
| D6 | Semántica temporal desde configuración (2026-08-01 a 2026-11-30) | R-3.11 |
| D7 | Estado de vencimiento calculado, no almacenado | R-3.12 |
| D8 | Regeneración de SQL limitada a 2 intentos | R-3.10, R-5.7, R-6.4 |
| D9 | psycopg2 directo, no SQLAlchemy | R-3.5, R-3.6 |
| D10 | Chunking por cláusula, tope 800 / solapamiento 150 — el tope y el solapamiento se reemplazaron por D97 | R-4.3 |
| D11 | Idempotencia por `sha256(contenido)` — precisada por D66 y D98: el hash es el del archivo y el unique es `(documento_id, chunk_index)` | R-4.5 |
| D12 | top-k = 5, umbral calibrado con medición: 0.35 hipótesis, 0.67 (D85), vigente 0.64 provisorio (D88) | R-4.4, R-4.8 |
| D13 | Índice HNSW `vector_cosine_ops` | T3.4 |
| D14 | Usuario dedicado `agent_ro` + timeout + `search_path` | R-3.5 |
| D15 | `max_steps = 6`, temperatura 0, timeout de API 30 s | Art. 7, R-6.2 |
| D16 | Aserción sobre clasificación, SQL y filas; prosa con rúbrica manual | Art. 6, Art. 7 |
| D17 | El historial no alimenta al agente (lo conserva el frontend; v1 es de un solo turno) | R-7.0 |
| D18 | ~~Cloud Run + Cloud SQL + Secret Manager~~ — reemplazado por D81 (entorno local) | criterio de promoción 1 |
| D19 | PDFs generados por el integrante de RAG y base de datos | G6–G9, R1–R3 |
| D20 | Un artefacto, un solo lugar | `TP/README.md` |
| D21 | Whitelist excluye `agent_runs`, `documentos` y `documentos_chunks` | R-3.4 |
| D22 | La vista de estado calculado (`v_prestamos_estado`) en la whitelist | R-3.12 |
| D23 | Mapa alias→tabla antes de la whitelist (CTEs y alias) — **reemplazada por D38** | R-3.4 |
| D24 | El límite de 50 filas lo aplica la ejecución, no la validación | R-3.6 |
| D25 | `SELECT *` se expande a las columnas de la whitelist | R-3.14 |
| D26 | Allowlist de funciones, código `FUNCTION_NOT_ALLOWED` | R-3.13 |
| D27 | `FOR UPDATE` rechazado como no-lectura | R-3.2 |
| D28 | Identificadores normalizados a minúsculas | R-3.15 |
| D29 | `error_level=RAISE` en el parseo | R-3.3 |
| D30 | Se registra la sentencia normalizada; `sql_original` conserva la del modelo | R-3.9, R-6.4 |
| D31 | Los literales no se modifican por la normalización | Art. 4 |
| D32 | Sin política de PII: acceso uniforme a la información del dominio | Art. 11, R-3.4 |
| D33 | Fallo de ejecución con código `EXECUTION_ERROR` | R-3.16 |
| D34 | `pytest` excluye por defecto `integration` y `llm` | Art. 6 |
| D35 | `psycopg2` importado de forma diferida | Art. 6 |
| D36 | ~~Modelo por defecto `gemini-3-flash-preview`~~ — reemplazado por D71 | D15, `pytest -m llm` |
| D37 | Cliente de `google-genai` en variable, no encadenado | `tests/test_llm_smoke.py` |
| D38 | Tablas y columnas resueltas por scope (reemplaza el mapa global de D23) | R-3.4, R-3.14 |
| D39 | Nodos de escritura rechazados en cualquier posición del árbol | R-3.2 |
| D40 | Schema distinto de `public` rechazado | R-3.4 |
| D41 | Allowlist contra el nombre emitido por postgres; `CASE`/`EXISTS`/`AND` no son funciones | R-3.13 |
| D42 | `SELECT` sin `FROM` permitido si no lee columnas | R-3.4 |
| D43 | `;` final tolerado | R-3.3 |
| D44 | Columnas de salida repetidas desambiguadas; alias naturales | R-3.9, R-3.14 |
| D45 | Conexión de solo lectura, perezosa, con rollback y cierre | R-3.18 |
| D46 | `timeout_ms` efectivo con `SET LOCAL`; SQLSTATE `57014` | R-3.6 |
| D47 | Zona horaria `APP_TIMEZONE` aplicada a la sesión SQL | R-3.11 |
| D48 | `SqlResult.truncated` declara el truncado a 50 filas | R-3.6 |
| D49 | La regeneración recibe el motivo del rechazo anterior | R-3.10, R-5.7 |
| D50 | Vocabulario de clasificación único: `sql`/`rag`/`hybrid`/`none` | R-2.1 |
| D51 | ~~`prestamos.estado` fuera de la whitelist~~ — reemplazado por D64 | R-3.12 |
| D52 | `AgentAnswer`: `answer_kind`, `trace`, evidencia por fuente | R-2.4, Art. 4 |
| D53 | `QUERY_TOO_COMPLEX`: sin `WITH RECURSIVE`, tope de tablas | R-3.17 |
| D54 | Dependencias de ejecución y desarrollo separadas, con cotas | Art. 8 |
| D55 | Golden set con entidades concretas y checks independientes del alias | D16 |
| D56 | Proveedor del LLM configurable (LiteLLM); clasificador agnóstico | D15, R-2.7 |
| D57 | Reintento ante 429 respetando la espera de la API | D15, Art. 7 |
| D58 | Fuentes declaradas = invocadas; fallos con plantilla fija | R-2.7, R-5.2, R-5.7 |
| D59 | Medición sin base: backends falsos y validador real; evidencia versionada | R-2.1 |
| D60 | ~~Contrato de lectura de `documentos_embeddings`~~ — reemplazado por D66 | R-4.2, R-4.4 |
| D61 | `max_steps + 1` llamadas al modelo en smolagents | D15 |
| D62 | Clasificador no-Gemini con 4096 tokens y motivo real del fallo | R-2.8, R-5.7 |
| D63 | Dos roles: `agent_ro` (lectura) y `agent_logger` (solo `INSERT` en `agent_runs`) | R-3.5, R-6.2 |
| D64 | Se adopta el esquema real compartido (N:M autores, vista `v_prestamos_estado`, `estado` solo activo/devuelto); reemplaza D51 | R-3.4, R-3.12 |
| D65 | `db/schema.sql` normalizado desde el DDL exportado, base local en Docker y datos de desarrollo | T1.3, T2.1 |
| D66 | La recuperación lee `documentos_chunks` + `documentos`; la ubicación sale de `metadata` | R-4.2, R-4.7 |
| D67 | `agent_runs` se arma solo desde el `AgentAnswer` y su fallo no rompe la respuesta | R-6.1, R-6.3 |
| D68 | `POSTGRES_HOST=127.0.0.1` por defecto (en Windows `localhost` cuesta ~2 s por conexión) | T1.3 |
| D69 | Corpus simulado de RAG para medir contenido sin PDFs; no calibra el umbral | R-2.8, D59 |
| D70 | El clasificador de Gemini conserva el motivo del fallo de la API | R-5.7, D62 |
| D71 | Modelo definitivo y por defecto: `gemini-3.1-flash-lite` (reemplaza D36) | R-2.1, R-2.8 |
| D72 | El check de los híbridos exige SQL ejecutado y fragmento citado, no filas no vacías | R-3.8, D16 |
| D73 | Idioma de la respuesta instruido en el prompt, declarado en la evidencia y verificado con casos en inglés aparte | R-5.1, D16 |
| D74 | Dockerfile multi-etapa (`base`, `measure`, `runtime`), sin secretos y sin tests en la imagen que se ejecuta (D81) | D18, Art. 8, Art. 9 |
| D75 | `POST /ask` con streaming de progreso real y el `AgentAnswer` completo al final; sin tokens | R-7.1, R-7.2, D58 |
| D76 | Cancelación cooperativa por desconexión del cliente; la consulta cancelada no se registra | R-7.5, R-6.7 |
| D77 | `LibraryAgent.answer()` serializa las consultas con un lock | R-1.3 |
| D78 | ~~UI Streamlit en proceso; imagen `runtime` arranca Streamlit~~ — reemplazado por D80 | D18 |
| D79 | Correcciones al streaming: marcador de fin de agente y `duration_s` siempre numérico | R-7.3, R-7.2 |
| D80 | Sin UI propia: el agente es accesible solo por la API HTTP y el frontend es un cliente externo; la imagen `runtime` sirve la API | R-7.0, D18 |
| D81 | No se despliega en la nube: el sistema se prepara para correr en entorno local (Docker + `uvicorn`) | D18, criterio de promoción 1 |
| D82 | CORS con allowlist `API_ALLOWED_ORIGINS`, sin wildcard y sin autenticación | R-7.8, D81 |
| D93 | La interfaz gráfica vuelve como cliente de la API (`web/`, change `frontend-web-vite`); la API sigue siendo el único acceso al agente y la imagen `runtime` no sirve interfaz | R-7.0, D80 |
| D83 | Riesgo de promoción aceptado explícitamente: margen 2/5, desviación del requisito de nube y confirmación con la cátedra abierta | criterios de promoción 1 y 3, D18, D80, D81 |
| D84 | La fuente se declara solo en `sources`; el texto de `answer` no lleva línea de fuente | R-5.2, R-2.6, D58 |
| D85 | Umbral de similitud 0.67, calibrado con consultas reales — precisado por D88 (0.64, poblaciones que se solapan) | R-4.6, D12 |
| D86 | Se elimina el manual de uso del corpus del RAG | R-4.6, D16, D85 |
| D87 | Ampliación del catálogo y de las reseñas | D85 |
| D88 | Umbral provisorio 0.64 y editoriales en el prompt | D87 |
| D89 | Un solo seed y prompt de editoriales genérico | T2.4, T6.1, D87, D88 |
| D90 | Las reseñas no son datos de la base | T6.1, D88 |
| D91 | `docker compose up` carga el catálogo completo | T1.3, T2.4, D87 |
| D92 | `docker compose up` también ingesta el RAG | T3.3, T9.2, D91 |
| D94 | Pedidos de escritura, una sola nota y mensajes con carácter | R-2.9, R-5.8, R-5.9 |
| D95 | La SPA presenta `answer` como Markdown (`react-markdown` + `remark-gfm`), sin HTML crudo | R-8.11, R-8.7 |
| D96 | La frase de los mensajes fijos va en el título | T7.8, D94 |
| D97 | El chunking es por sección `## `, sin tope de tokens ni solapamiento | R-4.3, R-4.7, R-9.4 |
| D98 | La clave de idempotencia es el `sha256` del PDF en `documentos`; el unique del fragmento es `(documento_id, chunk_index)` (precisa D11) | R-4.5, D66 |
| D99 | R-7.9 se cumple en la herramienta SQL (whitelist), no en los permisos del rol | R-7.9, R-3.4, D63 |

## Risks / Trade-offs

- **[Text-to-SQL poco preciso]** → mitigación: few-shot de 8 ejemplos en el prompt + golden set de 5 casos SQL que se ejecuta en CI local con `pytest`.
- **[Clasificación de fuente inestable por no determinismo]** → mitigación: temperatura 0, golden set de 13 casos, umbral de aceptación ≥11/13 documentado en `TP/05-validacion.md`.
- **[Retrieval devuelve fragmentos irrelevantes y el agente alucina]** → mitigación: umbral de similitud mínimo (R-4.6) obliga a declarar "no se encontró información relevante". Con los documentos reales el margen es angosto y las poblaciones de casos con y sin cobertura se solapan (D87, D88): el umbral es solo un filtro grueso y la segunda barrera es el clasificador.
- ~~**[Cloud SQL sin pgvector disponible en la región/cuota]**~~ — descartado por D81 (entorno local).
- **[Margen mínimo de promoción: 2 de 5 sin nube]** → mitigación: el tercer criterio es la interfaz gráfica, la SPA de `web/` sobre la API (D80, D93); confirmar con la cátedra; registrado en D83.
- **[Un modelo local valida el flujo pero no es el modelo definitivo]** → mitigación: R-2.8 separa
  "validación del flujo" de "aceptación"; la evidencia consigna el modelo (R-6.5) y el golden set se repite
  con Gemini antes de dar por cumplido R-2.1. Un modelo local más débil genera SQL peor (medido: inventó una
  columna) pero eso lo frena el validador, no cambia el criterio.
- **[Cuota gratuita de la API: ~5 req/min y 20 req/día con `gemini-3-flash-preview`]** → mitigación:
  reintento con la espera que informa la API (D57) y medición con un modelo de mayor cuota
  (`gemini-3.1-flash-lite`). El golden set usa ~50 llamadas: **no entra** en 20 por día, así que
  `gemini-3-flash-preview` no puede completar la medición con la clave gratuita; por eso el modelo
  definitivo es `gemini-3.1-flash-lite` (D70, D71).
- **[Costo de tokens por el ciclo SDD]** → mitigación: artefactos cortos, constitution de 1 página, tareas sin narrativa.

## Migration Plan

1. `docker compose up` con Postgres + pgvector en local.
2. `db/schema.sql` (esquema compartido normalizado, D65) y `db/migrations/001_agent_runs.sql`; roles
   `agent_ro` y `agent_logger` con `db/init/10-roles.sh`. Todo se levanta con `docker compose up -d --wait`.
3. Datos: `db/seed.sql` (catálogo completo, 70 libros) lo carga `docker compose up` con `DEV_SEED=full`
   (D91); `DEV_SEED=1` carga `db/dev_seed.sql` (7 libros, el que usan los tests de integración). El
   entregable `db/dump.sql` está pendiente (T2.8).
4. `rag/ingest.py` sobre los PDFs.
5. **Validación del flujo contra un modelo local** (`LLM_MODEL=openai/<id>`, `LLM_API_BASE=http://127.0.0.1:<puerto>/v1`):
   confirma clasificación previa, tools por fuente, límites y composición sin consumir cuota (R-2.8, D56).
6. **Medición de aceptación con Gemini** (`GEMINI_API_KEY`, sin cambios de código): se repite el golden set
   completo y la evidencia se versiona en `TP/evidencia/` con el modelo usado. Los resultados del modelo
   local no cuentan como aceptación (D59).
7. Despliegue local (D81): `docker compose` para Postgres + pgvector; imagen `runtime` o
   `uvicorn api.app:app`; `GEMINI_API_KEY` vía `.env` y `docker run --env-file`.
8. Rollback: la ejecución local no muta datos; basta con volver a levantar la imagen o el commit anterior.

## Open Questions

Las tres preguntas que había se cerraron: evaluación del golden set (D16), semántica temporal
(D6) y origen de los PDFs (D19). Lo que queda abierto son decisiones y mediciones, y vive en `tasks.md`
por su ID: 9.11, 9.13 y 2.9. El umbral de similitud se cerró con evidencia en 0.67 (D85) y quedó en 0.64
provisorio (D88); T3.6 sigue abierta hasta que la calibración separe las poblaciones.
