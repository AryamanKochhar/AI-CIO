# Local Development — AI-CIO

## Canonical commands

```bash
make install
make dev-build   # first run, or after dependency/Dockerfile changes
make dev-up
```

Open http://localhost:3100

## Docker architecture

One compose project (`ai-cio`) with services: `postgres`, `migrate`, `api`, `web`.

- **Dependencies are baked into Docker images** at build time (`make dev-build`).
- **`make dev-up` does not run pnpm install** — it starts pre-built containers.
- **Host `node_modules` are never mounted** into the Linux web container.
- **Linux ARM64 SWC** (`@next/swc-linux-arm64-gnu`) is verified during the web image build.

## pnpm strategy

Repository `.npmrc` sets `node-linker=hoisted` for Docker-compatible dependency layout.

Host development (`pnpm install` on macOS) uses the same config. Docker web image installs Linux dependencies independently during `make dev-build`.

## When to rebuild

Run `make dev-build` after changing:

- `package.json` / `pnpm-lock.yaml`
- `apps/web/Dockerfile.dev` / `apps/api/Dockerfile`
- workspace package dependencies

## Deprecated scripts

These are obsolete; use `make dev-up` instead:

- `scripts/docker-web.sh` (runtime pnpm install)
- `scripts/docker-api.sh` (runtime pip install)
- `scripts/dev-up-host.sh` / `scripts/dev-up-web-host.sh`

## Full guide

See [docs/development-guide.md](../docs/development-guide.md).
