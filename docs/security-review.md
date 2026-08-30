# Security Review — AI-CIO Monorepo Restructure

> Date: 2026-08-30  
> Status: MVP development review (not production certification)

## Summary

The restructure preserves user-scoped data access, server-side psychometric scoring, and password hashing. Several items require hardening before production.

## Authentication

| Check | Status | Notes |
|-------|--------|-------|
| Passwords hashed | ✅ | PBKDF2-HMAC-SHA256, 290k iterations |
| Plaintext passwords stored | ✅ Not stored | Verified by tests |
| Password in API responses | ✅ Excluded | `UserResponse` omits hash |
| Session tokens / JWT | ⚠️ Not implemented | Client stores user id in localStorage (MVP) |
| HTTPS enforcement | ⚠️ Dev only | Required for production |
| Rate limiting on auth | ❌ Not implemented | PLANNED |

## Authorization / user isolation

| Check | Status | Notes |
|-------|--------|-------|
| Queries scoped by user_id | ✅ | Services enforce ownership |
| Cross-user data leakage tests | ✅ | `test_twin_cross_user_isolation`, document scoping tests |
| Client-provided user_id trusted | ⚠️ | No server-side session binding yet; MVP accepts path user_id |

## Data handling

| Check | Status | Notes |
|-------|--------|-------|
| Money as NUMERIC/Decimal | ✅ | No Float for money |
| Psychometric scoring server-side | ✅ | Frontend submits answer_id only |
| Raw CAS page text exposed | ✅ Not via API/MCP | Stored for traceability only |
| PII in logs | ⚠️ Review needed | Structured logging not fully implemented |
| Secrets in repo | ✅ | `.env` gitignored |

## File upload

| Check | Status | Notes |
|-------|--------|-------|
| File type validation | ✅ | PDF expected for CAS |
| File size limits | ⚠️ | No explicit max size on API |
| Path traversal | ✅ | Temp files with safe names |
| Unsupported doc types | ✅ | Stored without fabricated holdings |

## API

| Check | Status | Notes |
|-------|--------|-------|
| Input validation (Pydantic) | ✅ | Request schemas |
| Stack traces to users | ✅ | HTTPException detail only |
| CORS | ⚠️ | `allow_origins=["*"]` — tighten for production |
| SQL injection | ✅ | SQLAlchemy ORM parameterized queries |

## Recommendations before production

1. Implement secure HTTP-only session cookies or JWT with refresh rotation
2. Bind API routes to authenticated session user_id (reject mismatched path ids)
3. Add upload size limits and virus scanning policy
4. Restrict CORS to known web origins
5. Add rate limiting and account lockout on failed logins
6. Enable structured logging with request IDs; audit PII fields
7. Security headers on Next.js (CSP, HSTS)

## PLANNED (not in scope)

- OAuth / SSO
- Multi-factor authentication
- Field-level encryption at rest
- Penetration testing
