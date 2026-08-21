# Architecture

`parser.py` reads the PDF with PyMuPDF. It recognizes the MFCentral layout used by the uploaded CAS, including AMC headings, folios, scheme/ISIN lines, opening and closing balances, NAV, valuation, and page-spanning transaction tables.

`database.py` persists parsed records in local SQLite. The tables are `funds`, `holdings`, `transactions`, and `sources`. There is no ORM, remote database, cache, or external service.

`analysis.py` uses `Decimal` values to calculate totals, allocation buckets, rankings, SIP summaries, valuation comparisons, and unit reconciliation checks.

`server.py` registers the MCP tools. It returns facts; it is not a hard-coded chatbot or recommendation engine. `knowledge/` supplies locally searchable, educational Markdown articles.

Design principles: local-first processing, deterministic arithmetic, source-page traceability, conservative parsing, and a clear separation between factual metrics and client-side explanation.
