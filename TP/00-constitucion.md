# Constitución — Pipidu Library Agent

> Principios que gobiernan todo el desarrollo. Son la "constitución" del proyecto: los specs y
> las tareas no pueden contradecirla. No se modifican durante la implementación; cualquier cambio
> requiere acuerdo del grupo y queda registrado en `CHANGELOG.md`.
>
> **Versión:** 1.0 · **Fecha:** 2026-10-08

---

## Art. 1 — Spec antes de código

Ningún componente del agente se implementa sin un requisito escrito y trazable. Cada archivo de
código debe poder vincularse a un requisito (`R-x.y`) de `03-especificaciones-por-capacidad.md`.

**Regla:** si una línea de código no satisface un requisito existente, o el requisito no existe,
primero se escribe el requisito.

## Art. 2 — Separación WHAT / HOW

- La **spec** describe comportamiento observable, alcance, reglas y aceptación. No menciona librerías.
- El **plan** describe arquitectura, componentes, interfaces y estrategia de testing.
- Si una decisión técnica aparece en la spec, está mal ubicada.

## Art. 3 — Read-only por diseño

El agente **nunca** escribe en la base de datos. Defensa en profundidad en tres capas:

1. Prompt de sistema restringido a `SELECT`.
2. Validación estática en código (whitelist de tablas/columnas, rechazo de DML/DDL, `;`, comentarios, `COPY`, `CALL`).
3. Rol `readonly` a nivel de PostgreSQL + timeout de ejecución.

Si una de las tres capas se elimina, el Art. 3 se considera violado.

## Art. 4 — Provenencia obligatoria de la respuesta

Toda respuesta del agente declara la fuente utilizada (`SQL`, `RAG`, `SQL+RAG` o `ninguna`).
El agente **no afirma nada que no esté soportado por una fuente consultada**. Si ninguna fuente
responde, declara explícitamente que no tiene información suficiente.

## Art. 5 — Trazabilidad de ejecución

Cada consulta se registra en la tabla `agent_runs` (pregunta, clasificación, tools invocadas,
SQL generado, chunks recuperados, latencia). Esto no es un extra: es la evidencia que el informe
técnico exige.

## Art. 6 — Testeabilidad como definición de "done"

Una capacidad no está terminada sin su test. No se acepta un cambio que rompa un caso del
**golden set** (`05-validacion.md`).

## Art. 7 — Determinismo acotado

El LLM es no determinista, pero el sistema lo acota: temperatura fija, top-k fijo, umbral de
similitud fijo, y un golden set de preguntas con respuesta esperada. Cualquier cambio en un
parámetro de configuración debe revalidarse contra el golden set.

## Art. 8 — Reproducibilidad

Cualquier evaluador debe poder: `git clone` → `docker compose up` → `python -m rag.ingest` →
`streamlit run ui/app.py`. Si algo requiere una acción manual no documentada en el README, el
criterio de aprobación está en riesgo.

## Art. 9 — Sin secretos en el repositorio

API keys y credenciales vía variables de entorno (`.env` en `.gitignore`) o GCP Secret Manager.
`.env.example` sin valores reales.

## Art. 10 — Disciplina de alcance

Lo que no está en la spec no se implementa. Las exclusiones de `01-especificacion-funcional.md` §5.5 son
vinculantes. Un feature no pedido se trata como un cambio de spec, no como una mejora.

## Art. 11 — Acceso uniforme a la información del dominio

No hay política de privacidad ni roles de acceso diferenciados: todos los usuarios del agente acceden a
toda la información del dominio, salvo que la consigna del trabajo práctico detalle lo contrario (la
consigna 2026 no lo detalla).

La whitelist de tablas y columnas es un control de **alcance y de inyección** (R-3.4), no un control de
privacidad. Si la consigna introdujera un requisito de privacidad, se trata como un cambio de spec
(Art. 10), no como una mejora.

---

## Convenciones

| Tema | Convención |
|---|---|
| Python | 3.11+, type hints en toda función pública, `ruff` para lint |
| IDs de requisito | `R-<capacidad>.<n>` (ej. `R-3.2`) |
| IDs de tarea | `T<n>` en `04-tareas.md` |
| Formato de aceptación | GIVEN / WHEN / THEN |
| Commits | `T<n>: <resumen>` (ej. `T3: sql_query_tool + validación estática`) |
| Estructura de specs | Sintaxis OpenSpec-compatible (`### Requirement:` + `#### Scenario:`), para poder correr `openspec validate` |

---

## Herramienta SDD adoptada

**OpenSpec** (`@fission-ai/openspec`) — ver comparativa en la respuesta del chat.
Motivo: los artefactos son Markdown plano versionado en el repo, que es exactamente lo que el TP
pide adjuntar; la ceremonia es baja y el formato de requisitos es verificable con
`openspec validate`. Los archivos de esta carpeta ya respetan ese formato, por lo que adoptarlo
no exige reescribir nada.
