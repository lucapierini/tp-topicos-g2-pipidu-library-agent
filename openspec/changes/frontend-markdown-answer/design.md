# Design

## Context

`AnswerView` pone `result.answer` en un `BubbleContent` con `whitespace-pre-wrap`. El modelo responde en
Markdown, así que se ven `*` y `**` literales. shadcn/ui no trae un componente de Markdown: las guías del skill
piden componer con los componentes existentes (`Table`, `Separator`, `Badge`), tokens semánticos (`text-muted-foreground`, `bg-muted`),
`gap-*` en vez de `space-y-*` y `size-*`, y nada de HTML o estilos a mano que dupliquen un componente. Ya están
instalados `Table` y `Separator`, y los íconos son de `hugeicons`. `web/` usa React 19, Vite y Tailwind v4 sin `@tailwindcss/typography`.

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
   `react-markdown`: `table`/`thead`/`tbody`/`tr`/`th`/`td` → `Table*` de shadcn; `ul`/`ol` con `flex flex-col gap-1` y `list-inside`/`pl-5`;
   `p` con `leading-relaxed`; `code` en línea con `bg-muted`; `pre` con el estilo de la evidencia SQL (`rounded-xl bg-muted p-3 font-mono text-xs`);
   `blockquote` con borde `border-l-2` y `text-muted-foreground`; `a` con `target="_blank" rel="noreferrer noopener"`; `hr` → `Separator`;
   `h1`–`h4` con tamaños acotados al ancho de la burbuja. Solo clases de layout y tokens semánticos, sin colores crudos.
3. **Se usa dentro de la `Bubble` actual** (variante `muted`), sin `whitespace-pre-wrap` y con `max-w-full` en la burbuja si hay tabla, para que
   la tabla haga scroll horizontal dentro de `Table` en vez de desbordar. Si sigue la regla de chat del skill, la burbuja no se reimplementa.
4. **Solo `answer_kind: answer`.** `no_coverage` y `error` quedan en `Alert` como texto, y la evidencia no se toca (R-8.4).
5. **Spec como delta de `interfaz-web`.** No hay spec principal todavía (los changes no están archivados): se agrega R-8.11 y se
   archiva `frontend-web-vite` primero. Se registra en `TP/CHANGELOG.md` como D94 (D93 ya es la SPA).

## Risks / Trade-offs

- **Dependencias nuevas** (~40 KB gzip) → aceptable para una SPA local; versiones fijadas por `package-lock.json`.
- **Texto plano con saltos simples**: Markdown junta líneas contiguas en un párrafo → se usa `remark-breaks` solo si la verificación
  con respuestas reales lo muestra necesario; se decide en la tarea 3.1.
- **XSS**: sin `rehype-raw`, el HTML crudo se escapa; se cubre con un test (R-8.11) y los enlaces `javascript:` los neutraliza `react-markdown` por defecto.
- **Respuestas largas** (como la agrupación por editorial) → la lista crece dentro de la burbuja; el scroll lo da `MessageScroller`.
