#!/bin/sh
set -eu
corepack enable
corepack prepare pnpm@9.15.0 --activate
export PNPM_HOME="/pnpm"
export PATH="$PNPM_HOME:$PATH"
export CI=true
pnpm config set store-dir /pnpm/store
pnpm config set node-linker hoisted
pnpm install --frozen-lockfile
exec pnpm --filter @ai-cio/web exec next dev --hostname 0.0.0.0 --port 3000
