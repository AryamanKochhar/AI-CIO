# Document Ingestion — AI-CIO

> Status: **IMPLEMENTED** for Mutual Fund CAS (`cas_pdf`) and CDSL CAS (`cdsl_statement`). NSDL remains stored with parser pending.

## Unified upload endpoint

```text
POST /users/{id}/documents?kind=...
```

Supported `kind` values:

- `cas_pdf` — MFCentral CAMS/KFintech mutual fund CAS (parsed)
- `cdsl_statement` — CDSL Consolidated Account Statement (parsed)
- `nsdl_statement` — stored; parser pending
- `other` — stored; parser pending

## Adapter architecture

```text
Document → Classifier / kind → Document Adapter → Normalized Financial Data → Persistence → Twin
```

| Kind | Adapter | Location |
|------|---------|----------|
| `cas_pdf` | `parse_cas` | `apps/api/domain/parser.py` |
| `cdsl_statement` | `parse_cdsl_cas` | `apps/api/domain/documents/cdsl.py` |
| `nsdl_statement` | pending | — |

Parsers are pure (no DB). Persistence lives in `ai_cio/services/portfolio.py`. Orchestration lives in `ai_cio/services/documents.py`.

## CDSL CAS flow

1. Validate PDF size/type.
2. Classify using multiple CDSL markers (not a single string).
3. Extract statement metadata, demat accounts, equity holdings/transactions, MF holdings/transactions, portfolio summary, monthly snapshots.
4. Persist into existing `documents`, `funds`, `holdings`, `transactions`, plus `portfolio_snapshots`.
5. Store structured metadata on `documents.metadata_json` (period, CAS ID, accounts, allocation).
6. Return summary for extraction review; user confirms via existing portfolio confirm endpoint.
7. Digital Twin reads normalized holdings with provenance (`source`, period, last processed).

## Idempotency

Uploads are fingerprinted with SHA-256 `checksum`. Re-uploading the same bytes for the same user returns the existing document with `already_processed: true` and does not duplicate holdings/transactions.

## Provenance

Every holding and transaction row carries `user_id` and `document_id`. Twin portfolio provenance includes document kind, statement period, and processed time.

## Status values

`pending` → `processing` (transient) → `extracted` | `needs_review` | `failed`

Partial CDSL extraction (some sections failed) uses `needs_review` / `validation_status=partial`.

## Future NSDL

Add `domain/documents/nsdl.py` implementing the same normalized `ParseResult` + metadata contract, register in `PARSABLE_KINDS`, and reuse persistence. The Twin should not care whether holdings came from CDSL or NSDL.
