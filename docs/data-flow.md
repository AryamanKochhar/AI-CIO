# Data flow

1. Put a text-based MFCentral CAS at `data/cas.pdf`.
2. Run `python scripts/ingest.py data/cas.pdf`.
3. PyMuPDF extracts page text. The parser tracks AMC, folio, and scheme metadata across page breaks, then records holdings, transaction rows, and source pages.
4. SQLite stores the results locally in `data/portfolio.db`. Each ingest replaces prior portfolio records.
5. An MCP client calls a tool in `server.py`. The server retrieves database rows and uses `analysis.py` for aggregation.
6. For educational questions, the client can call `search_knowledge` and combine those general explanations with factual metrics.

Transaction descriptions are preserved and normalized to types such as `PURCHASE`, `SIP_PURCHASE`, `REDEMPTION`, `FAILED_PAYMENT`, `SIP_CANCELLED`, `SIP_REGISTERED`, `ADDRESS_UPDATE`, or `OTHER`. Failed and informational events never count as purchases.
