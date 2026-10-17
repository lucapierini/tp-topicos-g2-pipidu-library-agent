# Artefactos SDD

Artefactos del ciclo **Requirement → Spec → Plan → Tasks → Implementation → Validation** con el que se desarrolló el agente.

## Archivo canónico por etapa del ciclo

Un artefacto vive en **un solo lugar**:

| Etapa del ciclo | Archivo canónico |
|---|---|
| Principios / gobernanza | `TP/00-constitucion.md` |
| Contexto y alcance funcional | `TP/01-especificacion-funcional.md` |
| Requirement / Spec (WHAT) | `openspec/changes/<change>/specs/<capacidad>/spec.md` — acá viven los IDs `R-x.y` |
| Plan (HOW) | `TP/02-especificacion-tecnica.md` (arquitectura y contratos) + `design.md` (decisiones indexadas) |
| Decisiones | `TP/CHANGELOG.md` |
| Tasks | `openspec/changes/agente-y-tools/tasks.md` |
| Validation | `TP/05-validacion.md` |
| Evidencia de corridas medidas | `TP/evidencia/*.json` |

`openspec/` es la **fuente de verdad operativa**: ahí se valida, se actualiza y se archiva cada change.
`TP/` es la **versión legible**: documentos de lectura continua, no requisitos formales.
En `TP/` no hay copia de specs ni de tareas. Cuando un change se archiva (`openspec archive <change>`),
sus requisitos se consolidan en `openspec/specs/`, que pasa a describir el sistema ya construido.

Si un requisito cambia, se cambia en `openspec/` y la decisión se registra en `CHANGELOG.md`; no se
edita una copia en paralelo.

## Capabilities especificadas

Change `agente-y-tools` (agente y herramientas; IDs `R-1.x` a `R-7.x`):

1. `entrada-de-consulta`
2. `seleccion-de-fuente`
3. `sql-query-tool`
4. `rag-retrieval-tool`
5. `composicion-de-respuesta`
6. `trazabilidad-de-ejecucion`
7. `consulta-por-api`

Change `base-de-datos-neon` (justificación del esquema, seed y documentos fuente del RAG):

- `esquema-de-base-de-datos` (`R-7.1` a `R-7.10`)
- `datos-de-prueba` (`R-8.1`, `R-8.2` y `R-8.4` a `R-8.8`)
- `documentos-fuente-rag` (`R-9.1` a `R-9.7`)

Change `calibracion-umbral-rag` (calibración y re-ranking del RAG): amplía `rag-retrieval-tool` con `R-4.9` a `R-4.11`.

Changes `frontend-web-vite` y `frontend-markdown-answer` (interfaz web): capability `interfaz-web`
(`R-8.1` a `R-8.11`).

**Los prefijos `R-7.x` y `R-8.x` se repiten entre capabilities** (los IDs no se renumeran): se citan junto con
su capability cuando hay ambigüedad (por ejemplo, «R-7.8 de `consulta-por-api`» es CORS y «R-7.8 de
`esquema-de-base-de-datos`» es el vector de 768 dimensiones).

Los PDF documentales (`rag/documents/pdf/`) cubren el contenido que sostienen los casos G6–G9 y R1–R3 del golden set.

## Comandos

```bash
openspec list --specs          # inventario de capacidades
openspec list                  # changes en curso
openspec validate --all --strict   # valida requisitos y escenarios de todos los changes
openspec show agente-y-tools   # ver un change (también `base-de-datos-neon`, `calibracion-umbral-rag`, `frontend-web-vite` y `frontend-markdown-answer`)
openspec context               # contexto del proyecto
```

## Formato

Cada requisito usa `### Requirement: R-x.y — <nombre>` y al menos un `#### Scenario:` con
`- **WHEN**` / `- **THEN**`. El ID `R-x.y` coincide con `05-validacion.md`, de modo que cada escenario
es un caso de test identificable.
