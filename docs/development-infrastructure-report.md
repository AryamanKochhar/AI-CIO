# Development Infrastructure Report — AI-CIO

> Updated after Docker dependency architecture fix (August 2026)

## Root cause of web startup failure

| Issue | Effect |
|-------|--------|
| Runtime `pnpm install` in container | 40–300s linking into Docker volumes on every start |
| Bind-mounting full `./apps/web` | Host macOS `node_modules` leaked into Linux container |
| Alpine + wrong SWC variant | Next.js tried to download `@next/swc-linux-arm64-gnu` at runtime |
| Named `web_node_modules` volume | Empty volume hid image dependencies |

## Fix applied

1. **`.npmrc`** — explicit `node-linker=hoisted` (no runtime pnpm config changes)
2. **`apps/web/Dockerfile.dev`** — layer-cached `pnpm install`, SWC verification at build time, `node:20-bookworm-slim` (glibc / `@next/swc-linux-arm64-gnu`)
3. **`docker-compose.yml`** — build `api` + `web` images; mount only source paths (`src/`, config files, `packages/`) — never `node_modules`
4. **`make dev-build`** — rebuild images when dependencies change
5. **`make dev-up`** — starts pre-built containers in ~17s (no install step)

## Final Compose services

| Service | Image | Purpose |
|---------|-------|---------|
| `postgres` | `postgres:15-alpine` | One canonical PostgreSQL |
| `migrate` | `ai-cio-api:local` | One-shot Alembic |
| `api` | `ai-cio-api:local` | FastAPI |
| `web` | `ai-cio-web:local` | Next.js dev server |

## Developer flow

```bash
make install      # host Python + pnpm (for tests, MCP, IDE)
make dev-build    # first run or after dep changes
make dev-up       # start stack → http://localhost:3000
```

## Verification (August 2026)

- `make dev-up` — **17s** to ready (postgres + migrate + api + web)
- Web ready in **~1.5s** inside container (no SWC download)
- `docker compose ps` — exactly one `postgres` service
- `pytest -q` — **56/56 passed**
- `pnpm typecheck` — pass
- `pnpm build` — pass

## Deprecated

- Runtime install scripts (`scripts/docker-*.sh`)
- Host fallback scripts (`scripts/dev-up-host.sh`)
- Bind-mounting host `node_modules` into containers
