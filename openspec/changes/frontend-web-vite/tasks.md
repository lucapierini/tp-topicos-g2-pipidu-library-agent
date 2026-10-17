# Tasks

## 1. Scaffolding de `web/`

- [x] 1.1 Ejecutar `npx shadcn@latest init --preset b1Vq8M9Q --template vite` dentro de `web/`; verificar que existen `web/package.json`, `web/components.json` (con `iconLibrary` `hugeicons`) y que `npm run build` termina sin errores (R-8.8)
- [x] 1.2 Agregar `vitest` y un script `npm test`; verificar que `npm test` corre con 0 tests fallando
- [x] 1.3 Agregar a `.dockerignore` y `.gitignore` `web/node_modules` y `web/dist`; verificar con `git status` que no aparecen en los cambios (R-8.9)

## 2. Cliente de la API

- [x] 2.1 Implementar `web/src/lib/ask-stream.ts`: `fetch` POST a `/api/ask`, parser SSE sobre `ReadableStream` (eventos partidos entre chunks, UTF-8), tipos de los eventos y de `result`; verificar con tests de `vitest` que cubren chunk partido, `result` con fechas/decimales como texto y `error` (R-8.2, R-8.3)
- [x] 2.2 Implementar el hook `useAsk` con los estados `idle/running/done/failed` (cancelar vuelve a `idle`) y
  `AbortController`; verificar con tests que `sources` solo existe en `done`, que cancelar vuelve a `idle` sin
  respuesta y que un flujo sin `result` termina en `failed` (R-8.2, R-8.5, R-8.6)
- [x] 2.3 Mapear fallas: API inalcanzable, 422 y corte antes de `result` a mensajes distintos; verificar con tests de `vitest` de cada caso (R-8.6)
- [x] 2.4 Configurar el proxy de `/api` en `vite.config.ts` hacia `http://127.0.0.1:8000`; verificar que `npm run dev` con la API local responde `/api/health` sin CORS

## 3. Interfaz

- [x] 3.1 Consultar `npx shadcn@latest docs` e instalar con `npx shadcn@latest add` los componentes necesarios (`button`, `field`, `textarea`, `card`, `badge`, `alert`, `table`, `collapsible`, `spinner`, `skeleton`, `empty`, `separator` y las primitivas de chat); verificar que existen en `web/src/components/ui/` y revisar cada archivo agregado según las reglas del skill
- [x] 3.2 Pantalla de consulta: `FieldGroup`/`Field` con el texto, botón enviar deshabilitado si está vacío o en curso, estado vacío con `Empty`; verificar con un test de componente que no llama a la API con texto vacío (R-8.1)
- [x] 3.3 Panel de progreso: clasificación, herramienta invocada, pasos y segundos de espera por `heartbeat`, con la
  clase `shimmer` en lugar de `Spinner`; verificar con un test de componente que no muestra fuentes antes de `result`
  (R-8.2)
- [x] 3.4 Vista de respuesta: texto, `Badge` por fuente y variante visual distinta para `no_coverage` y `error`; verificar con tests de componente de los tres `answer_kind` (R-8.3)
- [x] 3.5 Vista de evidencia: SQL y filas en `Table`, fragmentos con `document` y `location`, sin sección si no hay evidencia; verificar con tests de componente de cada caso (R-8.4)
- [x] 3.6 Botón cancelar y manejo de errores con `Alert` y reintento; verificar con test de componente que cancelar no deja respuesta parcial (R-8.5, R-8.6)
- [x] 3.7 Confirmar que consultas en castellano e inglés se envían y muestran sin modificarse; verificar con un test del cliente (R-8.7)
- [x] 3.8 Indicar la espera con `shimmer` en lugar de spinner y conservar el historial de la sesión al enviar una consulta nueva; verificar con tests del reducer, del panel de progreso y de `App` (R-8.2, R-8.10)

## 4. Docker

- [x] 4.1 Crear `docker/Dockerfile.web` (build con Node 24 y servido con `nginx:1.29-alpine`) y `docker/nginx.conf` (SPA con fallback a `index.html`, `/api/` a `http://api:8080/` con `proxy_buffering off`, `proxy_http_version 1.1` y `proxy_read_timeout` de 10 minutos); verificar con `docker build -f docker/Dockerfile.web -t pipidu-web .` (R-8.8)
- [x] 4.2 Agregar `api` y `web` a `docker-compose.yml` con `depends_on` por salud, `POSTGRES_HOST: db`, `POSTGRES_PORT: 5432`, healthchecks y puertos en `127.0.0.1`; verificar con `docker compose config` y `docker compose up -d --wait` con los tres servicios sanos (R-8.8)
- [x] 4.4 Verificar que la base no está sana → la API no inicia (`docker compose up` con la base detenida) y que la imagen `web` no contiene `.env` ni claves (`docker run --rm pipidu-web sh -c 'grep -r GEMINI /usr/share/nginx/html || true'` sin salida) (R-8.8, R-8.9)

## 5. Documentación y specs

- [x] 5.1 Reformular R-7.0 en `consulta-por-api` y actualizar las docs que excluían la interfaz, registrando D93 en `TP/CHANGELOG.md`; verificado con `openspec validate --strict` en ambos changes
- [x] 5.2 Actualizar `README.md` (arranque con `docker compose up -d --wait`, puertos, `npm run dev`, criterio "Interfaz gráfica") y `.env.example` (`WEB_PORT`, `API_PORT`, `API_ALLOWED_ORIGINS` para desarrollo); verificar siguiendo el README desde un checkout limpio
  *Verificado el 2026-10-16 siguiendo el README desde un clon limpio: `docker compose up -d --build --wait` dejó `db`, `api` y `web` sanos, `/health` respondió `ok`, las tres consultas del README respondieron por `/api/ask` de la web y el camino de desarrollo (`uvicorn` en 8000, `npm run dev` con el proxy `/api`, 46 tests de vitest) funcionó.*
- [x] 5.3 Ejecutar `python -m pytest -q`, `python -m ruff check .`, `npm test` y `npm run build` en `web/`; verificar que todo pasa
