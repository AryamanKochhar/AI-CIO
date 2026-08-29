# Architecture

AI-CIO is one product with one user-facing application.

The Streamlit shell (`frontend/app.py`) is the only user journey. Psychometrics, finances, goals, CAS, profile review, and decision capture are steps in that journey — not separate dashboards. FastAPI (`python -m ai_cio.api`) is the application API. PostgreSQL is the system of record. One `user_id` is used from onboarding through review.

`parser.py` reads an MFCentral CAS PDF with PyMuPDF. It recognizes AMC headings, folios, scheme/ISIN lines, balances, NAV, valuation, and page-spanning transaction tables. `analysis.py` uses `Decimal` values for totals, allocation, rankings, and unit checks. Ingest appends a document to the signed-in user; it does not wipe other users.

Psychometric questions are served from the seeded instrument. Option scores are omitted from the public payload. Scoring runs only on the server.

The Digital Financial Twin, specialist agents, and Portfolio Conference are internal concepts. They are not user-facing applications in this version. MCP (`server.py`) exposes read-only facts to models; it is not a second UI.

Design principles: one application, one identity, one database, explicit missing data, deterministic money arithmetic, human-in-the-loop, no autonomous trading.
