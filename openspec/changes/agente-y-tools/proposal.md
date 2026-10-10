# Proposal

## Why

El TP exige un agente que reciba consultas en lenguaje natural y responda correctamente combinando
una base de datos relacional y un repositorio documental RAG. La aprobación depende de que el agente
**decida por sí mismo** qué fuente consultar, y la promoción depende de que esa decisión sea
observable, testeable y reproducible. Sin una spec de comportamiento, la selección de fuente y la
seguridad del SQL quedan como decisiones implícitas durante la implementación.

## What Changes

- Nuevo agente orquestador (Smolagents) que clasifica cada consulta en `sql`, `rag`, `hybrid` o `none`.
- Nueva tool `sql_query_tool` con validación estática de sentencias y ejecución en rol de solo lectura.
- Nueva tool `rag_search_tool` con retrieval top-k por similitud de coseno y umbral mínimo.
- Nueva política de composición de respuesta con proveniencia declarada y evidencia exhibida.
- Nuevo registro de ejecución por consulta (tabla `agent_runs`) como evidencia para el informe.
- Pipeline de ingesta RAG idempotente sobre 4–6 PDFs.

## Capabilities

### New Capabilities

- `entrada-de-consulta`: cómo el sistema recibe la consulta en lenguaje natural y qué rechaza.
- `seleccion-de-fuente`: clasificación autónoma de la consulta y qué herramienta se invoca.
- `sql-query-tool`: generación y ejecución segura de `SELECT` contra la base relacional.
- `rag-retrieval-tool`: recuperación de fragmentos documentales relevantes con su referencia de origen.
- `composicion-de-respuesta`: formato de la respuesta, idioma y proveniencia de la fuente.
- `trazabilidad-de-ejecucion`: registro de cada consulta para validación y evidencias.

### Modified Capabilities

_(ninguna — es el primer change del proyecto)_

## Impact

- Nuevas tablas: las 6 del modelo relacional + `documentos_embeddings` (pgvector) + `agent_runs`.
- Nuevo rol de base de datos `readonly_role`.
- Nuevas dependencias: `smolagents`, `psycopg2-binary`, `pypdf`, `google-genai`, `streamlit`, `pytest`.
- Nueva variable de entorno: `GEMINI_API_KEY`, credenciales de Cloud SQL.
- Depende de un despliegue en GCP (Cloud Run + Cloud SQL) para el criterio de promoción 1.
