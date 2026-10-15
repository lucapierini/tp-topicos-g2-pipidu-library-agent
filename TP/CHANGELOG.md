# CHANGELOG — Decisiones de diseño

> Registro incremental del ciclo SDD. Cada decisión relevante se consigna aquí con fecha,
> alternativa descartada y motivo. Es el artefacto que la cátedra pide adjuntar.
>
> Los IDs `D1…D18` son los mismos que usa `openspec/changes/agente-y-tools/design.md`. La numeración
> anterior (D8–D13 de la tabla de "decisiones vigentes") quedó **superada** por esta.

---

## 2026-10-08 — Ciclo SDD orientado al agente y sus tools

**Decisión:** completar el ciclo `Requirement → Spec → Plan → Tasks → Validation` con los dos
artefactos que faltaban (`04-tareas.md`, `05-validacion.md`) y agregar la constitución (`00-constitucion.md`).

**Decisión:** adoptar OpenSpec como herramienta de estandarización grupal, manteniendo los artefactos
en Markdown plano dentro de `TP/` para que sean directamente adjuntables al informe.

**Alternativa descartada:** Spec-Kit. Motivo: constitution + templates + slash commands implican
mayor ceremonia y costo de tokens para un trabajo de 3 personas con un informe de 10 páginas.
Se retoma solo si el grupo necesita checkpoints de clarificación formales.

**Decisión:** los criterios de aceptación pasan a formato GIVEN / WHEN / THEN, porque los checkboxes
previos no eran verificables.

---

## 2026-10-10 — Cierre de las decisiones pendientes

Las 15 decisiones abiertas se cierran aquí. Las que estaban registradas como "Pendiente" (acceso a
datos, chunking, memoria, despliegue) quedan resueltas con alternativa descartada y motivo.

### D1 — Contrato invertido: el agente genera el SQL, la tool solo valida y ejecuta
`execute_sql(sql)` recibe la sentencia ya formada.
**Descartado:** que la tool reciba la pregunta y genere SQL con una llamada interna al modelo.
**Motivo:** en Smolagents el LLM es el agente; una llamada anidada saca la decisión fuera del loop,
impide atribuir el SQL al agente y hace la tool no testeable sin credenciales de API.
**Traza:** R-3.1.

### D2 — `ToolCallingAgent`, no `CodeAgent`
**Motivo:** `CodeAgent` exige un ejecutor de código (local o E2B), lo que agrega un sandbox en Cloud Run
y una superficie de ejecución que contradice el Art. 3 de la constitución. El TP exige un framework
agéntico, no ejecución de código.
**Traza:** `02 §5.1`.

### D3 — Clasificación mediante salida estructurada obligatoria
Function calling con campo `classification` antes de cualquier invocación.
**Descartado:** instrucción de texto libre en el prompt.
**Motivo:** R-2.1 exige clasificación observable y medible (≥11/13); el texto libre no es verificable.
**Traza:** R-2.7.

### D4 — Validación estática con `sqlglot`, no regex
Parseo del statement raíz y extracción de tablas/columnas.
**Motivo:** regex no distingue CTEs, subqueries ni identificadores entre comillas, así que R-3.4 no era
testeable (casos S5, S7 del set adverso).
**Traza:** R-3.2, R-3.3, R-3.4.

### D5 — Embeddings: `gemini-embedding-001` con `output_dimensionality = 768`
**Descartado:** `text-embedding-004` (768), deprecado; y 3072 dimensiones por defecto.
**Motivo:** define la columna `vector(768)` de `documentos_embeddings`; se fija 768 para mantener la
tabla liviana sin pérdida relevante de calidad. Impacta `db/schema.sql`.
**Traza:** R-4.2, T2.3.

### D6 — Semántica temporal desde configuración
Rango de cuatrimestre fijo **2026-08-01 a 2026-11-30**, `CURRENT_DATE` y zona horaria única.
**Descartado:** dejar la interpretación temporal al modelo.
**Motivo:** G2, G10 y los casos T1 del set de validación dependen de que "este cuatrimestre" y "hace 20
días" no sean ambiguos.
**Traza:** R-3.11.

### D7 — Estado de vencimiento calculado, no almacenado
Vista o columna generada a partir de las fechas; el seed no escribe `estado`.
**Motivo:** evita que G3 dé resultados distintos según el momento de ejecución.
**Traza:** R-3.12.

### D8 — Regeneración de SQL limitada a 2 intentos
El agente puede regenerar una sentencia rechazada una vez; al segundo rechazo se reporta el error.
**Descartado:** cero reintentos (fragilidad ante errores menores) y reintentos sin límite (costo y
latencia indefinidos).
**Motivo:** la regeneración es la única tolerancia al error del modelo; el límite la mantiene medible
en `agent_runs.attempts`.
**Traza:** R-3.10, R-5.7, R-6.4, casos S11–S12.

### D9 — Capa de acceso a datos: psycopg2 directo
**Descartado:** SQLAlchemy.
**Motivo:** un solo `SELECT` dinámico; el ORM entorpece la validación estática y el control del timeout.
**Traza:** Art. 3, R-3.5, R-3.6.

### D10 — Chunking por cláusula, tope 800 tokens, solapamiento 150
**Descartado:** chunking fijo por caracteres.
**Motivo:** los documentos son normativos, donde una cláusula suele cruzar el corte de página; cortar
una cláusula arruina el retrieval (R2 del set de retrieval).
**Traza:** R-4.3.

### D11 — Idempotencia por `sha256(contenido)` como unique del chunk
**Traza:** R-4.5.

### D12 — top-k = 5, umbral de similitud calibrado contra los PDFs reales
Valor inicial 0.35; la calibración (T3.6) lo fijó en **0.67**: ver D75.
**Motivo:** el umbral sin calibración convierte R-4.6 en un número arbitrario.
**Traza:** R-4.4, R-4.8, R4 del set de retrieval.

### D13 — Índice vectorial HNSW con `vector_cosine_ops`
**Motivo:** con ~100 chunks el rendimiento es irrelevante; se mantiene porque es demostrable en el
informe y coherente con la elección de pgvector.
**Traza:** T3.4.

### D14 — Rol de solo lectura como usuario dedicado `agent_ro`
`GRANT SELECT` sobre las 6 tablas, `statement_timeout = 10000`, `search_path` restringido.
**Descartado:** `SET ROLE` sobre un usuario con más permisos.
**Motivo:** la defensa en profundidad no debe depender de que el código recuerde cambiar de rol.
**Traza:** Art. 3, R-3.5.

### D15 — Límites del agente: `max_steps = 6`, 1 llamada al modelo por consulta, timeout de API 30 s, temperatura 0
**Motivo:** temperatura 0 es condición de reproducibilidad del golden set; los límites hacen el costo
acotable y comparable entre ejecuciones.
**Traza:** Art. 7, R-6.2.

### D16 — Validación del golden set: aserción sobre clasificación, SQL y filas
La prosa se valida con rúbrica manual de 3 criterios.
**Motivo:** no se puede afirmar igualdad sobre texto generado por un modelo.
**Traza:** Art. 6, Art. 7, `05 §1`.

### D17 — Historial de UI solo visual
Se muestra pero no alimenta al agente.
**Motivo:** un historial que alimenta al agente contradice la exclusión de memoria conversacional.
**Traza:** `01 §5.5`, T8.3.

### D18 — Despliegue: Cloud Run + Cloud SQL + Secret Manager
**Descartado:** Compute Engine y GKE.
**Motivo:** Streamlit como contenedor en Cloud Run es lo mínimo que satisface el criterio de promoción;
GKE es desproporcionado para 3 personas.
**Traza:** criterio de promoción 1.

### D19 — PDFs generados por el integrante responsable de RAG y base de datos
**Descartado:** documentación real de la universidad.
**Motivo:** el golden set necesita respuestas esperadas verificables; con documentación ajena la rúbrica
se vuelve discutible.
**Dependencia:** G6–G9 y R1–R3 se congelan como preguntas, no como respuestas, hasta que existan los
PDFs. El contenido debe cubrir plazo de devolución, sinopsis, pasos del sistema y horario.

### D20 — Un artefacto, un solo lugar
Las specs por capacidad viven solo en `openspec/`. `TP/` conserva constitución, especificación funcional,
especificación técnica, validación y CHANGELOG. Drive queda solo con la consigna y un puntero al repo.
**Motivo:** con tres integrantes y asistentes de IA distintos, dos copias del mismo requisito derivan en
ediciones divergentes. Se eliminaron `03-especificaciones-por-capacidad.md` y `04-tareas.md` del Drive.
**Traza:** `TP/README.md`.

---

## 2026-10-13 — Base de datos en Neon y documentos del RAG (change `base-de-datos-neon`)

**Decisión:** traer a este repositorio la justificación del esquema, el seed y los documentos fuente
del RAG, que se habían diseñado en `UCSE-2026-TAIA` (features 01 y 02). Se tramitan como un change
propio, `openspec/changes/base-de-datos-neon/`, con capacidades `esquema-de-base-de-datos` (R-7.x),
`datos-de-prueba` (R-8.x) y `documentos-fuente-rag` (R-9.x). **Motivo:** D64 adoptó el esquema compartido
sin dejar escrito por qué tiene esa forma; el informe necesita sustentar el modelo de datos.

**Corrección:** la nota de origen decía "8 tablas" en `production`; el DDL declara 9 (7 de dominio y 2
documentales). Se consigna 9.

Las decisiones de diseño llevan prefijo `D-DB` para no colisionar con `D1…D74`:

| ID | Decisión | Alternativa descartada y motivo |
|---|---|---|
| D-DB1 | Neon (PostgreSQL + pgvector + bucket privado) es la base compartida; GCP aloja solo agente + UI. Respalda 9.6 y matiza D18 | Cloud SQL: más costo y fricción con pgvector; Neon ya ofrece ramas y almacenamiento de objetos |
| D-DB2 | `GENERATED ALWAYS AS IDENTITY` | `SERIAL`: no estándar, permite ids manuales |
| D-DB3 | Libros y autores por tabla puente `libros_autores` (origen de D64) | `libros.autor_id`: no representa varios autores |
| D-DB4 | `prestamos.estado` solo `activo`/`devuelto`, con CHECK contra `fecha_devolucion_real` | Guardar `vencido`: se desactualiza |
| D-DB5 | Vista `v_prestamos_estado` con `estado_calculado` y `dias_atraso` (refuerza D7) | Que el agente calcule fechas en el SQL |
| D-DB6 | `ejemplares_disponibles` como columna con CHECK `0..totales` | Derivarla de préstamos: complica el text-to-SQL |
| D-DB7 | `ON DELETE RESTRICT` en dominio, `CASCADE` en puente y chunks | `CASCADE` general: borraría historial |
| D-DB8 | `vector(768)` + HNSW coseno (D5, D13) | Más dimensiones: más almacenamiento sin ganancia con ~22 chunks |
| D-DB9 | El rol del SQL tool no ve `documentos*` | Acceso total: no lo necesita |
| D-DB10 | Plazos, límites y multas viven en el reglamento (RAG), no en tablas | Tabla de políticas: la consulta mixta no ejercitaría el RAG |

**Orden seguido:** DDL aprobado antes de crear tablas → validado en rama de Neon (`test-ddl`) → aplicado
a `production` → seed validado en `test-seed` → aplicado → PDFs generados y subidos al bucket `rag`.

---

## Decisiones de base (sin cambio)

| # | Decisión | Estado |
|---|---|---|
| B1 | PostgreSQL + pgvector como BD y vector store | Confirmada |
| B2 | LLM y embeddings: API de Gemini | Confirmada |
| B3 | Framework agéntico: Smolagents | Confirmada |
| B4 | UI: Streamlit | Confirmada |
| B5 | Criterios de promoción elegidos: nube, UI, framework agéntico, SDD (4 de 5) | Confirmada |
| B6 | LangSmith / observabilidad: **no incluido** | Confirmada (exclusión explícita) |
| B7 | Persistencia de trazabilidad en `agent_runs` | Confirmada (Art. 5) |

---

## Pendientes de calibración (se cierran con evidencia, no con discusión)

| Qué | Valor inicial | Cierre |
|---|---|---|
| Umbral de similitud definitivo | 0.35 | **Cerrada (D75): 0.67**, con 16 consultas sobre los PDFs reales |
| Cantidad real de chunks por documento | — | T3.2, con el chunking ejecutado |
| Fuente de los PDFs | generados por el integrante de RAG/BD | **Cerrada (D19)**; queda pendiente el contenido concreto |
| Mecanismo exacto de despliegue en Cloud Run | — | T10, primera prueba de `docker run` local |

---

## Decisiones tomadas durante la implementación

| ID | Fecha | Tarea | Decisión | Motivo |
|---|---|---|---|---|
| D21 | 2026-10-10 | T4.1 | La whitelist excluye explícitamente `agent_runs` y `documentos_embeddings` | La herramienta SQL lee el dominio, no la trazabilidad ni el repositorio documental. Si el agente pudiera leer `agent_runs`, un usuario podría reconstruir la historia completa de consultas |
| D22 | 2026-10-10 | T4.1 | *(La vista se llama `v_prestamos_estado`: D64.)* `prestamos_estado` entra en la whitelist como vista | Es la única forma de que el agente consulte el vencimiento sin un valor almacenado (D7, R-3.12) |
| D23 | 2026-10-10 | T4.2 | *(Reemplazada por D38.)* Los alias de CTE y de tabla se resuelven con un mapa alias→tabla antes de aplicar la whitelist; una columna proyectada por una CTE no se valida contra el esquema físico | `sqlglot` trata `FROM top` (una CTE) como tabla física: sin el mapa, `WITH top AS (...) SELECT * FROM top` se rechaza falsamente. Lo mismo con `socios s` |
| D24 | 2026-10-10 | T4.2 | El límite de 50 filas lo aplica la ejecución, no la validación estática | S10 es un `SELECT` válido; confundir los dos niveles haría que el test de sanitización afirme algo que la herramienta no hace |
| D25 | 2026-10-10 | T4.2 | `SELECT *` se expande a las columnas de la whitelist antes de ejecutar | La whitelist de columnas era evadible: `SELECT * FROM socios` devolvía cualquier columna física del esquema. Expandir la hace inalcanzable para el agente. No es un control de privacidad (Art. 11, D32), es lo que vuelve verificable R-3.14 |
| D26 | 2026-10-10 | T4.2 | Allowlist de funciones con código `FUNCTION_NOT_ALLOWED` | `pg_sleep`, `pg_read_file`, `dblink` y `pg_advisory_lock` pasaban la validación. El timeout limita el tiempo, no los efectos (R-3.13) |
| D27 | 2026-10-10 | T4.2 | Se rechaza `FOR UPDATE` con `SQL_NOT_READONLY` | Un lock de fila no es lectura, aunque la sentencia empiece con `SELECT` (R-3.2) |
| D28 | 2026-10-10 | T4.2 | Identificadores normalizados a minúsculas antes de comparar | `FROM "Libros"` se rechazaba falsamente; Postgres resuelve la tabla como `libros` (R-3.15) |
| D29 | 2026-10-10 | T4.2 | `error_level=RAISE` en el parseo | Por defecto `sqlglot` avisa y degrada a `Command`; una sentencia mal formada se reinterpretaba en vez de fallar (R-3.3) |
| D30 | 2026-10-10 | T4.2 | Se registra la sentencia **normalizada** como la ejecutada y `SqlResult.sql_original` conserva la del modelo | Con la expansión de `*` la sentencia que corre ya no es idéntica a la que produjo el modelo; sin las dos versiones la evidencia del informe no es verificable (R-3.9, R-6.4) |
| D31 | 2026-10-10 | T4.2 | Los literales de texto no se modifican por la normalización | La respuesta final debe citar los valores efectivamente devueltos (Art. 4); normalizar identificadores no puede cambiar un valor |
| D32 | 2026-10-10 | — | No hay política de PII ni roles de acceso diferenciados: todos los usuarios acceden a toda la información del dominio | La consigna 2026 no lo detalla. La whitelist de tablas y columnas es control de alcance y de inyección (R-3.4), no de privacidad. Si la consigna introdujera un requisito de privacidad, es un cambio de spec (Art. 10) |
| D33 | 2026-10-10 | T4.3 | El fallo de ejecución se reporta con el código `EXECUTION_ERROR` (R-3.16) | Los códigos existentes cubren la validación estática; un fallo al ejecutar (conexión, restricción, sintaxis) no tiene código y sin él la herramienta termina interpretando el mensaje de la base |
| D34 | 2026-10-10 | T4.3 | `pytest` por defecto excluye `integration` y `llm` (`addopts = -m "not integration and not llm"`) | Art. 6 exige que los tests corran sin base ni credenciales. Con la conexión inyectable, la política de clamp/regeneración se prueba offline con un fake; lo que sí necesita base queda en `-m integration` |
| D35 | 2026-10-10 | T4.3 | `psycopg2` se importa de forma diferida dentro de `_connect()` | Si el import estuviera al nivel de módulo, los tests offline no podrían importar el executor sin el paquete instalado |
| D36 | 2026-10-10 | T6.3 | *(Reemplazada por D71.)* El modelo por defecto pasa a `gemini-3-flash-preview` | `gemini-2.5-flash` devuelve 404 para cuentas nuevas (verificado con la API real en `pytest -m llm`). El modelo se lee de `GEMINI_MODEL`, así que el cambio es de configuración, no de código |
| D37 | 2026-10-10 | T6.3 | El cliente de `google-genai` se mantiene en una variable, no en una llamada encadenada | `genai.Client(...).models.generate_content(...)` libera el `Client` antes de la llamada y su `__del__` cierra el httpx: `RuntimeError: client has been closed`. Reproducido y verificado |
| D38 | 2026-10-10 | T4.2 | Tablas y columnas se resuelven **por scope** (`sqlglot.optimizer.scope.traverse_scope` + `qualify_columns` con la whitelist como schema). Reemplaza el mapa global alias→tabla de D23 | Una CTE homónima definida en una subquery ocultaba la tabla prohibida del `FROM` externo (`agent_runs`, `pg_class`); las columnas sin calificar en un JOIN no se validaban; `*` sobre CTE/subquery producía SQL inválido o `KeyError`. Reproducido en la auditoría (R-3.4, R-3.14) |
| D39 | 2026-10-10 | T4.2 | Los nodos de escritura se rechazan **en cualquier posición del árbol** (`INSERT`, `UPDATE`, `DELETE`, `INTO`, `COPY`, `SET`, …), no solo en la raíz | `WITH d AS (DELETE … RETURNING id) SELECT id FROM d` tiene raíz `SELECT` y pasaba el validador. Lo cubría solo el rol `agent_ro`, que todavía no existe (Art. 3, R-3.2) |
| D40 | 2026-10-10 | T4.2 | Una tabla con schema distinto de `public` se rechaza con `TABLE_NOT_ALLOWED` | `otro_schema.libros` pasaba la whitelist por nombre y se ejecutaba con el schema, evadiendo el `search_path` de D14 (R-3.4) |
| D41 | 2026-10-10 | T4.2 | La allowlist de funciones se valida contra el nombre **emitido por el dialecto postgres**; `CASE`, `EXISTS`, `IF`, `AND` y `OR` no son funciones; `Anonymous` se lee de `this`; los niladicos (`CURRENT_USER`) pasan por la allowlist. Corrige la convención de D26 | `sql_name()` devolvía nombres internos de sqlglot: 11 de 58 expresiones comunes se rechazaban (`CASE`, `EXISTS`, `string_agg`, `to_char`, …). Una versión intermedia del fix rechazó todo `AND` porque `And` es `Func` en sqlglot (R-3.13) |
| D42 | 2026-10-10 | T4.2 | `SELECT now()` y `SELECT CURRENT_DATE` sin `FROM` se aceptan | No leen ningún dato; "¿qué fecha es hoy?" es una consulta legítima (R-3.4) |
| D43 | 2026-10-10 | T4.2 | Un único `;` final se tolera; más de una sentencia se rechaza | Los modelos emiten `;` al final con frecuencia y gastaban uno de los 2 intentos de D8. No separa sentencias (R-3.3) |
| D44 | 2026-10-10 | T4.2 / T4.3 | Las columnas de salida repetidas se renombran `<tabla>_<columna>`; las que queden repetidas el executor las desambigua con `_2`; las agregaciones sin alias recuperan su nombre natural (`count`, `max`) | `dict(zip(columns, row))` pisaba en silencio el segundo `id` de un JOIN, y `qualify_columns` nombra `_col_0` a lo que Postgres llama `count` (Art. 4, R-3.9) |
| D45 | 2026-10-10 | T4.3 | Una conexión por executor, perezosa, de solo lectura (`set_session(readonly=True)`), con `rollback()` tras cada ejecución y `close()`; el executor por defecto es perezoso; `.env` se carga con path explícito | `_connect()` abría una conexión por consulta sin cerrarla, y tras un error la transacción quedaba abortada para la siguiente (R-3.18). `find_dotenv()` falla desde stdin |
| D46 | 2026-10-10 | T4.3 | `timeout_ms` se aplica con `SET LOCAL statement_timeout`; el timeout se reconoce por SQLSTATE `57014` | El parámetro se aceptaba y se ignoraba. `25000` no es el código de `statement_timeout`; funcionaba solo por el nombre de la clase `QueryCanceled` (R-3.6) |
| D47 | 2026-10-10 | T4.3 | La zona horaria viene de `APP_TIMEZONE` y se fija en la **sesión** SQL; `TZ` deja de leerse | `Config.timezone` no tenía consumidores: `CURRENT_DATE` usaba la zona del servidor (Cloud SQL en UTC) y "vencido" cambiaba a las 21:00 ART. `TZ` es una variable del sistema que Cloud Run fija en UTC (D6, R-3.11) |
| D48 | 2026-10-10 | T4.3 | `SqlResult.truncated`: el executor pide `max_rows + 1` filas y declara el truncado | 50 filas presentadas como el total son una afirmación falsa (Art. 4, R-3.6) |
| D49 | 2026-10-10 | T4.4 | La callable de regeneración recibe el `SqlResult` anterior; `SqlResult.detail` lleva el motivo; el rechazo final conserva `detail` y `sql_original` | Regenerar a ciegas repite el mismo SQL, y el usuario solo veía un código (R-3.10, R-5.7, R-6.4) |
| D50 | 2026-10-10 | T6.3 | Un solo vocabulario de clasificación: `sql`, `rag`, `hybrid`, `none`. `sql+rag` no existe | El smoke test y `probe_llm.py` usaban `sql+rag` como enum del modelo: la clasificación habría salido inválida para `AgentAnswer` (R-2.1) |
| D51 | 2026-10-10 | T4.1 | *(Reemplazada por D64.)* `prestamos.estado` sale de la whitelist; el estado solo se consulta en la vista `prestamos_estado` | La tabla expone un `estado` almacenado que nunca dice `vencido`; el modelo podía leerlo en vez de calcularlo (D7, R-3.12) |
| D52 | 2026-10-10 | T7.1 | `AgentAnswer` agrega `answer_kind` (`no_coverage`) y `trace`; `as_outcome()` expone clasificación/SQL/filas/chunks; cada fuente declarada exige su propia evidencia | La ausencia de información se detectaba con una regex sobre prosa; un híbrido con la evidencia de una sola fuente era válido (D16, R-2.4, Art. 4) |
| D53 | 2026-10-10 | T4.2 | `QUERY_TOO_COMPLEX` para `WITH RECURSIVE` y más de `SQL_MAX_TABLE_REFS` (8) referencias a tablas | El timeout limita el tiempo, no la carga: un producto cartesiano de 5 tablas pasaba (R-3.17) |
| D54 | 2026-10-10 | T1.2 | `requirements.txt` (ejecución) y `requirements-dev.txt` separados, con cotas; `pyproject.toml` con la configuración de `ruff` | `psycopg2-binary>=2.20` no existe (última 2.9.x) y `pip install -r` fallaba; pytest/faker iban a la imagen de producción (Art. 8) |
| D55 | 2026-10-10 | T9.1 | El golden set nombra entidades concretas del seed (`SEED_ENTITIES`), compara documentos por prefijo (`resenas_libro_`) y su check de conteo no depende del alias | `X` literal no tiene respuesta en ninguna base; `resenas.md` no existe (son `resenas_libro_N.pdf`, `TP/02` §4); el alias `count` lo elige el modelo (D16) |
| D56 | 2026-10-10 | T6.2 | El proveedor del LLM es configuración: `LLM_MODEL` (formato LiteLLM) y `LLM_API_BASE`. Por defecto `gemini/<GEMINI_MODEL>`. `build_classifier` usa Gemini nativo (salida estructurada con enum) o `LiteLLMClassifier` para cualquier otro proveedor | Permite validar el flujo contra un servidor local OpenAI-compatible sin gastar cuota (la cuenta gratuita da ~5 req/min). El criterio de aceptación R-2.1 se mide con el modelo definitivo, no con el local |
| D57 | 2026-10-10 | T6.2 | Reintento ante 429 con la espera que informa la API (`Please retry in Ns`), tope 60 s y `AGENT_API_MAX_RETRIES` (3) | `gemini-3-flash-preview` con la clave gratuita permite ~5 req/min y cada consulta usa 3–5 llamadas: sin reintento 12 de 13 casos fallaron en 0,2 s |
| D58 | 2026-10-10 | T6.2 | Las fuentes declaradas son las **efectivamente invocadas** y la evidencia sale de lo que devolvieron las tools, no del texto del modelo. Un fallo de tool o de clasificación se responde con plantilla fija (`answer_kind=error`) | Art. 4 y R-2.7: si el modelo afirma datos sin haber consultado no puede haber respuesta con fuente; R-5.7: el error se informa en vez de responder sin datos |
| D59 | 2026-10-10 | T6.3 | La medición de R-2.1 sin base ni PDFs usa backends falsos y el validador de SQL **real**; mide clasificación, herramientas invocadas, orden y SQL aceptado, no el contenido. La evidencia se versiona en `TP/evidencia/` | El contenido (filas, fragmentos) depende del seed y de los PDFs del otro integrante (D19). Lo que el orquestador controla ya se puede medir y afirmar |
| D60 | 2026-10-10 | T5.1 | *(Reemplazada por D66.)* `rag_tool` lee `documentos_embeddings(id, document, location, text, content_hash, vector)` con `1 - (vector <=> q)`; el embedder usa `RETRIEVAL_QUERY` y normaliza | Es el contrato con la ingesta (D19). La ingesta debe embeber con `RETRIEVAL_DOCUMENT`, 768 dimensiones, y dar `GRANT SELECT` a `agent_ro` |
| D61 | 2026-10-10 | T6.2 | smolagents hace una llamada extra al llegar a `max_steps`: el tope real de llamadas al modelo es `max_steps + 1` | Verificado con un modelo falso que nunca converge (7 llamadas con tope 6) |
| D62 | 2026-10-10 | T6.2 | El clasificador para proveedores no-Gemini usa `max_tokens=4096` y propaga el motivo real del fallo (no solo la clase de la excepción) | La medición con un modelo local que razona dejó G12 en error 3 de 3 veces: con 1024 tokens el servidor devolvió `finish_reason=length` con el JSON incompleto, y el mensaje solo decía `ClassificationError`. El error era técnico y parecía una clasificación inválida (R-2.8) |
| D63 | 2026-10-10 | T7.4 | Dos roles de aplicación: `agent_ro` (solo lectura del dominio y de `documentos_chunks`) y `agent_logger` (solo `INSERT` en `agent_runs`, y `SELECT (id)` para `RETURNING`). `agent_ro` no ve `agent_runs` | `agent_ro` es de solo lectura (R-3.5): no puede escribir la bitácora. Un único rol con escritura rompería Art. 3. Con rol de solo inserción, una credencial filtrada no expone la historia de consultas (D21). Verificado contra Postgres real |
| D64 | 2026-10-10 | T2.1 | Se adopta el **esquema real compartido**: `libros` no tiene `autor_id` (N:M por `libros_autores`); la vista es `v_prestamos_estado` con `estado_calculado` y `dias_atraso`; `prestamos.estado` existe pero solo vale `activo`/`devuelto`. Reemplaza D51 y renombra la vista de D22 | Se asumía `libros.autor_id` y una vista `prestamos_estado.estado = 'vencido'` (TP/02 original). El esquema que compartió el integrante de BD es otro: el SQL que generaba el modelo con el prompt anterior habría fallado en `autor_id` y devuelto 0 filas en "vencidos". La whitelist, el prompt, los ejemplos y los tests se alinearon; el test de coincidencia con `schema.sql` ahora es bidireccional y corre |
| D65 | 2026-10-10 | T1.3, T2.1 | `db/schema.sql` es el DDL exportado de Neon **normalizado**; la base local corre en Docker (`docker compose up -d --wait`) con roles, `agent_runs`, permisos y `db/dev_seed.sql`; `scripts/replicate_neon.sh` trae datos reales con `pg_dump` desde un contenedor | El DDL exportado no corría en PostgreSQL: `CREATE VIEW … TABLESPACE`, `CREATE UNIQUE INDEX` duplicando el de cada PK/UNIQUE, `CREATE SCHEMA public`, falta `CREATE EXTENSION vector`. El HNSW no declaraba operador (por defecto L2) y el agente consulta por coseno (D13): se declaró `vector_cosine_ops`. Cada cambio queda anotado en la cabecera de `schema.sql` para llevarlo al esquema compartido |
| D66 | 2026-10-10 | T5.1 | La herramienta de RAG lee `documentos_chunks` + `documentos`. `location` = `metadata.seccion` / `ubicacion` / `pagina` o "fragmento N"; `content_hash` = `sha256 + ":" + chunk_index`. Reemplaza D60 | D60 asumía una tabla `documentos_embeddings(document, location, text, content_hash, vector)` que no existe. El esquema real no tiene columna de ubicación: la cita "Art. 12" (R-4.7) depende de que la ingesta la guarde en `metadata` |
| D67 | 2026-10-10 | T7.4 | `agent_runs` se arma solo desde el `AgentAnswer` (una sola fuente de verdad). Si el registro falla, la consulta se contesta igual y el fallo queda en `evidence.run_recording_error`. La consulta vacía no se registra (R-1.2). Con la base caída no se reintenta durante 30 s | Una respuesta correcta no se pierde por un problema de bitácora, pero tampoco se finge que se registró (Art. 4). Sin el enfriamiento cada consulta pagaría el timeout de conexión (R-6.2, R-6.3) |
| D68 | 2026-10-10 | T1.3 | `POSTGRES_HOST` por defecto `127.0.0.1` | En Windows `localhost` intenta primero IPv6 y cada conexión costaba ~2 s (medido: 2,03 s contra 0,03 s). La suite de integración pasó de 98 s a 2,4 s |
| D69 | 2026-10-11 | T6.7 | Corpus simulado de RAG (`tests/rag_fixture.py`): un `RagRetriever` real sobre un embedder léxico y 7 fragmentos de prueba; `measure_golden.py --rag-mock` lo usa y evalúa el `check` de contenido solo donde las fuentes no son falsas (`content_evaluable`). Su umbral (0,15) es propio y **no** calibra D12 | Sin PDFs ni ingesta (D19) el contenido de los casos RAG e híbridos no se podía evaluar y la aceptación (R-2.1) se medía con un único fragmento fijo. El mock permite medir al agente (decisión, tool, cita, composición) con el modelo definitivo sin esperar a otro integrante; no mide retrieval semántico ni sustituye 3.6–3.8 (R-2.8, D59) |
| D70 | 2026-10-11 | T6.7 | `GeminiClassifier` conserva el motivo del fallo de la API (clase + primeros 200 caracteres del mensaje), igual que el clasificador de LiteLLM (D62) | Una corrida con `gemini-3-flash-preview` dio 3/13 con `classifier_errors=10` y el mensaje decía solo `ClientError`: el motivo real (cuota gratuita de 20 requests por día y por modelo agotada, HTTP 429) solo apareció haciendo una llamada aparte. Con el motivo a la vista la corrida se descarta como no evaluable en vez de leerse como falla del modelo (R-5.7, Art. 4) |
| D71 | 2026-10-11 | T6.7 | El modelo definitivo y por defecto pasa a `gemini-3.1-flash-lite` (`GEMINI_MODEL`). Reemplaza D36 | `gemini-3-flash-preview` tiene 20 requests por día en la clave gratuita y una corrida del golden set usa ~50 (D70): no puede completar la medición de aceptación. `gemini-3.1-flash-lite` midió 13/13 clasificados, 3/3 híbridos y 1/1 `none` en dos corridas (`TP/evidencia/`), con base local y RAG simulado en la última. Si el equipo despliega otro modelo, la medición se repite completa (`TP/05` §4.1, regla 5) |
| D72 | 2026-10-11 | T9.1 | El `check` de los híbridos (`_both_sources`) exige una sentencia SQL ejecutada y un fragmento citado, **no** filas no vacías. Un resultado vacío es válido | G11 daba contenido fallido con la respuesta correcta: el agente resolvió el socio con más préstamos y después verificó si tenía vencidos (0 filas) y `as_outcome()` toma las filas de la última sentencia. Exigir filas contradecía R-3.8 (sin resultados es una respuesta válida). Se cambió el criterio, no el agente, con test; se regeneró la corrida y el 12/13 original queda en el historial de git (D16) |
| D73 | 2026-10-11 | T7.6 | El idioma de la respuesta se **instruye** en el prompt con la clasificación (`LANGUAGE_RULES`: "Answer in English" / "Respondé en castellano"), se consigna en `evidence["language"]` y se verifica en el golden set con casos aparte (`B1`, `B2`, fuera de los 13 de R-2.1) y una heurística de palabras funcionales sobre la prosa | La corrida con casos en inglés dio idioma declarado `en` 2/2 pero **contenido 0/2**: el modelo respondía en castellano y solo la etiqueta fija salía "Source:". El prompt, las herramientas y los documentos están en castellano y la regla genérica "en el idioma de la consulta" no alcanzaba. La heurística es una excepción acotada a D16 (prosa solo con rúbrica): el idioma sí es verificable; la calidad de la prosa sigue siendo manual (R-5.1) |
| D74 | 2026-10-11 | T9.2 | Un solo Dockerfile con tres etapas: `base` (Python 3.12 + `requirements.txt` + `agent/`, usuario no root), `measure` (+ `scripts/` y `tests/`) y `runtime` (destino por defecto, sin tests). Secretos solo por entorno; `.env` fuera del contexto | `measure_golden.py` importa los dobles y el golden set de `tests/`: sin una etapa aparte habría que llevar los tests a la imagen que se despliega o no poder medir dentro del contenedor. Los tests estáticos (`tests/test_dockerfile.py`) atrapan rutas inexistentes, secretos y root sin necesitar el daemon, y el build real se verificó con Docker: las dos etapas construyen, `runtime` corre como uid 10001 sin `tests/` ni `.env`, y `measure` ejecutó G1, G6 y G13 contra la base del host y la API (3/3) (Art. 8, Art. 9) |
| D75 | 2026-10-15 | T3.6 | Umbral de similitud = **0.67** (antes 0.35). Calibrado con 16 consultas sobre los 36 fragmentos reales: positivos entre 0.686 y 0.802, negativos del dominio entre 0.597 y 0.649; el punto medio es 0.667. Evidencia: `TP/evidencia/calibracion_umbral.json`. Reemplaza el valor inicial de D12 | Con 0.35 pasaba cualquier consulta: hasta una pregunta del dominio sin cobertura ("¿hay wifi?") puntúa 0.65. **Margen angosto (~0.02 a cada lado):** el peor positivo es una pregunta en inglés (B2, 0.686) y el mejor negativo "wifi" (0.649). El umbral solo es un filtro grueso: la segunda barrera es el clasificador y que el modelo, con los fragmentos a la vista, declare que no hay información (R-4.6). Conviene recalibrar si cambian los documentos, el chunking o el modelo de embeddings |
| D76 | 2026-10-15 | T3.1 | Se **elimina el manual de uso del sistema** del corpus del RAG: quedan 5 documentos (reglamento, políticas y 3 reseñas) y 28 fragmentos. G8, R3 y el caso de calibración R11 pasan a verificar el `reglamento_biblioteca` (renovaciones y límites, Art. 3 y 4); el corpus simulado de los tests pierde sus 2 fragmentos del manual (5 en total). Se quitan las menciones al manual en los prompts y en los documentos del TP. Con el corpus nuevo la calibración da el mismo veredicto (positivos desde 0.686, negativos hasta 0.649, punto medio 0.667): el umbral 0.67 de D75 se mantiene | El equipo decidió que no hacía falta. Qué cambia: ya no hay cobertura para "cómo se hace X en la plataforma"; esas consultas dan "sin información" (R-4.6) salvo que el reglamento las responda. La evidencia histórica de `TP/evidencia/` conserva las corridas anteriores con el manual (D16). Las corridas de aceptación con prompts distintos deben repetirse completas antes de la entrega (`TP/05` §4.1, regla 5) |
| D77 | 2026-10-15 | T2.4 | **Ampliación del catálogo y de las reseñas.** `db/seed.sql` (único seed, sin archivo aparte) suma 51 libros: 10 cómics de DC, 10 de Marvel, la saga Empyrean, Tolkien (Silmarillion, Hobbit, 3 tomos), Narnia (7), Harry Potter (7), Berserk Deluxe (5) y Dragon Ball (4), con ISBN verificados en Open Library. En el RAG sale la reseña de IA y entran `resenas_tolkien` y `resenas_empyrean` (6 PDFs en total), con una sección de sinopsis y otra de valoración por libro. `rag/ingest.py` agrega poda: lo que ya no está en `rag/documents/` se borra de la base. Corpus: 6 documentos, 44 fragmentos | Las reseñas se limitan a 2 sagas para respetar el tope de 6 PDFs. **La calibración dejó de separar:** el peor positivo (R15, una pregunta sobre un personaje, 0.646) quedó 0.003 por debajo del mejor negativo (el wifi, 0.649). Partir las reseñas en sinopsis y valoración no lo resolvió. El umbral de D75 (0.67) se mantiene hasta decidir si se prioriza no rechazar preguntas válidas (bajarlo a ~0.64) o no dejar pasar negativos difíciles. Además, "¿cuántos cómics de Marvel hay?" respondió 2 y son 10: el agente filtró por texto y no por editorial |
| D78 | 2026-10-15 | T3.6, T6.1 | **Umbral provisorio 0.64 y editoriales en el prompt.** El umbral baja de 0.67 a 0.64 (D77 lo dejó sin separación: R15 0.646 vs wifi 0.649); se prioriza no rechazar preguntas válidas y queda sujeto a recalibración. El esquema describe `editoriales` con ejemplos (Marvel, Planeta, DC) y el prompt suma una regla y el ejemplo 9: «libros de Marvel» se resuelve con JOIN a `editoriales`, no con `ILIKE` sobre título/categoría | Antes «¿cuántos cómics de Marvel hay?» respondía 2 (real: 10); ahora 10. La imagen Docker de `agent` debe reconstruirse (`build ingest agent`) para ver los cambios de prompt. Falta repetir la medición de aceptación completa |
| D79 | 2026-10-15 | T2.4, T6.1 | **Un solo seed y prompt de editoriales genérico.** La ampliación se integra en `db/seed.sql` y se elimina `db/seed_ampliacion.sql`; sobre una base vacía deja 70 libros, 57 autores, 28 editoriales, 18 categorías y 95 vínculos, idénticos a Neon. El prompt y la nota de `editoriales` ya no nombran Marvel/Planeta/DC: regla general (filtrar editorial, autor y categoría con JOIN, `ILIKE '%X%'`) y un ejemplo neutro | `seed.sql` no es idempotente: Neon y la base local ya tienen los datos, solo sirve para bases nuevas. Con solo la regla de JOIN, «cómics de Marvel» seguía respondiendo 2; lo resolvió decir que un nombre propio es editorial o autor (no se busca en título ni en la descripción de la categoría) y que un tipo de libro suma el filtro de categoría. Ahora responde 10 en tres corridas |
| — | T3 | — | — | — |
| — | T5 | — | — | — |
