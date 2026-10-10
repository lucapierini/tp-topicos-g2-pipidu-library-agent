# Design

## Context

Proyecto greenfield. No existe código todavía. La motivación está en `proposal.md`. Las
restricciones que condicionan el diseño son las de `TP/00-constitucion.md` (read-only por diseño,
proveniencia obligatoria, trazabilidad de ejecución) y los criterios de promoción elegidos:
despliegue en GCP, UI Streamlit, framework agéntico y SDD.

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
- Autenticación de usuarios, streaming de respuestas y reintentos ante fallo de API.

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
| D10 | Chunking por cláusula, tope 800 / solapamiento 150 | R-4.3 |
| D11 | Idempotencia por `sha256(contenido)` | R-4.5 |
| D12 | top-k = 5, umbral 0.35 calibrado con medición | R-4.4, R-4.8 |
| D13 | Índice HNSW `vector_cosine_ops` | T3.4 |
| D14 | Usuario dedicado `agent_ro` + timeout + `search_path` | R-3.5 |
| D15 | `max_steps = 6`, temperatura 0, timeout de API 30 s | Art. 7, R-6.2 |
| D16 | Aserción sobre clasificación, SQL y filas; prosa con rúbrica manual | Art. 6, Art. 7 |
| D17 | Historial de UI solo visual | T8.3 |
| D18 | Cloud Run + Cloud SQL + Secret Manager | criterio de promoción 1 |
| D19 | PDFs generados por el integrante de RAG y base de datos | G6–G9, R1–R3 |
| D20 | Un artefacto, un solo lugar | `TP/README.md` |
| D21 | Whitelist excluye `agent_runs` y `documentos_embeddings` | R-3.4 |
| D22 | `prestamos_estado` como vista en la whitelist | R-3.12 |
| D23 | Mapa alias→tabla antes de la whitelist (CTEs y alias) | R-3.4 |
| D24 | El límite de 50 filas lo aplica la ejecución, no la validación | R-3.6 |
| D25 | `SELECT *` se expande a las columnas de la whitelist | R-3.4 |
| D26 | Allowlist de funciones, código `FUNCTION_NOT_ALLOWED` | R-3.13 |
| D27 | `FOR UPDATE` rechazado como no-lectura | R-3.2 |
| D28 | Identificadores normalizados a minúsculas | R-3.4 |
| D29 | `error_level=RAISE` en el parseo | R-3.3 |
| D30 | Se registra la sentencia normalizada; `sql_original` conserva la del modelo | R-3.9, R-6.4 |
| D31 | Los literales no se modifican por la normalización | Art. 4 |

## Risks / Trade-offs

- **[Text-to-SQL poco preciso]** → mitigación: few-shot de 8 ejemplos en el prompt + golden set de 5 casos SQL que se ejecuta en CI local con `pytest`.
- **[Clasificación de fuente inestable por no determinismo]** → mitigación: temperatura 0, golden set de 13 casos, umbral de aceptación ≥11/13 documentado en `TP/05-validacion.md`.
- **[Retrieval devuelve fragmentos irrelevantes y el agente alucina]** → mitigación: umbral de similitud mínimo (R-4.6) obliga a declarar "no se encontró información relevante".
- **[Cloud SQL sin pgvector disponible en la región/cuota]** → mitigación: spike de despliegue en la semana 1, antes de dependencias de mayor tamaño.
- **[Costo de tokens por el ciclo SDD]** → mitigación: artefactos cortos, constitution de 1 página, tareas sin narrativa.

## Migration Plan

1. `docker compose up` con Postgres + pgvector en local.
2. `db/schema.sql` (incluye `readonly_role`, `documentos_embeddings`, `agent_runs`).
3. `db/seed_data.py --seed 42` → `db/dump.sql` para el entregable.
4. `rag/ingest.py` sobre los PDFs.
5. Despliegue: imagen Docker → Cloud Run; Cloud SQL con pgvector; Secret Manager para `GEMINI_API_KEY`.
6. Rollback: el despliegue no muta datos; basta con redeployear la imagen anterior.

## Open Questions

Ninguna abierta. Las tres que había se cerraron: evaluación del golden set (D16), semántica temporal
(D6) y origen de los PDFs (D19). Lo único pendiente es numérico, no conceptual: el umbral de similitud
definitivo (D12) se cierra con la medición de T3.6.
