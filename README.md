# AI-CIO

One product, one application, one user identity.

AI-CIO is a human-in-the-loop personal financial decision-support system. It walks a person through psychometric onboarding, finances, goals, and document upload inside a single UI, then assembles a Digital Financial Twin for human review. It does not place trades and it does not invent missing numbers.

## Current MVP

```text
LOGIN → UNDERSTAND ME → MY FINANCES → MY GOALS → DOCUMENTS → REVIEW → FINANCIAL PROFILE (TWIN)
```

Future capabilities (agents, conference, autonomous recommendations) are **not implemented**.

## Architecture

```text
Next.js (apps/web)
        │  HTTP
        ▼
FastAPI (python -m ai_cio.api)
        │
        ▼
Domain services (ai_cio/services)
        │
        ▼
PostgreSQL

MCP (python server.py) → Domain → PostgreSQL
```

## Repository structure

```text
apps/
  api/          # Python API documentation entry point
  web/          # Next.js user interface (canonical UI)
packages/
  ui/           # Shared design system components
  contracts/    # Shared TypeScript API contracts
  utils/        # Shared formatting helpers
  config-*/     # Shared ESLint/TS config
ai_cio/         # Python domain package (API, services, db, psychometrics)
instruments/    # Versioned psychometric instrument
knowledge/      # Educational markdown for MCP
tests/          # pytest suite
docs/           # Architecture and product documentation
skills/         # Engineering agent skills
```

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- pnpm 9+
- Docker (for PostgreSQL)

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pnpm install
cp .env.example .env
```

### Database

```bash
docker compose up -d
alembic upgrade head
```

### Run API

```bash
python -m ai_cio.api
```

API: http://127.0.0.1:8000

### Run web (canonical UI)

```bash
pnpm dev:web
```

Web: http://localhost:3000

### Run tests

```bash
pytest -q          # backend (54 tests)
pnpm typecheck     # frontend types
pnpm build         # frontend production build
```

### Legacy Streamlit UI (deprecated)

```bash
streamlit run frontend/app.py
```

Streamlit remains for parity verification during migration. **Do not use for new development.**

## Authentication (MVP)

Registration and login use email + password with PBKDF2-HMAC-SHA256 hashing. This is development-grade authentication and requires production hardening (HTTPS-only cookies, rate limiting, email verification, etc.) before any real deployment.

## Current limitations

- NSDL/CDSL documents are stored but not parsed (explicit "parser pending" message)
- No autonomous investment recommendations or trade execution
- MVP auth without OAuth or session tokens
- Analysis / Portfolio Conference / AI-CIO decision synthesis not implemented

## Documentation

- [Current architecture](docs/current-architecture.md)
- [Target architecture](docs/target-architecture.md)
- [Migration map](docs/migration-map.md)
- [UI design](docs/ui-design.md)
- [Security review](docs/security-review.md)
- [Development guide](docs/development-guide.md)
