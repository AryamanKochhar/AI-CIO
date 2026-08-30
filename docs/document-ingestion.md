# Document Ingestion — AI-CIO

> Status: **IMPLEMENTED**. CAS is parsed; NSDL/CDSL statements are stored and explicitly marked as parser pending.

## Unified upload endpoint

The canonical entry point is:

```text
POST /users/{id}/documents?kind=...
```

Supported `kind` values:

- `cas_pdf`
- `nsdl_statement`
- `cdsl_statement`
- `other`

The older `POST /users/{id}/documents/cas` endpoint is kept for backward compatibility and simply delegates to the unified service with `kind=cas_pdf`.

## Ingestion contract

The parser adapter pattern in `ai_cio/services/documents.py` is:

```text
Document → Document Type → Parser Adapter → Normalized Financial Data
```

Currently only CAS has a concrete adapter (`parser.py` → `ai_cio/services/portfolio.py`).

## CAS ingestion flow

1. The uploaded bytes are written to a temporary file.
2. `parser.py` parses the MFCentral CAMS/KFintech CAS PDF using PyMuPDF.
3. `parse_cas` returns a `ParseResult` containing:
   - `holdings`
   - `transactions`
   - `pages` (raw text by one-based page)
   - `warnings`
4. `ai_cio/services/portfolio.py::persist_parse_result` stores:
   - One `Document` row with `kind=cas_pdf`, `parser_version`, `checksum`, and `warning_json`.
   - One `SourcePage` row per extracted page.
   - `Fund`, `Holding`, and `Transaction` rows all carrying `user_id` and `document_id`.
5. If no holdings are confidently parsed, ingestion stops with a `DomainError` and no partial rows are committed.
6. After successful CAS ingestion, the unified service sets:
   - `status = "extracted"` and `validation_status = "valid"` if no warnings.
   - `status = "needs_review"` and `validation_status = "partial"` if warnings exist.

## Multiple documents per user

- A user can upload multiple CAS PDFs.
- Each upload creates a new `Document` and child rows.
- No upload ever deletes or overwrites another user's data.
- Holdings queries default to the latest CAS document but can be scoped to any document the user owns.

## NSDL / CDSL / other ingestion

For kinds whose parser is not yet implemented:

- The file is stored as a `Document` with the correct `kind`.
- `status` stays `pending`.
- `validation_status` stays `unvalidated`.
- The response includes a warning such as `"nsdl_statement parser support pending; document stored for future processing."`.
- **No holdings or transactions are fabricated.**

## Data integrity fields

- `checksum`: SHA-256 of uploaded bytes.
- `parser_version`: taken from `CAS_PARSER_VERSION` env (default `cas-v1`).
- `warning_json`: list of parser warnings stored as JSON.

## Status and validation values

`status` check constraint:

- `pending`
- `processing`
- `extracted`
- `needs_review`
- `failed`

`validation_status` check constraint:

- `unvalidated`
- `valid`
- `partial`
- `invalid`

## Planned (not implemented)

- NSDL and CDSL parser adapters.
- OCR support for image-only or scanned PDFs.
- A dedicated validation UI workflow for `needs_review` documents.
