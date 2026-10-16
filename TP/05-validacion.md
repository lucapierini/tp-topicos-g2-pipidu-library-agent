# Validación — Golden set y pruebas

> Última etapa del ciclo SDD: `Requirement → Spec → Plan → Tasks → Implementation → Validation`.
> Esta es la sección que sustenta las "evidencias de funcionamiento" del informe técnico.

---

## 1. Golden set — casos con respuesta esperada

La semilla es fija y versionada: `db/seed.sql` es el entregable (catálogo real de 70 libros, socios y
préstamos sintéticos) y `db/dev_seed.sql` es la base de desarrollo, que contiene las entidades que nombran
los casos (`tests/golden_set.py::SEED_ENTITIES`). Las fechas de préstamo son relativas a `CURRENT_DATE`, así
que los atrasos envejecen: las afirmaciones deterministas son sobre entidades, filas y clasificación, no
sobre días literales. La semilla generada con `--seed 42` (`db/seed_data.py`, T2.4) no está implementada.

### Método de afirmación (D16)

Los casos se afirman sobre **clasificación, SQL y filas devueltas**, no sobre la prosa generada, porque
el texto del modelo no es determinista. La prosa se valida con una rúbrica manual de 3 criterios:

1. La fuente declarada coincide con la herramienta efectivamente invocada.
2. Los valores citados coinciden con la evidencia.
3. El idioma y el formato cumplen R-5.5 y R-5.6.

La afirmación automática de cada caso queda en `tests/golden_set.py` (`GOLDEN_SET`, `BILINGUAL_SET`), ejecutada
por `tests/test_golden_set.py`. El resultado de la rúbrica manual no se registra en el repositorio: se consigna
en el informe (pendiente).

### Casos SQL (≥5, criterio de aprobación 2)

| # | Pregunta esperada | Fuente esperada | Resultado esperado |
|---|---|---|---|
| G1 | ¿Qué libros tiene prestados el socio Juan Pérez? | SQL | Lista de títulos con fecha de préstamo |
| G2 | ¿Cuáles son los 5 libros más prestados este cuatrimestre? | SQL | Ranking de 5 títulos con conteo |
| G3 | ¿Qué socios tienen préstamos vencidos? | SQL | Lista de socios con días de atraso |
| G4 | ¿Cuántos libros de la categoría "Ciencias de la Computación" hay disponibles? | SQL | Conteo de ejemplares disponibles |
| G5 | ¿Qué autor tiene más libros publicados por la editorial Sudamericana? | SQL | Autor + cantidad |

### Casos RAG (≥4, criterio de aprobación 3)

| # | Pregunta | Fuente esperada | Resultado esperado |
|---|---|---|---|
| G6 | ¿Cuántos días tengo para devolver un libro antes de que me multen? | RAG | Plazo exacto citado del reglamento |
| G7 | ¿De qué trata el libro "Cien años de soledad"? | RAG | Sinopsis citada de la reseña |
| G8 | ¿Cómo renuevo un préstamo desde el sistema? | RAG | Renovación citada (Art. 4 del reglamento) |
| G9 | ¿Cuál es el horario de la biblioteca? | RAG | Horario citado del reglamento |

### Casos híbridos (≥3, requisito R-2.4)

| # | Pregunta | Fuente esperada | Resultado esperado |
|---|---|---|---|
| G10 | Juan Pérez tiene un libro prestado hace 20 días, ¿le corresponde multa según el reglamento? | SQL + RAG | Fecha del préstamo + regla de sanción + conclusión |
| G11 | ¿El socio con más préstamos puede renovar según el reglamento? | SQL + RAG | Socio top + límite del reglamento |
| G12 | ¿Un docente tiene un plazo distinto que un alumno para el libro más prestado? | SQL + RAG | Tipo de socio + norma aplicable |

### Caso de no-cobertura (R-2.5)

| # | Pregunta | Fuente esperada | Resultado esperado |
|---|---|---|---|
| G13 | ¿Cuál es el precio del libro "Rayuela"? | ninguna | Declaración de "no dispone de información suficiente" |

### Casos en inglés (R-5.1, T7.6, D73)

Van aparte para no cambiar el denominador del criterio ≥ 11/13 (`BILINGUAL_SET`).

| # | Pregunta | Fuente esperada | Resultado esperado |
|---|---|---|---|
| B1 | Which books does Juan Pérez currently have on loan? | SQL | Equivalente de G1, respondido en inglés |
| B2 | How many days do I have to return a book before I get fined? | RAG | Equivalente de G6, respondido en inglés |

---

## 2. Pruebas de sanitización de SQL (R-3.2, R-3.3, R-3.4)

Casos adversos. El criterio de éxito es **rechazo sin ejecución contra la base**.

| # | Sentencia generada | Error esperado |
|---|---|---|
| S1 | `DELETE FROM prestamos WHERE socio_id = 1` | `SQL_NOT_READONLY` |
| S2 | `SELECT 1; DROP TABLE libros` | `SQL_NOT_READONLY` |
| S3 | `SELECT * FROM pg_catalog.pg_tables` | `TABLE_NOT_ALLOWED` |
| S4 | `SELECT * FROM libros -- comentario` | `SQL_NOT_READONLY` |
| S5 | `WITH x AS (SELECT 1) INSERT INTO autores VALUES (...)` | `SQL_NOT_READONLY` |
| S6 | `COPY libros TO '/etc/passwd'` | `SQL_NOT_READONLY` |
| S7 | `SELECT * FROM libros WHERE id = 1 /* bloque */ ; CREATE TABLE t (a int)` | `SQL_NOT_READONLY` |
| S8 | `SELECT * FROM usuarios_vistos` (tabla inexistente) | `TABLE_NOT_ALLOWED` |
| S9 | `CALL some_procedure()` | `SQL_NOT_READONLY` |
| S10 | `SELECT * FROM libros LIMIT 100000` | límite aplicado (≤50 filas) — se verifica en la ejecución (T4.3), no en la validación estática |
| S13 | `SELECT * FROM agent_runs` | `TABLE_NOT_ALLOWED` |
| S14 | `SELECT * FROM documentos_embeddings` | `TABLE_NOT_ALLOWED` |
| S15 | `SELECT secreto FROM socios` (columna fuera de la whitelist) | `COLUMN_NOT_ALLOWED` |
| S16 | `SELECT id, pg_sleep(10) FROM libros` | `FUNCTION_NOT_ALLOWED` |
| S17 | `SELECT pg_read_file('/etc/passwd') FROM libros` | `FUNCTION_NOT_ALLOWED` |
| S18 | `SELECT dblink('dbname=x', 'SELECT 1') AS r FROM libros` | `FUNCTION_NOT_ALLOWED` |
| S16b | `SELECT pg_advisory_lock(1) FROM libros` | `FUNCTION_NOT_ALLOWED` |
| S19 | `SELECT id FROM libros FOR UPDATE` | `SQL_NOT_READONLY` |
| S20 | `SELECT FROM WHERE` (mal formada) | `SQL_NOT_READONLY` por parse estricto |
| S21 | `SELECT * FROM socios` con una columna física fuera de la whitelist | `*` se expande a la whitelist; la columna no documentada no puede alcanzarse (R-3.4) |
| S22 | `SELECT id FROM "Libros"` | aceptado: identificador normalizado a minúsculas (R-3.4) |
| S23 | `SELECT l.id FROM libros l, (WITH agent_runs AS (SELECT id FROM libros) SELECT id FROM agent_runs) t, agent_runs` | `TABLE_NOT_ALLOWED`: la CTE homónima no oculta la tabla (D38) |
| S24 | `WITH d AS (DELETE FROM prestamos WHERE id > 0 RETURNING id) SELECT id FROM d` | `SQL_NOT_READONLY`: escritura dentro de una CTE (D39) |
| S25 | `SELECT secreto FROM socios s JOIN prestamos p ON p.socio_id = s.id` | `COLUMN_NOT_ALLOWED`: columna sin calificar en un JOIN (D38) |
| S26 | `SELECT id FROM otro_schema.libros` | `TABLE_NOT_ALLOWED` (D40) |
| S27 | `SELECT * FROM libros, generate_series(1, 10)` | `FUNCTION_NOT_ALLOWED`: función de tabla (R-3.13) |
| S28 | `SELECT "pg_sleep"(1) FROM libros` | `FUNCTION_NOT_ALLOWED`: el nombre entre comillas no la oculta (D41) |
| S29 | `WITH RECURSIVE r AS (...) SELECT n FROM r` | `QUERY_TOO_COMPLEX` (R-3.17) |
| S30 | `SELECT estado_calculado FROM prestamos` | `COLUMN_NOT_ALLOWED`: el estado calculado solo existe en la vista (D64) |
| S31 | `SELECT 'abc FROM libros` y `""` | `SQL_NOT_READONLY`, sin lanzar excepción (R-3.3) |
| S32 | `CASE`, `EXISTS`, `AND`/`OR`, `string_agg`, `to_char`, `SELECT t.* FROM (…) t` | aceptados (D41, D38) |
| S33 | `SELECT * FROM libros l JOIN editoriales e ON e.id = l.editorial_id` | aceptado; salida con `l_id` y `e_id`, sin pérdida de datos (D44) |
| S34 | `SELECT l.autor_id FROM libros l` | `COLUMN_NOT_ALLOWED`: los autores están en `libros_autores` (D64) |
| S35 | `SELECT contenido FROM documentos_chunks` | `TABLE_NOT_ALLOWED`: el repositorio documental no se consulta por SQL (D21) |

Los casos S23–S33 y el alcance de la allowlist (cada función permitida es alcanzable) están en
`tests/test_sql_validator_hardening.py`. Las consultas de referencia G1–G5 y G10–G12 también deben
pasar la validación.

`tests/test_sql_validator_hardening.py` tiene 31 casos adversos (`REJECTED`): 13 tienen ID en la tabla anterior
(B1=S23, B5=S24, B9=S25, B13=S26, B15=S27, B19=S29, B21=S30, B22 y B23=S31, B26=S28, B29=S34, B30=S35) y 18
no están nombrados acá, con el mismo criterio de rechazo: B2, B3, B4 (CTE homónima en `CROSS JOIN`,
`documentos_embeddings`, `pg_class` → `TABLE_NOT_ALLOWED`), B6, B7 (`UPDATE` e `INSERT` dentro de una CTE →
`SQL_NOT_READONLY`), B8 (`SELECT … INTO` → `SQL_NOT_READONLY`), B10, B11, B12 (columna fuera de la whitelist
sin calificar, calificada y dentro de una subquery → `COLUMN_NOT_ALLOWED`), B14 (schema y dos bases →
`TABLE_NOT_ALLOWED`), B16, B17, B18, B27, B28 (función de efecto en `CROSS JOIN`, en `WHERE`, `set_config`,
`current_user` → `FUNCTION_NOT_ALLOWED`), B20 (nueve tablas → `QUERY_TOO_COMPLEX`, R-3.17), B24, B25 (solo
espacios y solo `;` → `SQL_NOT_READONLY`), B31 (`SELECT nombre_archivo FROM documentos` → `TABLE_NOT_ALLOWED`,
D21). El mismo archivo suma 18 consultas que NO deben rechazarse (`ACCEPTED`), 17 entradas hostiles que no
deben lanzar excepción, y un test que verifica que cada función de la allowlist es alcanzable.

### Casos de regeneración (R-3.10, D8)

| # | Situación | Criterio |
|---|---|---|
| S11 | Primer SQL rechazado por whitelist, segundo intento válido | se ejecuta el segundo intento y `attempts = 2` |
| S12 | Dos rechazos consecutivos | no se ejecuta nada y se reporta el error al usuario (R-5.7) |

### Casos de semántica temporal (R-3.11, R-3.12, D6, D7)

| # | Situación | Criterio |
|---|---|---|
| T1 | "¿Préstamos de este cuatrimestre?" | usa el rango configurado 2026-08-01 a 2026-11-30 |
| T2 | "¿Qué socios tienen préstamos vencidos?" | estado calculado por fechas, coincide con G3 |

---

## 3. Pruebas de retrieval (R-4.4, R-4.6)

### Casos de cobertura y no-cobertura (R1–R4, `RETRIEVAL_TESTS`)

| # | Pregunta | Criterio |
|---|---|---|
| R1 | "¿Cuántos días tengo para devolver un libro y cuándo empieza la multa?" | top-1 pertenece a `reglamento_biblioteca.pdf` |
| R2 | "¿De qué trata el libro Cien años de soledad?" | top-1 pertenece a la reseña correspondiente |
| R3 | "¿Cómo renuevo un préstamo?" | top-1 pertenece a `reglamento_biblioteca.pdf` |
| R4 | "¿Cuánto cuesta el libro Cien años de soledad?" | similitud máxima < umbral → reporte de no-relevancia |

El top-1 de R1–R3 con embeddings reales (T3.7) **no está verificado**: la evidencia versionada registra
similitudes, no el documento recuperado.

### Casos extra de la calibración (T3.6, `CALIBRATION_EXTRA`)

`scripts/calibrate_threshold.py` suma 12 preguntas y usa además G6–G9 y B2: 21 casos en total.

| # | Pregunta | Cobertura esperada | Similitud top-1 medida |
|---|---|---|---|
| R5 | ¿Hay wifi en la biblioteca? | ninguna | 0,649 |
| R6 | ¿Puedo tomar café en la sala de lectura? | ninguna | 0,644 |
| R7 | ¿Cómo reservo una sala de estudio? | ninguna | 0,597 |
| R8 | ¿Puedo imprimir o fotocopiar? | ninguna | 0,602 |
| R9 | ¿Cuánto es la multa por día de atraso? | RAG | 0,771 |
| R10 | ¿Hasta qué hora está abierta la biblioteca? | RAG | 0,735 |
| R11 | ¿Cuántos libros puedo llevar al mismo tiempo? | RAG | 0,765 |
| R12 | ¿De qué trata El Hobbit? | RAG | 0,732 |
| R13 | ¿En qué orden conviene leer a Tolkien? | RAG | 0,737 |
| R14 | ¿De qué trata Alas de hierro? | RAG | 0,706 |
| R15 | ¿Quién es Violet Sorrengail? | RAG | 0,646 |
| R16 | ¿Quién escribe la Canción de hielo y fuego? | ninguna | 0,627 |
| G6–G9 | plazos, reseña de Cien años de soledad, renovación, horario | RAG | 0,755 / 0,762 / 0,703 / 0,758 |
| B2 | días antes de la multa (inglés) | RAG | 0,686 |

El valor vigente es top-k = 5 (`RAG_TOP_K`) y umbral de similitud de coseno = **0,64**
(`RAG_SIMILARITY_THRESHOLD`, default en `agent/config/__init__.py` y `.env.example`). Historia del número:
0,35 fue hipótesis (D12); la primera corrida con los PDFs reales lo fijó en 0,67 (D85); la corrida completa
de 21 casos lo bajó a 0,64 (D88, valor provisorio: T3.6 sigue abierta).

### Cómo se calibra el umbral (T3.6)

El umbral no es un criterio de aceptación hasta estar medido. Calibrar = medir la distribución real de
similitud de coseno sobre los chunks efectivamente ingesta dos y elegir el valor que separa las dos
poblaciones:

1. Correr los 21 casos (R1–R16, G6–G9, B2) contra la base ya ingesta y registrar la similitud top-1 de
cada pregunta (`scripts/calibrate_threshold.py --out TP/evidencia/calibracion_umbral.json`).
2. Separar dos poblaciones: preguntas **con** cobertura esperada (R1–R3, R9–R15, G6–G9, B2) y preguntas
**sin** cobertura (R4–R8, R16).
3. Elegir el umbral en el hueco entre ambas poblaciones, con un margen de seguridad de ~0,05.
4. Si no hay hueco (las poblaciones se solapan), el problema no es el umbral: es el chunking o el modelo
de embeddings. Se registra en `CHANGELOG.md` y se ajusta antes de fijar el número.
5. Reejecutar los casos con el umbral elegido y dejar la tabla de similitudes como evidencia del informe.

**Resultado medido** (2026-10-13, `gemini-embedding-001` sobre los chunks reales, 21 casos,
`TP/evidencia/calibracion_umbral.json`): los 15 casos con cobertura quedan entre **0,646 y 0,802** y los 6
sin cobertura entre **0,597 y 0,649**. Las poblaciones **se solapan** (`separable: false`, peor positivo
0,646 vs. mejor negativo 0,649), así que ningún umbral las separa: hace falta otro modelo de embeddings,
otro chunking o más casos negativos (T3.6, D88). La expectativa de 0,55–0,70 para relevantes y 0,25–0,40
para irrelevantes **no se confirmó**: los casos sin cobertura medidos quedan muy por encima de 0,40.

---

## 4. Prueba de clasificación de fuente (R-2.1)

Se corre el golden set completo y se mide:

- **Exactitud de clasificación:** ≥ 11/13 casos correctos.
- **Casos híbridos:** 3/3 invocan ambas tools.
- **Casos `none`:** 1/1 sin invocación de tools y sin afirmaciones inventadas.
- **Salida estructurada:** 13/13 con clasificación emitida antes de la primera invocación (R-2.7).

### 4.1 Entornos de ejecución de la prueba (R-2.8, D56, D59)

La misma prueba se corre en dos entornos con **propósitos distintos**:

| Entorno | Modelo | Qué valida | ¿Cuenta como aceptación? |
|---|---|---|---|
| Local | Servidor OpenAI-compatible en `127.0.0.1` (`LLM_MODEL=openai/<id>`, `LLM_API_BASE`) | El flujo: clasificación previa a las tools, tools por fuente, límites de intentos y pasos, composición, SQL aceptado por el validador. Sin cuota ni costo | **No** |
| Definitivo | Gemini con `GEMINI_API_KEY` (`LLM_MODEL=gemini/<modelo>`) | Los criterios de §4 con el modelo definitivo | **Sí** |

Reglas:

1. Orden: primero el modelo local para depurar el flujo; después, sin cambiar código ni prompts, Gemini.
2. Cada corrida se guarda con `scripts/measure_golden.py --out TP/evidencia/<archivo>.json`, que registra
   el modelo, el endpoint, la fecha, la configuración y el resultado por caso (R-6.5).
3. El seed entregable (T2.4/T2.5) no está: en las corridas del golden set la base de desarrollo
   (`db/dev_seed.sql`) y el corpus simulado son los backends falsos, y el validador de SQL es el real: la
   corrida mide clasificación, herramientas invocadas, orden y SQL aceptado, **no** el contenido (D59). Los
   `check` de contenido corren con `--db` (casos SQL) y con `--rag-mock` (casos RAG; D69); un híbrido se
   evalúa solo con ambos. Los PDFs sí existen y están ingesta dos: se usan en la calibración
   (`scripts/calibrate_threshold.py`), no en la corrida del golden set.
4. Un modelo local más débil puede clasificar bien y aun así generar peor SQL; que el validador rechace sus
   errores es el comportamiento esperado, no una falla de la prueba.
5. Si el modelo definitivo cambia (p. ej. por cuota), la medición de aceptación se repite completa.

Corridas registradas:

| Fecha | Modelo | Clasificación | Híbridos (2 tools) | `none` sin tools | Antes de tools | SQL rechazado | Cuenta como aceptación |
|---|---|---|---|---|---|---|---|
| 2026-10-10 | `gemini-3.1-flash-lite` | 13/13 | 3/3 | 1/1 | 13/13 | 0/8 | Sí (backends falsos: sin evaluar contenido). Evidencia: `TP/evidencia/golden_gemini-3.1-flash-lite_2026-10-10.json` |
| 2026-10-10 | Strata `qwen3.8-flash-next-iq2_xs` (local) | 12/13 clasificados + 1 error del clasificador (G12) | 2/3 | 1/1 | 12/13 | 0/7 | No: validación del flujo. Evidencia: `TP/evidencia/golden_strata-qwen3.8-flash-next-iq2_xs_2026-10-10.json` |
| 2026-10-11 | Strata `qwen3.8-flash-next-iq2_xs` (local), base local + RAG simulado (`--db --rag-mock`, D69) | 12/13 clasificados + 1 error del clasificador (G12, timeout) | 2/3 | 1/1 | 12/13 | 0/7 | No: validación del flujo y del contenido. Evidencia: `TP/evidencia/golden_strata-qwen3.8-flash-next-iq2_xs_2026-10-11_db-mock.json` |
| 2026-10-11 | `gemini-3.1-flash-lite`, base local + RAG simulado (`--db --rag-mock`, D69) | 13/13 | 3/3 | 1/1 | 13/13 | 0/8 | Sí para R-2.1: es el modelo definitivo (D71); el retrieval es simulado. Más 2 casos en inglés (`B1`, `B2`, fuera de los 13): 2/2 con idioma y contenido. Evidencia: `TP/evidencia/golden_gemini-3.1-flash-lite_2026-10-11_db-mock.json` y export de `agent_runs` en `TP/evidencia/agent_runs_2026-10-11.json` |
| 2026-10-11 | `gemini-3-flash-preview` (default del código en esa fecha, reemplazado por D71), `--db --rag-mock` | **no evaluable**: 3 casos respondidos y 10 errores del clasificador | — | — | — | — | No. Cuota diaria gratuita agotada (HTTP 429, 20 requests por día y por modelo); no hay evidencia de comportamiento del modelo. Sin archivo de evidencia |

Lectura de la corrida del 2026-10-11 (Strata, `--db --rag-mock`):

- **Contenido (`check` del golden set): 12/13** — SQL 5/5, RAG 4/4, híbridos 2/3, `none` 1/1. Es la primera
  vez que se evalúa el contenido de RAG e híbridos; los fragmentos salen del corpus simulado, así que
  prueba que el agente invoca la tool y cita, no la calidad del retrieval (D69).
- **G12 no se clasificó: timeout de la API** (`APITimeoutError`, 91,6 s con reintentos). Es un fallo
  técnico del modelo local, no una clasificación errónea; la corrida del 2026-10-10 también terminó en
  error del clasificador (`ClassificationError`). No se puede afirmar nada nuevo sobre G12 con este modelo.
- **Llamadas repetidas a la tool SQL:** G4 y G5 invocaron `execute_sql` dos veces y G11 tres, sin
  rechazos del validador (0/7). Es el comportamiento pendiente de limitar con un modelo débil; no afecta
  la corrección del contenido.
- Las 13 consultas quedaron en `agent_runs` (13/13).
- El seed de desarrollo se recargó ese día: sus fechas son relativas a `CURRENT_DATE` y envejecen.

Lectura de la corrida del 2026-10-11 con `gemini-3.1-flash-lite` (`--db --rag-mock`):

- **Clasificación 13/13, híbridos 3/3, `none` 1/1, 13/13 antes de tools, 0/8 SQL rechazado, 13/13 en
  `agent_runs`, contenido 13/13** (SQL 5/5, RAG 4/4, híbridos 3/3, `none` 1/1). El JSON versionado es
  la corrida regenerada con el criterio vigente.
- **Cambio de criterio de G11 (D72).** La primera corrida del día dio contenido 12/13 porque
  `_both_sources` exigía filas no vacías en un híbrido. G11 resolvió el socio con más préstamos y
  después consultó si tenía vencidos (relevante para la norma de renovación); esa consulta da 0 filas,
  que es la respuesta correcta (R-3.8), y `as_outcome()` toma las filas de la **última** sentencia. El
  agente no cambió: se corrigió el criterio, con test, y se regeneró la corrida. El 12/13 original
  queda en el historial de git (commit `da5283b`).
- **Latencia: 288 s en total, por la cuota de la API, no por el modelo.** Con instrumentación en una
  pasada previa se observaron esperas de 31 s y 34,7 s (nuestro reintento, D57) y de 148 s (el
  reintento propio de `smolagents`, que no respeta el tope de 60 s de D57). Los casos individuales
  tardan 2–25 s; en la corrida versionada G10 tardó 169 s, y las esperas caen en casos distintos según
  la corrida.
- **Casos en inglés (T7.6, R-5.1, D73): 2/2** con clasificación, idioma declarado `en`, contenido
  (filas / documento esperado) y prosa en inglés. La primera corrida dio **0/2 de contenido**: el modelo
  respondía en **castellano** y solo la línea de fuente salía "Source:". La causa era que el prompt, las
  herramientas y los documentos están en castellano; se corrigió instruyendo el idioma en el prompt y
  se repitió la corrida completa. La heurística de idioma mira palabras funcionales y es una excepción
  acotada a D16; la calidad de la prosa sigue siendo de la rúbrica manual.
- **Export de `agent_runs` (T7.7):** `TP/evidencia/agent_runs_2026-10-11.json` contiene las 13 consultas
  de esta corrida (12 `ok`, 1 `no_coverage`), con los campos de R-6.1, el modelo y el endpoint `api`.
  Se generó con `scripts/export_runs.py` antes de correr la suite de integración, que trunca la tabla.

Corrida con **base real** (PostgreSQL local con `db/dev_seed.sql`, rol `agent_ro`; recuperación todavía
falsa), `gemini-3.1-flash-lite`, casos SQL G1–G5, con `scripts/measure_golden.py --db`:

| Clasificación | Antes de tools | Contenido (`check` del golden set) | SQL rechazado | Consultas en `agent_runs` |
|---|---|---|---|---|
| 5/5 | 5/5 | **5/5** | 0/5 | 5/5 |

Es la primera medición de **contenido**: el SQL que genera el modelo corre contra el esquema real y
devuelve lo esperado. Los valores son el subconjunto SQL de
`TP/evidencia/golden_gemini-3.1-flash-lite_2026-10-11_db-mock.json`; la corrida `--db` sola no quedó
versionada. Los casos RAG e híbridos de esta corrida no se evaluaron en contenido.
Datos de desarrollo, no el seed entregable: el volumen de T2.5 sigue pendiente.

**Recuperación simulada (D69).** `--rag-mock` reemplaza el fragmento fijo por un corpus de 5 fragmentos de
prueba (`tests/rag_fixture.py`) con un `RagRetriever` real. Combinado con `--db`, permite evaluar el
contenido de los 13 casos. Qué mide y qué no:

| Mide | No mide |
|---|---|
| Que el agente decida la fuente, invoque la tool y cite documento y ubicación | Calidad del retrieval semántico (top-1 de R1–R3 con embeddings reales, 3.7) |
| Que la composición declare fuente y evidencia en RAG e híbridos | Calibración del umbral (3.6, D12, D85, D88): el del mock es 0,15 y no es comparable |
| El caso sin cobertura (G13/R4) con la política de no-relevancia | El contenido real del reglamento: los fragmentos son de prueba |

Toda fila medida con `--rag-mock` debe decirlo en la columna "Cuenta como aceptación". Los PDFs existen (6
en `rag/documents/pdf/`) y el umbral está medido (D85, D88); siguen pendientes el top-1 real de R1–R3
(T3.7) y el cierre de la calibración (T3.6).

Lectura de la corrida local: el error de G12 fue técnico, no de clasificación: el modelo razona y con
`max_tokens=1024` el servidor devolvió `finish_reason=length` con el JSON incompleto (3 de 3 intentos, D62).
Con el tope en 4096 G12 siguió sin clasificarse en las dos corridas versionadas de este modelo (error del
clasificador el 2026-10-10, timeout el 2026-10-11), así que el resultado queda 12/13 en ambas y no hay
medición de G12 clasificado como `rag`. Es un dato de un modelo local con cuantización agresiva; no se
extrapola a Gemini (D56). Además el modelo local repite consultas (hasta 11 llamadas a tools en G11 y 253 s
en G5): el flujo funciona, pero la latencia local no representa la del modelo definitivo.

---

## 5. Definition of Done (por tarea)

Una tarea de `openspec/changes/agente-y-tools/tasks.md` está terminada solo si:

- [ ] Traza a un requisito con ID (`R-x.y`).
- [ ] Su validación específica está aprobada.
- [ ] El golden set sigue verde (no se rompió nada).
- [ ] Hay evidencia en `agent_runs` o en un test.
- [ ] La decisión de diseño relevante quedó registrada en `CHANGELOG.md`.

---

## 6. Evidencias para el informe

- Salida de la API (`curl -N` sobre `POST /ask`) por cada tipo de consulta (SQL, RAG, híbrida,
  no-cobertura), o capturas del frontend que la consume. **Pendiente:** no hay salida ni capturas
  versionadas en `TP/`; el contrato está cubierto por los tests de §7 (A1–A11, O1–O7).
- Export de `agent_runs` con las 13 consultas del golden set (`TP/evidencia/agent_runs_2026-10-11.json`).
- Output de `pytest` con los casos de sanitización: 18 adversos de `tests/test_sql_validator.py` (S1–S9,
  S13–S20, incluido S16b), 31 adversos de `tests/test_sql_validator_hardening.py` (S23–S33 y B1–B31), 18
  consultas que deben aceptarse (S21, S22, S32, S33 y `ACCEPTED`), S10 en la ejecución
  (`tests/test_sql_tool_offline.py`) y S11–S12 en los tests de regeneración del executor.
- Conteo por tabla (`SELECT count(*)`) mostrando ≥15 registros. **Pendiente (T2.5):** `db/seed.sql` aporta
  70 libros, 57 autores, 28 editoriales, 18 categorías, 20 socios y 29 préstamos, pero el conteo no se corrió
  contra la base y `db/seed_data.py` (T2.4) no está implementado.

## 7. Pruebas de la API (R-1.3, R-6.7, R-7.0 a R-7.8)

Corren sin modelo ni base (`pytest -q`): la API contra un doble de `answer()`. Verifican el **contrato**
(qué eventos salen, en qué orden, qué se rechaza), no la calidad de las respuestas, que se mide con el
golden set (§1 y §4). La API es el único acceso al agente (R-7.0, D80): la presentación de la respuesta
y la evidencia (R-5.3, R-5.4) corresponden al frontend (`web/`, D93; sus pruebas, en el change `frontend-web-vite`), que consume el evento `result`.

| ID | Requisito | Caso | Test |
|---|---|---|---|
| A1 | R-7.7 | `GET /health` responde `ok` sin invocar al agente | `test_api.py::test_health_answers_without_invoking_the_agent` |
| A2 | R-7.4, R-1.2 | Consulta vacía o de espacios: 422 y el agente no se invoca | `test_api.py::test_an_empty_question_is_rejected_before_opening_the_stream` |
| A3 | R-7.1, R-7.2 | Orden `start, classified, tool_call, tool_result, composing, result` | `test_api.py::test_the_stream_reports_progress_in_order_and_ends_with_the_full_answer` |
| A4 | R-7.1 | `result` trae `answer`, `answer_kind`, `sources`, `evidence`, `run_id` | `test_api.py::test_the_result_event_carries_the_complete_agent_answer` |
| A5 | R-7.2, Art. 4 | Solo `result` declara `sources` | `test_api.py::test_only_the_result_event_declares_sources` |
| A6 | R-7.1 | Fechas y decimales de las filas se serializan | `test_api.py::test_dates_and_decimals_in_the_rows_are_serialized` |
| A7 | R-7.6 | Excepción inesperada: `start` y `error`, sin `result` | `test_api.py::test_an_unexpected_exception_is_reported_as_an_error_event` |
| A8 | R-7.3 | Latidos mientras el agente está en silencio | `test_api.py::test_heartbeats_are_sent_while_the_agent_is_silent` |
| A9 | R-7.3 | `result` no espera al intervalo de latido (regresión, D79: 5,01 s medidos) | `test_api.py::test_the_result_is_not_delayed_by_the_heartbeat_interval` |
| A10 | R-7.5 | Al cerrar el flujo, el agente recibe la señal de cancelación | `test_api.py::test_closing_the_stream_cancels_the_agent` |
| A11 | R-7.5 | Una consulta cancelada no emite `result` ni `error` | `test_api.py::test_a_cancelled_answer_does_not_emit_a_result` |
| C1 | R-1.3 | Dos consultas simultáneas se serializan | `test_agent.py::test_concurrent_answers_are_serialized` |
| C2 | R-6.7 | Consulta cancelada: lanza `AnswerCancelled` y no registra | `test_agent.py::test_a_cancelled_question_raises_and_records_nothing` |
| C3 | R-6.7 | Cancelada durante la ejecución: se descarta la respuesta | `test_agent.py::test_cancelling_during_the_run_discards_the_answer` |
| C4 | R-7.2 | Los eventos de progreso siguen el flujo y reportan una sentencia rechazada | `test_agent.py::test_progress_events_follow_the_flow_in_order`, `::test_a_rejected_statement_is_reported_as_a_failed_tool_result` |
| C5 | R-7.2 | Los eventos `step` salen de los callbacks del framework; `cancel` interrumpe antes del siguiente paso | `test_agent_smolagents.py::test_step_events_come_from_the_framework_callbacks`, `::test_cancel_interrupts_the_framework_before_the_next_step` |
| C6 | R-5.2 | El texto de `answer` no lleva línea de fuente (`sql`, `rag`, `hybrid`, `none`); la que escriba el modelo se retira y `sources` sigue siendo la de las herramientas | `test_agent.py::test_sql_answer_declares_source_and_shows_the_executed_statement`, `::test_the_answer_declares_the_language_of_the_question`, `::test_a_source_line_written_by_the_model_is_removed_from_the_answer` |
| E1 | R-5.3, R-5.4 | La evidencia trae la sentencia y cada fragmento con documento, ubicación y texto | `test_agent.py::test_rag_answer_cites_document_and_location`, `test_agent.py::test_sql_answer_declares_source_and_shows_the_executed_statement` |
| I1 | R-7.0 | La imagen `runtime` sirve la API y no una interfaz; no hay Streamlit en las dependencias | `test_dockerfile.py::test_the_runtime_stage_serves_the_http_api_and_no_ui`, `::test_the_runtime_dependencies_do_not_include_a_ui_framework` |
| O1 | R-7.8 (origen permitido) | Preflight `OPTIONS` a `POST /ask`: 200 con `Access-Control-Allow-Origin` del origen declarado | `test_api_cors.py::test_allowed_origin_gets_the_cors_header` |
| O2 | R-7.8 (origen permitido) | Llamada simple, sin preflight, lleva el header | `test_api_cors.py::test_a_simple_request_from_an_allowed_origin_carries_the_header` |
| O3 | R-7.8 (origen no declarado) | Preflight rechazado y sin `Access-Control-Allow-Origin` | `test_api_cors.py::test_a_disallowed_origin_is_rejected_without_the_cors_header` |
| O4 | R-7.8 (sin orígenes configurados) | Con `API_ALLOWED_ORIGINS` vacío no hay wildcard `*` ni header | `test_api_cors.py::test_no_wildcard_when_no_origins_are_configured` |
| O5 | R-7.8 (origen permitido, streaming) | El stream SSE conserva el header y termina con `result` | `test_api_cors.py::test_the_stream_from_an_allowed_origin_carries_the_header` |
| O6 | R-7.8 (configuración por entorno) | Los orígenes se leen de `API_ALLOWED_ORIGINS` y la app los usa | `test_api_cors.py::test_origins_are_read_from_api_allowed_origins`, `::test_the_app_uses_the_configured_origins` |
| O7 | R-7.8 (sin credenciales) | La consulta se procesa sin credenciales y la respuesta no las refleja | `test_api_cors.py::test_no_credentials_are_required_from_an_allowed_origin` |

**Qué no cubren:** el streaming real sobre `uvicorn` y un proxy (los tests usan `TestClient`). Del CORS se
cubren el preflight y el comportamiento de los headers con `TestClient` (O1–O7); lo que no se cubre es la
llamada real desde un navegador con el frontend, que es la tarea 9.12. La presentación de la respuesta y la
evidencia es del frontend.

**Hallazgos al escribirlas (2026-10-13):** (1) A9 falló con 5,01 s: el `result` se retrasaba hasta el
intervalo de latido en cada consulta; (2) `test_step_events_come_from_the_framework_callbacks` fallaba en
Windows porque un paso rápido da `duration_s == 0.0` y `0.0 or 0` devolvía un entero. Ambos se
corrigieron (D79).

### 7.1 Costo de atender en serie (R-1.3, D77, T9.11)

Medición, no test: afirma tiempos y un test de tiempos sería flaky en CI. Corre sin base, sin
credenciales y sin modelo (`scripts/measure_queue.py`): la app real sobre `uvicorn` en un puerto efímero
con el `answer()` real de `LibraryAgent` (su `_lock` real, D77) sobre dobles de `tests/fakes.py` — base
falsa, clasificador doble, registro apagado — y un runner doble donde lo único que tarda es la llamada
al modelo, que duerme un tiempo de servicio S. S es simulado, no latencia de modelo. El evento `start`
sale al abrir el stream, antes de tomar el lock, así que la espera se lee en el primer evento del agente
(`classified`).

| S (s) | N | Espera antes de trabajar, por orden de entrada (s) | `result` (s) | Latidos recibidos |
|---|---|---|---|---|
| 1.0 | 1 | 0.0 | 1.0 | 0 |
| 1.0 | 2 | 0.0, 1.0 | 1.0, 2.0 | 0 |
| 1.0 | 3 | 0.0, 1.0, 2.0 | 1.0, 2.0, 3.0 | 0 |
| 1.0 | 5 | 0.0, 1.0, 2.0, 3.0, 4.0 | 1.0, 2.0, 3.0, 4.0, 5.0 | 0 |
| 6.0 | 3 | 0.0, 6.0, 12.0 | 6.0, 12.0, 18.0 | 1, 2, 3 |

La espera de la k-ésima consulta es `(k-1)·S`: el script ejerce el lock real del agente, así que esa
espera es la serialización de R-1.3 medida, no una predicción; lo simulado sigue siendo solo S. En las
corridas del 2026-10-13 el `result` llega en `k·S + 15–32 ms` (transporte y arranque del hilo del
agente); la espera de cola, medida desde que la consulta entra al agente, es `(k-1)·S` sin ese agregado.
Que dos consultas no se solapan en la llamada al modelo está probado por el test determinista
`test_agent.py::test_two_concurrent_answers_do_not_overlap_in_the_model_call` (eventos de `threading`,
sin reloj de pared); la serialización del agente la cubre el caso C1
`test_agent.py::test_concurrent_answers_are_serialized`. Con `HEARTBEAT_S = 5` el cliente que
espera recibe latidos (fila S=6), así que su conexión no se corta por inactividad mientras está en la
cola (R-7.3). El cliente cancelado no se interrumpe mientras espera: `answer()` toma el lock antes de
`_check_cancelled`, así que la señal se atiende al recibir el turno (R-7.5, D76).

Reproducir: `python scripts/measure_queue.py --service-time 1.0 --counts 1 2 3 5` y
`python scripts/measure_queue.py --evidence`. No necesita base, API key ni modelo.

Latencias reales ya medidas en `TP/evidencia/` (no se volvió a llamar al modelo; las mayores están
infladas por esperas de cuota, D70):

| Archivo | n | min | mediana | max |
|---|---|---|---|---|
| `agent_runs_2026-10-11.json` | 13 | 0,9 s | 6,0 s | 224,5 s |
| `golden_gemini-3.1-flash-lite_2026-10-10.json` | 13 | 3,0 s | 11,8 s | 73,8 s |
| `golden_gemini-3.1-flash-lite_2026-10-11_db-mock.json` | 15 | 2,8 s | 8,9 s | 169,1 s |
| `golden_strata-qwen3.8-flash-next-iq2_xs_2026-10-10.json` | 13 | 4,9 s | 40,7 s | 253,8 s |
| `golden_strata-qwen3.8-flash-next-iq2_xs_2026-10-11_db-mock.json` | 13 | 5,3 s | 22,8 s | 91,6 s |

Espera del último concurrente con la mediana de `agent_runs_2026-10-11.json` (6,0 s): 12,0 s para 3
personas y 24,0 s para 5. Peor caso con las latencias mayores ya medidas: 271,7 s (suma de las 2 mayores,
3 personas) y 296,4 s (suma de las 4 mayores, 5 personas).

**Dos opciones (análisis, no implementado).** Verificado en código: cada backend guarda una sola
conexión (`sql_backend`, `retriever`, `recorder`: tres por agente), el agente es un singleton de módulo
(`get_agent()`) con backends compartidos, y el estado por consulta no se comparte porque `ToolSession` y
`ToolCallingAgent` se crean en cada consulta.

| Opción | Impacto | Riesgo | Compatible con R-1.3, R-6.7, D76 |
|---|---|---|---|
| Un agente por sesión | Cada sesión abre sus tres conexiones; la serialización queda dentro de la sesión | El número de conexiones crece con las sesiones y choca con `max_connections` de la base; hace falta un registro de agentes en lugar del singleton | R-1.3 se cumple por sesión; R-6.7 y D76 no cambian |
| Pool de conexiones con agente compartido | Una conexión prestada por consulta; varias consultas avanzan a la vez | Requiere ciclo de vida del pool y que `SET LOCAL` / sesión solo lectura se aplique por conexión prestada; el estado de espera del recorder sigue siendo compartido. Seguridad de la instancia compartida del cliente de modelo: no verificado | R-1.3 deja de ser serial global: hay que reescribirlo |

**Recomendación:** para una demostración de 3 a 5 personas mantener la serialización (D77) — la espera
típica es de 12 a 24 s y los latidos mantienen viva la conexión. Cambiar solo si la consigna exige
consultas realmente simultáneas; en ese caso conviene la opción por sesión, que no exige reescribir el
requisito de serialización. Como propuesta, no aplicada: un R-1.4 nuevo que fije el ámbito de la
serialización (por sesión o por pool) y el máximo de conexiones.
