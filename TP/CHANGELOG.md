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
| D23 | 2026-10-10 | T4.2 | Los alias de CTE y de tabla se resuelven con un mapa alias→tabla antes de aplicar la whitelist; una columna proyectada por una CTE no se valida contra el esquema físico | `sqlglot` trata `FROM top` (una CTE) como tabla física: sin el mapa, `WITH top AS (...) SELECT * FROM top` se rechaza falsamente. Lo mismo con `socios s` |
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
| — | T3 | — | — | — |
| — | T5 | — | — | — |
| — | T3 | — | — |
| — | T5 | — | — |
