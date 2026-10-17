# Design

## Context

El esquema, el seed y los documentos del RAG se diseñaron aparte (D19) y se versionan en este repo. Se
definieron **antes de crear ninguna tabla** y se validaron aplicándolos sobre una base vacía antes de darlos por buenos. Ese orden es parte de la justificación: el DDL aprobado es el que corre, no un borrador.

Condición de contorno: tres integrantes. Cada uno levanta la misma base local con `docker compose`, sin administrar una instancia compartida.

## Goals / Non-Goals

**Goals:**
- Que el esquema justifique cada decisión que condiciona al agente (text-to-SQL, seguridad, RAG).
- Que los datos y documentos sean reproducibles desde este repo.

**Non-Goals:**
- Cambiar el entorno de ejecución: la base corre en Docker (D65), que es el entorno de desarrollo y de CI.
- Ingesta de embeddings (otro change).

## Arquitectura

```mermaid
flowchart TB
    subgraph LOCAL[Entorno local - docker compose]
        UI[SPA de web/] --> API[API] --> AGENT[Agente Smolagents]
    end
        PG[(PostgreSQL 17 + pgvector)]
    end
    AGENT -->|rol de solo lectura| PG
    INGEST[rag/ingest.py] -->|dueño de la base| PG
    SEED[Esquema / seed] -->|dueño de la base| PG
```

El sistema corre en el entorno local de `docker compose`, con la SPA de `web/` como interfaz (D93).

| Uso | Conexión | Motivo |
|---|---|---|
| DDL, seed, ingesta | dueño de la base | Escriben; el agente en ejecución no usa esta conexión |
| SQL tool | rol de solo lectura (`agent_ro`), la misma conexión de la app y sesión marcada como de lectura | Defensa en profundidad (R-3.5, D63) |

## Decisions

Las decisiones de este change se numeran `D-DB1…D-DB10` para no colisionar con `D1…D101` de
`TP/CHANGELOG.md`, que es el registro canónico; allí se asientan con alternativa descartada y motivo
(entrada del 2026-10-13).

| ID | Decisión | Alternativa descartada y motivo | Traza |
|---|---|---|---|
| D-DB1 | PostgreSQL con pgvector en Docker como única fuente de datos; el sistema corre en el entorno local y la UI es la SPA de `web/` | Base en la nube (Cloud SQL): más costo y fricción con pgvector sin aportar al alcance local | R-7.1, D81, D93 |
| D-DB2 | `GENERATED ALWAYS AS IDENTITY` | `SERIAL`: no estándar y permite insertar ids a mano | R-7.2 |
| D-DB3 | `libros_autores` N:M | `libros.autor_id`: no representa libros con varios autores (Russell & Norvig). Origen de D64 | R-7.3 |
| D-DB4 | `prestamos.estado` solo `activo`/`devuelto`, con CHECK contra `fecha_devolucion_real` | Guardar `vencido`: se desactualiza con el paso del tiempo | R-7.4 |
| D-DB5 | Vista `v_prestamos_estado` con `estado_calculado` y `dias_atraso` | Que el agente calcule fechas: duplica lógica y es fuente de errores en el SQL generado | R-7.5 |
| D-DB6 | `ejemplares_disponibles` como columna con CHECK `0..totales` | Derivarla de préstamos: complica el SQL que genera el modelo | R-7.6 |
| D-DB7 | `ON DELETE RESTRICT` en dominio, `CASCADE` en el vínculo de la puente hacia `libros` y en chunks (hacia `autores` la puente es RESTRICT) | `CASCADE` general: borraría historial de préstamos | R-7.7 |
| D-DB8 | `vector(768)` + HNSW coseno | Más dimensiones: más almacenamiento sin ganancia con el corpus de 6 documentos y 44 fragmentos (medido con `rag/ingest.py --dry-run`) | R-7.8, D87 |
| D-DB9 | El SQL tool no accede a `documentos*` (la exclusión la hace la whitelist de la herramienta SQL, D21; el `rag_tool` lee los chunks con el mismo rol `agent_ro`, D63) | Acceso total: el SQL tool no necesita chunks ni embeddings | R-7.9 |
| D-DB10 | Multas, plazos y límites **no** son tablas: viven en el reglamento | Tabla de políticas: la consulta mixta se resolvería solo con SQL y el RAG quedaría sin función | R-9.2, R-8.4 |

### Por qué las reglas de negocio no están en la base (D-DB10)

"Juan Pérez tiene un libro prestado hace 20 días, ¿le corresponde multa?" solo se contesta combinando
SQL (fecha del préstamo y tipo de socio) con RAG (plazo y multa). Si las reglas estuvieran en tablas,
los casos híbridos del golden set no ejercitarían el RAG. Es una decisión de diseño del dominio,
no una omisión.

### Reglas del reglamento (fuente de verdad)

| Regla | Alumno | Docente |
|---|---|---|
| Plazo de préstamo | 14 días | 30 días |
| Máximo de libros simultáneos | 3 | 5 |
| Renovaciones | 1 vez, +7 días | 1 vez, +14 días |
| Multa por atraso | $200 por día | $200 por día |

## Cómo se aplicó (orden y evidencia)

1. DDL revisado y aprobado antes de crear tablas.
2. Aplicado sobre una base vacía: 9 tablas, 1 vista, extensión `vector` habilitada. Se comprobó que
   los CHECK/UNIQUE rechazan datos inválidos, que `vector(768)` rechaza otras dimensiones y que
   `agent_ro` solo lee tablas de negocio.
3. Seed validado sobre la base local. `db/seed.sql`, sobre una base vacía, deja
   70 libros, 57 autores, 28 editoriales, 18 categorías, 95 vínculos libro-autor, 20 socios y 28 préstamos
   (18 devueltos, 5 activos, 5 vencidos), contados sobre el archivo.
4. PDFs generados con `rag/build_pdfs.py` desde los `.md` y versionados en `rag/documents/pdf/`
   (6 archivos); `rag/ingest.py` los carga en la base.

## Risks / Trade-offs

- **Un solo DDL**: `db/schema.sql` es la única definición del esquema (D65); sus decisiones de
  normalización están anotadas en la cabecera, sobre todo `vector_cosine_ops` en el HNSW.
- **El seed envejece**: las fechas son relativas a `CURRENT_DATE` al cargar; los atrasos crecen día a día.
  Los tests no deben aseverar días de atraso literales.
- **Seed no idempotente**: aborta si ya hay datos. Reaplicarlo exige truncar.
- **Rol de solo lectura**: `agent_ro` se crea con login en la base local (`db/init/10-roles.sh`) y sus
  permisos se conceden en `db/post_restore.sql`.
- **Reseñas y catálogo**: los 10 títulos reseñados (Cien años de soledad, Clean Code, los 5 de Tolkien y los 3 de la saga Empyrean) deben existir en el catálogo del seed (R-8.8).
