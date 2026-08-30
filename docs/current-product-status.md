# Current Product Status — AI-CIO

> Audit date: August 2026. Authoritative snapshot before product integration pass.

## IMPLEMENTED

| Area | Status | Location |
|------|--------|----------|
| Monorepo structure | ✅ | `apps/web`, `apps/api`, `packages/*` |
| PostgreSQL + Alembic | ✅ | `apps/api/ai_cio/db`, `alembic/` |
| MVP auth (register/login, PBKDF2) | ✅ | `/auth/register`, `/auth/login` |
| Psychometric instrument v1.0 | ✅ | `instruments/v1.0.json` |
| Server-side psychometric scoring | ✅ | `apps/api/ai_cio/psychometrics/` |
| Financial onboarding API | ✅ | `/users/{id}/finances` |
| Goals CRUD | ✅ | `/users/{id}/goals` |
| Unified document upload | ✅ | `/users/{id}/documents?kind=` |
| CAS parser + persistence | ✅ | `apps/api/domain/parser.py` |
| CDSL CAS parser + persistence | ✅ | `apps/api/domain/documents/cdsl.py` |
| Digital Financial Twin API | ✅ | `/users/{id}/twin` |
| Financial Map (Twin projection) | ✅ | Twin `financial_map` + Twin UI |
| Journey persistence | ✅ | `/users/{id}/journey` |
| MCP read tools | ✅ | `apps/api/aicio_mcp/` |
| Backend tests | ✅ | 56 passing |
| Next.js canonical UI | ✅ | `apps/web` |
| Basic onboarding routes | ✅ | `/onboarding/*` |
| Shared UI package | ✅ | `packages/ui` |
| Unified Docker dev stack | ✅ | `make dev-up` — postgres, api, web |

## PARTIALLY IMPLEMENTED

| Area | Gap |
|------|-----|
| Landing / login UX | Functional but not premium; no split hero |
| Onboarding welcome | No dedicated welcome/resume screen |
| Psychometric UX | No back button; weak resume of in-progress session |
| Financial onboarding UI | Single form, not progressive multi-step |
| Goals UI | Basic list, not card-based selection |
| Document upload UX | Basic file input, limited state machine |
| Portfolio review | Holdings table exists; no explicit confirm step |
| Twin UI | Financial Map with drill-down, search, insights; list fallback |
| Journey resume | API exists; web does not route on login |
| Application shell | Minimal header; no contextual “what’s next” |
| Frontend tests | None yet |
| Session binding | MVP localStorage; path user_id not bound to auth |

## NOT IMPLEMENTED (this milestone)

| Area | Notes |
|------|-------|
| Specialist AI agents | Future phase |
| Portfolio Conference | Future phase |
| Investment recommendations | Explicitly out of scope |
| NSDL/CDSL parsing | Architecture only |
| Production auth (cookies/JWT) | Documented as future |
| Physiological sensing | Future research |

## DEPRECATED

| Path | Status |
|------|--------|
| `frontend/` (Streamlit) | **DELETED** — do not use |
| `parv-main/` | **DELETED** — do not use |
| Root duplicate `ai_cio/` | Legacy copy; canonical is `apps/api/ai_cio/` |
| SQLite runtime | Not used |

## Streamlit parity checklist

| Journey step | Next.js | Streamlit |
|--------------|---------|-----------|
| Login / identity | ✅ | Name-only |
| Psychometric assessment | ✅ | ✅ |
| Financial profile | ✅ | ✅ |
| Goals | ✅ | ✅ |
| CAS upload | ✅ | ✅ |
| Portfolio review | ⚠️ partial | ✅ |
| Review summary | ✅ | ✅ |
| Financial profile / Twin | ✅ | ✅ (review) |
| Resume onboarding | ⚠️ partial | ✅ (journey API) |
