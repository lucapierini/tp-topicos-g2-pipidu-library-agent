# Design

## Context

`AnswerView` muestra `result.answer` en un `BubbleContent` de la `Bubble`; el Markdown se interpreta con
`react-markdown` para que los marcadores `*` y `**` no se vean como texto. shadcn/ui no trae un componente de
Markdown: las guías del skill
piden componer con los componentes existentes (`Table`, `Separator`, `Badge`), tokens semánticos (`text-muted-foreground`, `bg-muted`),
`gap-*` en vez de `space-y-*` y `size-*`, y nada de HTML o estilos a mano que dupliquen un componente. `Table`
y `Separator` están instalados, y los íconos son de `hugeicons`. `web/` usa React 19, Vite y Tailwind v4 sin `@tailwindcss/typography`.

## Goals / Non-Goals

**Goals:**
- Que `answer` se vea formateado (listas, énfasis, tablas, código, citas, enlaces) en claro y oscuro.
- Reutilizar `Table` y los tokens del tema; sin HTML inyectado.

**Non-Goals:**
- Streaming token a token de la respuesta (la API entrega `answer` completo en `result`).
- Cambiar el agente para que responda en otro formato, o la API.
- Resaltado de sintaxis, matemática o diagramas.

## Decisions

1. **`react-markdown` + `remark-gfm`.** Renderiza a elementos de React (no a HTML en string), y no interpreta HTML
   crudo sin `rehype-raw`, que no se agrega. Alternativas: `marked` + `dangerouslySetInnerHTML` (requiere sanitizar,
   descartada) y escribir un parser propio (descartada).
2. **Un componente `Markdown` propio en `web/src/components/ask/markdown.tsx`** con el mapa `components` de
   `react-markdown`: `table`/`thead`/`tbody`/`tr`/`th`/`td` → `Table*` de shadcn; `ul`/`ol` con `flex flex-col gap-1` y `list-disc`/`list-decimal` con `pl-5`;
   `p` con `leading-relaxed`; `code` en línea con `bg-muted`; `pre` con el estilo de la evidencia SQL (`rounded-xl bg-muted p-3 font-mono text-xs`);
   `blockquote` con borde `border-l-2` y `text-muted-foreground`; `a` con `target="_blank" rel="noreferrer noopener"`; `hr` → `Separator`;
   `h1`–`h4` con tamaños acotados al ancho de la burbuja. Solo clases de layout y tokens semánticos, sin colores crudos.
3. **Se usa dentro de la `Bubble` actual** (variante `muted`), sin `whitespace-pre-wrap` y con `max-w-full` en la burbuja si hay tabla, para que
   la tabla haga scroll horizontal dentro de `Table` en vez de desbordar. Si sigue la regla de chat del skill, la burbuja no se reimplementa.
4. **Solo `answer_kind: answer`.** `no_coverage` y `error` quedan en `Alert` como texto, y la evidencia no se toca (R-8.4).
5. **Spec como delta de `interfaz-web`.** La capability no tiene spec principal: `frontend-web-vite` y este change
   viven como deltas, y `frontend-web-vite` se archiva primero. Se agrega R-8.11 y se registra en
   `TP/CHANGELOG.md` como D95 (D93 fija la SPA).

## Risks / Trade-offs

- **Dependencias nuevas** → aceptable para una SPA local; las versiones las fija `package-lock.json`.
- **Texto plano con saltos simples**: Markdown junta líneas contiguas en un párrafo, así que
  `remark-breaks` (D95) conserva los saltos de línea del `answer`; el test de la tarea 3.1 lo verifica.
- **XSS**: sin `rehype-raw`, el HTML crudo se escapa; se cubre con un test (R-8.11) y los enlaces `javascript:` los neutraliza `react-markdown` por defecto.
- **Respuestas largas** (como la agrupación por editorial) → la lista crece dentro de la burbuja; el scroll lo da `MessageScroller`.
