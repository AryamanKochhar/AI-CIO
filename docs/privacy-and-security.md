# Privacy and Security — AI-CIO

> Status: **IMPLEMENTED (MVP)**. This is not production-grade authentication or encryption.

## Implemented

### Password handling

- Passwords are hashed with **PBKDF2-HMAC-SHA256** using a per-user random salt and **120,000 iterations**.
- The hash string format is `pbkdf2_sha256$<iterations>$<salt>$<derived_hex>`.
- Passwords are never stored in plaintext.
- Verification uses `secrets.compare_digest` for constant-time comparison.

### User isolation

- All financial and document queries are user-scoped.
- Cross-user document access raises a `DomainError`.
- Integration tests verify that one user cannot read another user's holdings.

### Secrets and configuration

- Secrets come from `.env` (loaded by `ai_cio/settings.py`).
- `.env` is not committed to the repository.
- `DATABASE_URL`, `CAS_PARSER_VERSION`, `AICIO_USER_ID`, `API_HOST`, and `API_PORT` are read from the environment.

### Document handling

- Uploaded document bytes are checksummed (SHA-256) and stored on the `Document` row.
- Raw CAS page text is stored in `source_pages` for traceability but **is never exposed via the API or MCP**.
- MCP tools return holdings and metadata only; they do not return raw page text.

### Logging

- No sensitive user data is written to application logs by the canonical services.
- CAS parsing warnings are stored in `warning_json` rather than logged.

## Production required

The MVP authentication and storage layers need hardening before deployment:

- Proper session tokens, cookies, or an OAuth/OIDC provider.
- Rate limiting on `/auth/*` and upload endpoints.
- TLS termination.
- Encrypted at-rest storage for document text and metadata.
- A real password policy (currently only minimum length 8).
- Audit logging for sensitive operations.
- Data retention and deletion workflows.
- Explicit user consent handling for sensitive financial data.

## Note on PDF storage

The system currently stores **extracted text only** in `source_pages`. The original PDF bytes are not persisted in the database or on disk by the canonical ingestion path.
