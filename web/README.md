# web — interfaz del agente de biblioteca

SPA de consulta (Vite + React 19 + TypeScript + shadcn/ui, preset `base-luma`). Es un cliente de la API del agente
(`POST /ask`, SSE); no accede al agente ni a la base. La descripción funcional, la estructura y el arranque con Docker están
en el [README de la raíz](../README.md#interfaz-web-d93). Requisitos y criterios: capability `interfaz-web` en
[`openspec/changes/frontend-web-vite`](../openspec/changes/frontend-web-vite/) y
[`frontend-markdown-answer`](../openspec/changes/frontend-markdown-answer/).

## Desarrollo

Con la API local en `http://127.0.0.1:8000` (`uvicorn api.app:app --port 8000`):

```bash
npm install
npm run dev      # http://localhost:5173; /api se reenvía a la API (VITE_API_TARGET lo cambia)
npm test         # vitest
npm run lint
npm run build
```

## Componentes de shadcn/ui

```bash
npx shadcn@latest add <componente>   # se agregan en src/components/ui
```

Convenciones: tokens semánticos (`text-muted-foreground`), `gap-*` en lugar de `space-*`, íconos de Hugeicons y composición de
las primitivas de chat (`MessageScroller`, `Message`, `Bubble`).
