# Artefactos SDD

Carpeta de entrega de los artefactos del ciclo **Requirement → Spec → Plan → Tasks → Implementation → Validation**.

## Archivo canónico por etapa del ciclo

Un artefacto vive en **un solo lugar**:

| Etapa del ciclo | Archivo canónico |
|---|---|
| Principios / gobernanza | `TP/00-constitucion.md` |
| Contexto y alcance funcional | `TP/01-especificacion-funcional.md` |
| Requirement / Spec (WHAT) | `openspec/changes/agente-y-tools/specs/<capacidad>/spec.md` — acá viven los IDs `R-x.y` |
| Plan (HOW) | `TP/02-especificacion-tecnica.md` (arquitectura y contratos) + `design.md` (decisiones indexadas) |
| Decisiones | `TP/CHANGELOG.md` |
| Tasks | `openspec/changes/agente-y-tools/tasks.md` |
| Validation | `TP/05-validacion.md` |
| Enunciado original | `TP/Enunciado TP - 2026.pdf` |

`openspec/` es la **fuente de verdad operativa**: ahí se valida, se actualiza y se archiva cada change.
`TP/` es la **versión legible para la entrega**: documentos de lectura continua, no requisitos formales.
En `TP/` no hay copia de specs ni de tareas. Cuando un change se archiva (`openspec archive <change>`),
sus requisitos se consolidan en `openspec/specs/`, que pasa a describir el sistema ya construido.

Si un requisito cambia, se cambia en `openspec/` y la decisión se registra en `CHANGELOG.md`; no se
edita una copia en paralelo.

## Capabilities especificadas

1. `entrada-de-consulta`
2. `seleccion-de-fuente`
3. `sql-query-tool`
4. `rag-retrieval-tool`
5. `composicion-de-respuesta`
6. `trazabilidad-de-ejecucion`

Change `base-de-datos-neon` (justificación del esquema, seed y documentos fuente del RAG):

7. `esquema-de-base-de-datos`
8. `datos-de-prueba`
9. `documentos-fuente-rag`

Los PDFs documentales los genera el integrante responsable de RAG y base de datos, y deben cubrir el
contenido que sostienen los casos G6–G9 y R1–R3 del golden set.

## Comandos

```bash
openspec list --specs          # inventario de capacidades
openspec list                  # changes en curso
openspec validate --strict     # valida requisitos y escenarios
openspec show agente-y-tools   # ver el change
openspec context               # contexto del proyecto
```

## Formato

Para el change de base de datos: `openspec show base-de-datos-neon`.

Cada requisito usa `### Requirement: R-x.y — <nombre>` y al menos un `#### Scenario:` con
`- **WHEN**` / `- **THEN**`. El ID `R-x.y` coincide con `05-validacion.md`, de modo que cada escenario
es un caso de test identificable.
