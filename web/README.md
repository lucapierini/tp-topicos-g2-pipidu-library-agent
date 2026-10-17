# web — interfaz del agente de biblioteca

SPA de consulta (Vite + React 19 + TypeScript + shadcn/ui, preset `base-luma`). Es un cliente de la API del agente
(`POST /ask`, SSE); no accede al agente ni a la base. La descripción funcional, la estructura y el arranque con Docker están
en el [README de la raíz](../README.md#interfaz-web-d93). Requisitos y criterios: capability `interfaz-web` en
[`openspec/changes/frontend-web-vite`](../openspec/changes/frontend-web-vite/) y
[`frontend-markdown-answer`](../openspec/changes/frontend-markdown-answer/).

## Desarrollo

Requisitos: Node 24 (es la versión de la imagen `docker/Dockerfile.web`; `package.json` no declara `engines`) y la API
local en `http://127.0.0.1:8000` (`uvicorn api.app:app --port 8000`, ver el README de la raíz).

```bash
npm install
npm run dev          # http://localhost:5173; /api se reenvía a la API (VITE_API_TARGET lo cambia)
npm test             # vitest, una corrida (npm run test:watch: modo interactivo)
npm run lint         # eslint
npm run typecheck    # tsc --noEmit
npm run build        # tsc -b + vite build, deja los estáticos en dist/
npm run preview      # sirve dist/ localmente
npm run format       # prettier sobre los .ts/.tsx
```

`VITE_API_TARGET` es una variable del proceso de Vite (no del `.env` de la raíz): por ejemplo
`VITE_API_TARGET=http://127.0.0.1:8080 npm run dev` para apuntar a la API de `docker compose`.

## Componentes de shadcn/ui

```bash
npx shadcn@latest add <componente>   # se agregan en src/components/ui
```

Convenciones: tokens semánticos (`text-muted-foreground`), `gap-*` en lugar de `space-*`, íconos de Hugeicons y composición de
las primitivas de chat (`MessageScroller`, `Message`, `Bubble`).
