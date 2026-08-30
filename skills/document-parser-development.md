# Skill: Document Parser Development

## Purpose

Add support for new statement types (NSDL, CDSL, or other financial documents) using the parser adapter pattern, without fabricating holdings or leaking database concerns into the parser.

## When to use

- Adding a parser for NSDL statements, CDSL statements, mutual fund CAS variants, bank statements, etc.
- Extending the `Document` model with new `kind` values.
- Normalising extracted data into holdings, transactions, or other canonical structures.
- Surfacing parser warnings to users and operators.

## Architectural constraints

- Adapter pattern:
  ```text
  Document → Document Type → Parser Adapter → Normalized data
  ```
- Parsers live at the domain edge and are **pure**: no DB imports, no direct persistence.
- `ai_cio/services/documents.py` owns `SUPPORTED_KINDS` and `PARSABLE_KINDS`; only kinds in `PARSABLE_KINDS` are parsed into holdings.
- Document kinds are enumerated in `ai_cio/db/models.py` as `DOCUMENT_KINDS`.
- Unknown or unsupported statement content must not produce fabricated holdings.
- Parser warnings are surfaced through the document's `warning_json` and `status`/`validation_status` fields.

## Files to inspect first

1. `ai_cio/services/documents.py` — `SUPPORTED_KINDS`, `PARSABLE_KINDS`, `ingest_uploaded_document()`.
2. `ai_cio/db/models.py` — `DOCUMENT_KINDS`, `Document`, `SourcePage`, `Fund`, `Holding`, `Transaction`.
3. `ai_cio/services/portfolio.py` — how CAS holdings are persisted.
4. `parser.py` — existing CAS parser and `ParseResult`, `FundHolding`, `Transaction` structures.
5. `analysis.py` — portfolio analysis helpers.
6. `tests/test_parser.py` — parser unit tests.
7. `tests/fixtures/` — sample PDFs and golden outputs.

## Implementation rules

1. **Add the kind first**: update `DOCUMENT_KINDS` in `ai_cio/db/models.py` and register the new kind in `ai_cio/services/documents.py` before implementing parsing.
2. **Implement a parser adapter**: create a pure function that takes the raw document bytes/file path and returns a normalised result matching the existing `ParseResult` structure (or a documented extension of it).
3. **Keep the parser pure**: parser code must not import SQLAlchemy, FastAPI, Streamlit, or any service module. It may live in `parser.py`, a new module, or a sub-package.
4. **Register in `PARSABLE_KINDS`**: only after the adapter is complete and tested should the kind be moved from "stored pending" to `PARSABLE_KINDS`.
5. **Never fabricate holdings**: if parsing fails partially, return warnings and partial data; do not invent schemes, folios, or valuations.
6. **Surface warnings**: parser warnings must be appended to `document.warning_json` and should influence `status` (e.g., `needs_review`) and `validation_status` (e.g., `partial`).
7. **Store source pages**: extract and persist raw page text via `SourcePage` so downstream review can reference provenance.
8. **Persistence in the service layer**: the parser returns data; `ai_cio/services/portfolio.py` or a new persistence helper writes it to `funds`, `holdings`, `transactions`.
9. **Version the parser**: set `Document.parser_version` so migrations and audits can trace which parser produced the data.
10. **Status lifecycle**: document status should progress `pending → processing → extracted | needs_review | failed`.

## Testing requirements

- Unit tests for the parser adapter using fixture PDFs or synthetic text.
- Tests that verify no holdings are fabricated when parsing fails or content is unrecognised.
- Tests that warnings are returned and surfaced in the document payload.
- Integration tests for the full upload → parse → persist flow using the `client` fixture.
- Run `pytest tests/test_parser.py -q` and `pytest tests/test_runtime_unification.py -q`.
- Run `pytest -q` before finishing.

## Do NOT

- Add DB code inside the parser adapter.
- Return fabricated holdings, transactions, or valuations.
- Put parser logic in the UI or API routes.
- Register a kind in `PARSABLE_KINDS` before the adapter and tests exist.
- Expose raw page text in public APIs without a clear purpose.
- Skip fixture tests because "real PDFs are hard"; create minimal fixture PDFs or text stubs.

## Definition of done

- [ ] New document kind added to `DOCUMENT_KINDS` and registered in `documents.py`.
- [ ] Parser adapter implemented as a pure function with no DB dependencies.
- [ ] Adapter returns a normalised result and a warning list.
- [ ] Persistence logic added or reused in the service layer.
- [ ] Parser version recorded on the `Document` row.
- [ ] Kind added to `PARSABLE_KINDS` only after adapter + tests are complete.
- [ ] Fixture PDFs or text stubs exist for the new parser.
- [ ] Tests cover success, partial/failure, and no-fabrication cases.
- [ ] `pytest -q` passes.
