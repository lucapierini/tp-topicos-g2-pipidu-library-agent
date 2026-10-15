# Proposal

## Why

El agente (change `agente-y-tools`) consulta una base relacional y un repositorio documental, pero
el origen y la justificación de ambos vivían en otro repositorio (`UCSE-2026-TAIA`, features 01 y 02).
El esquema se adoptó como "compartido" (D64) sin que en este repo figurara por qué tiene esa forma,
dónde corre, cómo se pobló ni de dónde salen los documentos del RAG. Sin eso, el informe no puede
sustentar el modelo de datos y las tareas 2.4, 2.5, 3.1 y 9.6 quedan sin respaldo.

Este change trae esa justificación y los artefactos que la sostienen, y la deja trazable con SDD.

## What Changes

- Se documenta la elección de **Neon** (PostgreSQL gestionado + pgvector + bucket privado) como
  base compartida, y sus consecuencias sobre el despliegue en GCP (solo agente + UI).
- Se versiona la justificación del DDL (decisiones D-DB1 a D-DB10 en `design.md`).
- Se incorpora el **seed** con catálogo real y socios/préstamos sintéticos (`db/seed.sql`).
- Se incorporan los **5 documentos fuente del RAG** en Markdown, sus PDFs, y los scripts de
  conversión y subida al bucket (`rag/`).
- Se registran las reglas de negocio que viven en el reglamento y no en la base.

## Capabilities

### New Capabilities

- `esquema-de-base-de-datos`: forma, restricciones, vista de vencimiento y roles del esquema en Neon.
- `datos-de-prueba`: contenido, volumen y reproducibilidad del seed.
- `documentos-fuente-rag`: documentos, consistencia de sus reglas, PDFs y bucket privado.

### Modified Capabilities

_(ninguna: `rag-retrieval-tool` y `sql-query-tool` no cambian su comportamiento; este change
fundamenta los datos sobre los que operan)_

## Out of Scope

- Chunking, embeddings e ingesta en pgvector (`agente-y-tools`, tareas 3.2–3.5).
- Login y contraseña del rol de solo lectura en Neon; hoy el agente usa `agent_ro` en la base local (9.7).
- Seed con semilla fija (`db/seed_data.py`, tarea 2.4): el seed de este change es SQL estático.

## Impact

- Archivos nuevos: `db/seed.sql`, `rag/documents/*.md`, `rag/documents/pdf/*.pdf`,
  `rag/build_pdfs.py`, `rag/upload_to_bucket.py`, `rag/requirements.txt`.
- `.gitignore`: se agregan `.env.local` (credenciales de Neon) y `.neon/` (enlace local).
- Tareas de `agente-y-tools` que este change respalda: 2.1, 2.4 (parcial), 2.5, 2.7, 3.1, 9.6, 9.8.
- Origen: `UCSE-2026-TAIA`, rama `feature/initial-database` (docs `feature-01` y `feature-02`).
