# Proposal

## Why

El agente responde en Markdown (listas con `*`, **negritas**, *cursivas*, notas, a veces tablas), pero la SPA
mostraba `answer` como texto plano con `whitespace-pre-wrap` (`AnswerView`). La persona ve los asteriscos
literales y las listas sin formato, como en las consultas "libros con reseña", "reseña de Tolkien" y "libros
agrupados por editorial". La interfaz es el criterio de promoción "Interfaz gráfica" (D93): una respuesta
ilegible lo debilita.

## What Changes

- La respuesta `answer_kind: answer` se renderiza como Markdown (CommonMark + GFM: listas, énfasis, tablas,
  código, enlaces, citas), con los estilos de shadcn/ui y los tokens semánticos del proyecto.
- Las tablas Markdown usan el componente `Table` ya instalado; no se escribe HTML a mano ni se usa
  `dangerouslySetInnerHTML`. El HTML crudo dentro de la respuesta no se interpreta.
- `no_coverage` y `error` mantienen su presentación actual (`Alert`, R-8.3); no pasan por el renderizador.
- La evidencia (SQL, filas, fragmentos) sigue mostrándose tal como llega (R-8.4); no se renderiza como Markdown.
- Sin cambios en la API ni en el agente: `answer` sigue siendo texto, el cliente cambia solo cómo lo muestra.

## Capabilities

### New Capabilities

### Modified Capabilities
- `interfaz-web`: agrega R-8.11, presentación de la respuesta como Markdown. Hoy esta capability solo existe como
  delta en el change `frontend-web-vite` (no hay spec principal): este delta se aplica sobre él y requiere archivarlo antes.

## Impact

- `web/src/components/ask/answer-view.tsx` y un componente nuevo `web/src/components/ask/markdown.tsx`.
- Dependencias de `web/`: `react-markdown`, `remark-gfm` y `remark-breaks`.
- Tests de `web/` (`answer-view.test.tsx`); `README.md` y `TP/CHANGELOG.md` (decisión nueva) y `TP/05-validacion.md` si cita R-8.3.
- Sin cambios en `api/`, `agent/`, `db/` ni en Docker (la imagen `web` solo suma código estático).
