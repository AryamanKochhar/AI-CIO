# Target Architecture — AI-CIO

> Status: **IMPLEMENTED** (current target as of August 2026 restructure).

## Monorepo layout

```text
apps/web          → Next.js (canonical UI)
apps/api          → Python API documentation entry
ai_cio/           → Python domain package
packages/ui       → Design system
packages/contracts→ Shared TS types
packages/utils    → Formatting helpers
instruments/      → Psychometric instrument JSON
tests/            → pytest
docs/             → Documentation
skills/           → Agent engineering skills
```

## Dependency direction

```text
Next.js → FastAPI → Domain (ai_cio/services) → PostgreSQL
MCP → Domain → PostgreSQL
```

Domain does not depend on UI, API routing, or MCP.

## PLANNED (not implemented)

- `ai_cio/domain/intelligence`
- Agent orchestration, Portfolio Conference, autonomous AI-CIO
- Vector database, Kafka, Redis
- Physiological / robotics research layer

See [future-architecture.md](future-architecture.md) and [future-research.md](future-research.md).
