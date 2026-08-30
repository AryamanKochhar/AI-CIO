# Skill: Security Review

## Purpose

Check that a change does not weaken AI-CIO's security posture around secrets, authentication, authorisation, data exposure, and logging.

## When to use

- Adding authentication, registration, or login flows.
- Storing or handling passwords, API keys, or connection strings.
- Adding endpoints that return user data.
- Adding document parsing, logging, or admin endpoints.
- Before any production-hardening task.

## Architectural constraints

- Secrets live in `.env`, never in source code.
- Passwords are hashed with PBKDF2-HMAC-SHA256 in `ai_cio/services/identity.py`; this is labelled MVP, not production-grade.
- All user-owned queries are scoped to `user_id`.
- Raw document text is stored in `source_pages` but not exposed through public, unscoped endpoints.
- Sensitive data must not appear in logs or error messages.
- The product is currently an MVP; production-grade hardening must be explicitly labelled as such.

## Files to inspect first

1. `.env.example` and `.env` — what secrets exist and how they are loaded.
2. `ai_cio/settings.py` — secret and configuration loading.
3. `ai_cio/services/identity.py` — password hashing and verification.
4. `ai_cio/api/routes.py` — endpoints that expose user data or accept credentials.
5. `ai_cio/services/*.py` — user-scoping and data access patterns.
6. `ai_cio/db/models.py` — sensitive fields (password_hash, email, source page text).
7. Logging configuration and any `print()` statements in the changed code.

## Implementation rules

1. **Secrets in `.env`**: database URLs, default user IDs, and any future API keys must be read from environment variables via `ai_cio/settings.py` or `.env`. Never commit secrets.
2. **Password hashing**: passwords must be hashed before storage. Use `_hash_password()` in `identity.py` or a production-grade successor. Never store plaintext.
3. **User-scoped queries**: any query returning user data must filter by `user_id`. Admin endpoints must be clearly labelled and, in production, protected.
4. **No raw document text exposure**: `SourcePage.text` is for provenance and review, not for bulk public API exposure.
5. **No sensitive data in logs**: do not log passwords, full documents, email addresses, holdings, or `user_id` in production logs.
6. **Error messages**: return generic messages for auth failures ("Invalid email or password") to avoid user enumeration.
7. **MVP labelling**: explicitly label MVP security mechanisms (e.g., the current PBKDF2 implementation, name-only dev mode) as not production-grade.
8. **Input validation**: validate and sanitise file uploads (PDF-only for CAS), email format, password length, and enum values.
9. **Admin endpoints**: keep admin endpoints thin and consider them placeholders until proper authorisation exists.
10. **Dependencies**: keep security-sensitive dependencies up to date; avoid adding unnecessary auth or crypto libraries.

## Testing requirements

- Add tests that verify:
  - Passwords are not stored in plaintext.
  - Users cannot read or mutate another user's data.
  - Auth failures return generic error messages.
  - Sensitive fields are not returned by public endpoints.
- Run `pytest -q` before finishing.

## Do NOT

- Commit secrets, passwords, or `.env` files.
- Return `password_hash` in any API response.
- Log raw request bodies, documents, or credentials.
- Add admin endpoints without clearly documenting them as unprotected placeholders.
- Claim MVP security is production-ready.
- Skip user-scoping because the UI "always passes the right user_id".

## Definition of done

- [ ] No secrets added to source code.
- [ ] Passwords hashed before storage; no plaintext leakage.
- [ ] User-owned endpoints scoped to `user_id`.
- [ ] Sensitive fields excluded from API responses.
- [ ] Logs do not contain sensitive data.
- [ ] Security tests added or updated for the changed surface area.
- [ ] MVP-only mechanisms are explicitly labelled.
- [ ] `pytest -q` passes.
