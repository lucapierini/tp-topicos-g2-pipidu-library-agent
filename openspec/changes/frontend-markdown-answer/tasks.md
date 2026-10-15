# Tasks

## 1. Dependencias y componente

- [x] 1.1 Revisar con `npx shadcn@latest docs table separator` y la regla `rules/chat.md` del skill cómo se componen; agregar `react-markdown` y `remark-gfm` a `web/` con `npm install`; verificar que `npm run build` termina sin errores (R-8.11)
- [x] 1.2 Crear `web/src/components/ask/markdown.tsx` con el mapa `components` de la decisión 2 (tablas con `Table*`, listas, énfasis, código, citas, `hr` con `Separator`, enlaces con `target="_blank" rel="noreferrer noopener"`), sin `rehype-raw`, sin `space-y-*` ni colores crudos; verificar con `npm run lint` (R-8.11)

## 2. Integración

- [x] 2.1 Usar `Markdown` en `AnswerView` para `answer_kind` `answer` en lugar de `whitespace-pre-wrap`; dejar `no_coverage` y `error` y `EvidenceView` sin cambios; verificar con los tests existentes de `answer-view.test.tsx` (R-8.3, R-8.4, R-8.11)
- [ ] 2.2 Ajustar la burbuja para que una tabla ancha haga scroll dentro de `Table` y no desborde; verificar en el navegador con la consulta "libros agrupados por editorial" en claro y oscuro (R-8.11)

## 3. Verificación

- [x] 3.1 Agregar tests de `vitest` en `answer-view.test.tsx` de los cinco escenarios de R-8.11: lista con negritas sin `*` visibles, tabla GFM con `Table`, HTML (`<script>`, `<img onerror>`) sin interpretar, texto plano con saltos de línea intacto, y `no_coverage`/`error` con `Alert`; si el texto plano pierde sus saltos, sumar `remark-breaks` (R-8.11, R-8.7)
- [ ] 3.2 Probar de punta a punta con Docker las tres consultas reportadas ("libros con reseña", "reseña de Tolkien", "libros agrupados por editorial") y confirmar que no queda ningún `*` ni `**` visible; verificar con el navegador (R-8.11)

## 4. Documentación y specs

- [x] 4.1 Registrar D95 en `TP/CHANGELOG.md` (respuesta como Markdown con `react-markdown` + `remark-gfm`, sin HTML crudo) y citar R-8.11 en `README.md` (sección Interfaz web) y en `TP/05-validacion.md` si enumera R-8.x; verificar con `openspec validate frontend-markdown-answer --strict`
- [x] 4.2 Ejecutar `npm test`, `npm run lint` y `npm run build` en `web/`; verificar que todo pasa

## Workflow follow-up

- Archivar `frontend-web-vite` y después este change cuando se revisen con el equipo.
