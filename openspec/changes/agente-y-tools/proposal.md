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
- Nueva API HTTP (`POST /ask`), único acceso al agente (D80), con respuesta en streaming de eventos de
  progreso y cancelación cuando el cliente corta la conexión. No hay interfaz gráfica propia: el frontend
  es un cliente externo que consume la API.
- Atención en serie de las consultas simultáneas, porque cada backend guarda una única conexión.

## Capabilities

### New Capabilities

- `entrada-de-consulta`: cómo el sistema recibe la consulta en lenguaje natural y qué rechaza.
- `seleccion-de-fuente`: clasificación autónoma de la consulta y qué herramienta se invoca.
- `sql-query-tool`: generación y ejecución segura de `SELECT` contra la base relacional.
- `rag-retrieval-tool`: recuperación de fragmentos documentales relevantes con su referencia de origen.
- `composicion-de-respuesta`: formato de la respuesta, idioma y proveniencia de la fuente.
- `trazabilidad-de-ejecucion`: registro de cada consulta para validación y evidencias.
- `consulta-por-api`: consulta por HTTP con progreso en streaming, latido, cancelación y estado del servicio.

### Modified Capabilities

_(ninguna — es el primer change del proyecto)_

## Impact

- Esquema compartido (D64): `autores`, `editoriales`, `categorias`, `libros`, `libros_autores`, `socios`,
  `prestamos`, la vista `v_prestamos_estado` y el repositorio documental `documentos` +
  `documentos_chunks` (pgvector). Este change agrega `agent_runs` (`db/migrations/001_agent_runs.sql`).
- Roles de base de datos: `agent_ro` (solo lectura) y `agent_logger` (solo `INSERT` en `agent_runs`, D63).
- Nuevas dependencias: `smolagents[litellm]`, `psycopg2-binary`, `pypdf`, `google-genai`, `sqlglot`,
  `fastapi`, `uvicorn` (la API HTTP, D75) y `pytest`.
- Contenedor en ejecución: la imagen `runtime` arranca `uvicorn api.app:app` en `PORT` (8080 por defecto, D80).
- Nuevas variables de entorno: `GEMINI_API_KEY`, credenciales de Cloud SQL y, para cambiar de proveedor sin
  tocar código, `LLM_MODEL`, `LLM_API_BASE` y `LLM_API_KEY` (R-2.8). El flujo se valida primero contra un
  modelo local y la aceptación se mide después con Gemini.
- Depende de un despliegue en GCP (Cloud Run + Cloud SQL) para el criterio de promoción 1.
