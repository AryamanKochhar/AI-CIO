# Privacy and limitations

## Privacy

- Processing is local; no cloud service or external search API is required.
- `data/*.pdf` and `*.db` are ignored by Git.
- Normal ingestion does not print raw CAS text.
- Source text is retained only in the local SQLite database for traceability; `get_source` returns related holdings rather than raw source text.
- Never commit or share the CAS, PAN, contact details, or database.

## Limitations

- Scanned/image-only PDFs are not supported because V1 has no OCR component.
- The parser targets the observed MFCentral format, not every provider or CAS layout.
- Review results against the source CAS whenever a provider changes its document layout.
- Asset allocation is not inferred from fund names in V1.
- Portfolio measures and knowledge content are factual/educational, not personalized financial advice.
