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

### D12 — top-k = 5, umbral de similitud = 0.35, calibrado contra los PDFs reales
El valor definitivo se registra aquí cuando se complete la calibración (T3.6).
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
| Umbral de similitud definitivo | 0.35 | T3.6, con la curva de similitud sobre los PDFs reales |
| Cantidad real de chunks por documento | — | T3.2, con el chunking ejecutado |
| Fuente de los PDFs | generados por el integrante de RAG/BD | **Cerrada (D19)**; queda pendiente el contenido concreto |
| Mecanismo exacto de despliegue en Cloud Run | — | T10, primera prueba de `docker run` local |

---

## Decisiones tomadas durante la implementación

| ID | Fecha | Tarea | Decisión | Motivo |
|---|---|---|---|---|
| D21 | 2026-10-10 | T4.1 | La whitelist excluye explícitamente `agent_runs` y `documentos_embeddings` | La herramienta SQL lee el dominio, no la trazabilidad ni el repositorio documental. Si el agente pudiera leer `agent_runs`, un usuario podría reconstruir la historia completa de consultas |
| D22 | 2026-10-10 | T4.1 | `prestamos_estado` entra en la whitelist como vista | Es la única forma de que el agente consulte el vencimiento sin un valor almacenado (D7, R-3.12) |
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
| D36 | 2026-10-10 | T6.3 | El modelo por defecto pasa a `gemini-3-flash-preview` | `gemini-2.5-flash` devuelve 404 para cuentas nuevas (verificado con la API real en `pytest -m llm`). El modelo se lee de `GEMINI_MODEL`, así que el cambio es de configuración, no de código |
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
| D51 | 2026-10-10 | T4.1 | `prestamos.estado` sale de la whitelist; el estado solo se consulta en la vista `prestamos_estado` | La tabla expone un `estado` almacenado que nunca dice `vencido`; el modelo podía leerlo en vez de calcularlo (D7, R-3.12) |
| D52 | 2026-10-10 | T7.1 | `AgentAnswer` agrega `answer_kind` (`no_coverage`) y `trace`; `as_outcome()` expone clasificación/SQL/filas/chunks; cada fuente declarada exige su propia evidencia | La ausencia de información se detectaba con una regex sobre prosa; un híbrido con la evidencia de una sola fuente era válido (D16, R-2.4, Art. 4) |
| D53 | 2026-10-10 | T4.2 | `QUERY_TOO_COMPLEX` para `WITH RECURSIVE` y más de `SQL_MAX_TABLE_REFS` (8) referencias a tablas | El timeout limita el tiempo, no la carga: un producto cartesiano de 5 tablas pasaba (R-3.17) |
| D54 | 2026-10-10 | T1.2 | `requirements.txt` (ejecución) y `requirements-dev.txt` separados, con cotas; `pyproject.toml` con la configuración de `ruff` | `psycopg2-binary>=2.20` no existe (última 2.9.x) y `pip install -r` fallaba; pytest/faker iban a la imagen de producción (Art. 8) |
| D55 | 2026-10-10 | T9.1 | El golden set nombra entidades concretas del seed (`SEED_ENTITIES`), compara documentos por prefijo (`resenas_libro_`) y su check de conteo no depende del alias | `X` literal no tiene respuesta en ninguna base; `resenas.md` no existe (son `resenas_libro_N.pdf`, `TP/02` §4); el alias `count` lo elige el modelo (D16) |
| D56 | 2026-10-10 | T6.2 | El proveedor del LLM es configuración: `LLM_MODEL` (formato LiteLLM) y `LLM_API_BASE`. Por defecto `gemini/<GEMINI_MODEL>`. `build_classifier` usa Gemini nativo (salida estructurada con enum) o `LiteLLMClassifier` para cualquier otro proveedor | Permite validar el flujo contra un servidor local OpenAI-compatible sin gastar cuota (la cuenta gratuita da ~5 req/min). El criterio de aceptación R-2.1 se mide con el modelo definitivo, no con el local |
| D57 | 2026-10-10 | T6.2 | Reintento ante 429 con la espera que informa la API (`Please retry in Ns`), tope 60 s y `AGENT_API_MAX_RETRIES` (3) | `gemini-3-flash-preview` con la clave gratuita permite ~5 req/min y cada consulta usa 3–5 llamadas: sin reintento 12 de 13 casos fallaron en 0,2 s |
| D58 | 2026-10-10 | T6.2 | Las fuentes declaradas son las **efectivamente invocadas** y la evidencia sale de lo que devolvieron las tools, no del texto del modelo. Un fallo de tool o de clasificación se responde con plantilla fija (`answer_kind=error`) | Art. 4 y R-2.7: si el modelo afirma datos sin haber consultado no puede haber respuesta con fuente; R-5.7: el error se informa en vez de responder sin datos |
| D59 | 2026-10-10 | T6.3 | La medición de R-2.1 sin base ni PDFs usa backends falsos y el validador de SQL **real**; mide clasificación, herramientas invocadas, orden y SQL aceptado, no el contenido. La evidencia se versiona en `TP/evidencia/` | El contenido (filas, fragmentos) depende del seed y de los PDFs del otro integrante (D19). Lo que el orquestador controla ya se puede medir y afirmar |
| D60 | 2026-10-10 | T5.1 | `rag_tool` lee `documentos_embeddings(id, document, location, text, content_hash, vector)` con `1 - (vector <=> q)`; el embedder usa `RETRIEVAL_QUERY` y normaliza | Es el contrato con la ingesta (D19). La ingesta debe embeber con `RETRIEVAL_DOCUMENT`, 768 dimensiones, y dar `GRANT SELECT` a `agent_ro` |
| D61 | 2026-10-10 | T6.2 | smolagents hace una llamada extra al llegar a `max_steps`: el tope real de llamadas al modelo es `max_steps + 1` | Verificado con un modelo falso que nunca converge (7 llamadas con tope 6) |
| D62 | 2026-10-10 | T6.2 | El clasificador para proveedores no-Gemini usa `max_tokens=4096` y propaga el motivo real del fallo (no solo la clase de la excepción) | La medición con un modelo local que razona dejó G12 en error 3 de 3 veces: con 1024 tokens el servidor devolvió `finish_reason=length` con el JSON incompleto, y el mensaje solo decía `ClassificationError`. El error era técnico y parecía una clasificación inválida (R-2.8) |
| — | T3 | — | — | — |
| — | T5 | — | — | — |
