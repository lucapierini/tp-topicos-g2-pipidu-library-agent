# Validación — Golden set y pruebas

> Última etapa del ciclo SDD: `Requirement → Spec → Plan → Tasks → Implementation → Validation`.
> Esta es la sección que sustenta las "evidencias de funcionamiento" del informe técnico.

---

## 1. Golden set — casos con respuesta esperada

Se ejecutan siempre contra la misma semilla de datos (`--seed 42`), para que la respuesta esperada
sea determinista.

### Método de afirmación (D16)

Los casos se afirman sobre **clasificación, SQL y filas devueltas**, no sobre la prosa generada, porque
el texto del modelo no es determinista. La prosa se valida con una rúbrica manual de 3 criterios:

1. La fuente declarada coincide con la herramienta efectivamente invocada.
2. Los valores citados coinciden con la evidencia.
3. El idioma y el formato cumplen R-5.5 y R-5.6.

Cada caso queda en `tests/test_golden_set.py` con la afirmación automática y el resultado de la rúbrica.

### Casos SQL (≥5, criterio de aprobación 2)

| # | Pregunta esperada | Fuente esperada | Resultado esperado |
|---|---|---|---|
| G1 | ¿Qué libros tiene prestados el socio Juan Pérez? | SQL | Lista de títulos con fecha de préstamo |
| G2 | ¿Cuáles son los 5 libros más prestados este cuatrimestre? | SQL | Ranking de 5 títulos con conteo |
| G3 | ¿Qué socios tienen préstamos vencidos? | SQL | Lista de socios con días de atraso |
| G4 | ¿Cuántos libros de la categoría "Ciencias de la Computación" hay disponibles? | SQL | Conteo de ejemplares disponibles |
| G5 | ¿Qué autor tiene más libros publicados por la editorial X? | SQL | Autor + cantidad |

### Casos RAG (≥4, criterio de aprobación 3)

| # | Pregunta | Fuente esperada | Resultado esperado |
|---|---|---|---|
| G6 | ¿Cuántos días tengo para devolver un libro antes de que me multen? | RAG | Plazo exacto citado del reglamento |
| G7 | ¿De qué trata el libro "X"? | RAG | Sinopsis citada de la reseña |
| G8 | ¿Cómo renuevo un préstamo desde el sistema? | RAG | Pasos del manual de uso |
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
| G13 | ¿Cuál es el precio del libro X? | ninguna | Declaración de "no dispone de información suficiente" |

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
| S10 | `SELECT * FROM libros LIMIT 100000` | límite aplicado (≤50 filas) |

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

| # | Pregunta | Criterio |
|---|---|---|
| R1 | Pregunta sobre plazo de devolución | top-1 pertenece a `reglamento_biblioteca.pdf` |
| R2 | Pregunta sobre sinopsis de un libro del catálogo | top-1 pertenece a la reseña correspondiente |
| R3 | Pregunta sobre pasos del sistema | top-1 pertenece a `manual_uso_sistema.pdf` |
| R4 | Pregunta fuera de cobertura | similitud máxima < umbral → reporte de no-relevancia |

top-k = 5 y umbral de similitud de coseno = 0.35, calibrados contra los PDFs reales antes de fijarlos
como valor de aceptación; el valor definitivo se registra en `CHANGELOG.md` (D12, R-4.8).

### Cómo se calibra el umbral (T3.6)

0.35 es un **punto de partida**, no un criterio de aceptación. Calibrar = medir la distribución real de
similitud de coseno sobre los chunks efectivamente ingesta dos y elegir el valor que separa las dos
poblaciones:

1. Correr R1–R4 contra la base ya ingesta y registrar la similitud top-1 de cada pregunta.
2. Separar dos poblaciones: preguntas **con** cobertura esperada (R1–R3) y preguntas **sin** cobertura (R4).
3. Elegir el umbral en el hueco entre ambas poblaciones, con un margen de seguridad de ~0.05.
4. Si no hay hueco (las poblaciones se solapan), el problema no es el umbral: es el chunking o el modelo
de embeddings. Se registra en `CHANGELOG.md` y se ajusta antes de fijar el número.
5. Reejecutar R1–R4 con el umbral elegido y dejar la tabla de similitudes como evidencia del informe.

Con `gemini-embedding-001` las similitudes relevantes suelen ubicarse entre 0.55 y 0.70 y las
irrelevantes entre 0.25 y 0.40, por lo que 0.35 puede resultar demasiado permisivo: queda sujeto a la
medición, no a la discusión.

---

## 4. Prueba de clasificación de fuente (R-2.1)

Se corre el golden set completo y se mide:

- **Exactitud de clasificación:** ≥ 11/13 casos correctos.
- **Casos híbridos:** 3/3 invocan ambas tools.
- **Casos `none`:** 1/1 sin invocación de tools y sin afirmaciones inventadas.
- **Salida estructurada:** 13/13 con clasificación emitida antes de la primera invocación (R-2.7).

---

## 5. Definition of Done (por tarea)

Una tarea de `04-tareas.md` está terminada solo si:

- [ ] Traza a un requisito con ID (`R-x.y`).
- [ ] Su validación específica está aprobada.
- [ ] El golden set sigue verde (no se rompió nada).
- [ ] Hay evidencia en `agent_runs` o en un test.
- [ ] La decisión de diseño relevante quedó registrada en `CHANGELOG.md`.

---

## 6. Evidencias para el informe

- Captura de la UI por cada tipo de consulta (SQL, RAG, híbrida, no-cobertura).
- Export de `agent_runs` con las 13 consultas del golden set.
- Output de `pytest` con los 10 casos de sanitización.
- Conteo por tabla (`SELECT count(*)`) mostrando ≥15 registros.
