# Proposal

## Why

El agente (change `agente-y-tools`) consulta una base relacional y un repositorio documental. En este
repo no figuraba por qué el esquema (D64) tiene esa forma, dónde corre, cómo se pobló ni de dónde salen los documentos del RAG. Sin eso, el informe no puede sustentar el modelo de datos.

Este change trae esa justificación y los artefactos que la sostienen, y la deja trazable con SDD.

## What Changes

- Se documenta la elección de **PostgreSQL con pgvector en Docker** como única base: el sistema corre en el entorno local y la UI es la SPA de `web/` (D93).
- Se versiona la justificación del DDL (decisiones D-DB1 a D-DB10 en `design.md`).
- Se incorpora el **seed** con catálogo real y socios/préstamos sintéticos (`db/seed.sql`).
- Se incorporan los **6 documentos fuente del RAG** en Markdown, sus PDFs, y el script de
  conversión (`rag/`).
- Se registran las reglas de negocio que viven en el reglamento y no en la base.

## Capabilities

### New Capabilities

- `esquema-de-base-de-datos`: forma, restricciones, vista de vencimiento y roles del esquema.
- `datos-de-prueba`: contenido, volumen y reproducibilidad del seed.
- `documentos-fuente-rag`: documentos, consistencia de sus reglas, PDFs versionados.

### Modified Capabilities

_(ninguna: `rag-retrieval-tool` y `sql-query-tool` no cambian su comportamiento; este change
fundamenta los datos sobre los que operan)_

## Out of Scope

- Chunking, embeddings e ingesta en pgvector: los implementa `agente-y-tools` (`rag/ingest.py`).
- Login y contraseña del rol de solo lectura: el agente se conecta con `agent_ro` a la base local.
- Seed generado con semilla fija por script: el seed de este change es SQL estático (`db/seed.sql`).

## Impact

- Archivos nuevos: `db/seed.sql`, `rag/documents/*.md`, `rag/documents/pdf/*.pdf`,
  `rag/build_pdfs.py`, `rag/requirements.txt`.
- `.gitignore`: se agrega `.env.local` (credenciales locales).
- Tareas de `agente-y-tools` que este change respalda: 2.1 y 2.7.
- Origen: `UCSE-2026-TAIA`, rama `feature/initial-database` (docs `feature-01` y `feature-02`).
