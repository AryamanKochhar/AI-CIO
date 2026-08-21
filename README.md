# CAS Financial Intelligence MCP

A local MCP (Model Context Protocol) server for inspecting an Indian mutual-fund Consolidated Account Statement (CAS). It extracts facts from a text-based MFCentral CAMS/KFintech PDF, stores them locally in SQLite, calculates portfolio metrics deterministically, and makes those facts available to an MCP-compatible AI client. This is educational tooling, not personalised financial advice.

## What it does

- Parses holdings, folios, ISINs, units, NAVs, valuations, transactions, and source pages.
- Treats failed SIP/payment events as events—not investments.
- Calculates total value, fund/AMC allocation, rankings, and concentration metrics with `Decimal` arithmetic.
- Searches local educational Markdown content for explanatory context.

## Architecture

```text
CAS PDF → PyMuPDF parser → SQLite → MCP tools → MCP-compatible AI client
                              ↑              ↘ local Markdown knowledge
                         source pages
```

For a detailed design, see [architecture.md](docs/architecture.md) and [data-flow.md](docs/data-flow.md).

## Setup, ingest, and run

```bash
# 1. Create an isolated environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Place a local, text-extractable CAS PDF in the ignored data directory
mkdir -p data
cp /path/to/your/CAS.pdf data/cas.pdf

# 3. Parse it and create/update the local SQLite database
python scripts/ingest.py data/cas.pdf

# 4. Run automated tests
pytest -q

# 5. Start the server over standard input/output
python server.py
```

The supplied PDF is deliberately not tracked. Place it at `data/cas.pdf`; PDF and database files are ignored by Git. The parser never logs raw CAS text or PII. It only supports text-extractable MFCentral CAMS/KFintech statements in V1 and reports unsupported/image-only pages rather than guessing.

## Inspect the MCP

```bash
# If uv is installed, launch MCP Inspector / development mode
uv run mcp dev server.py
```

Available tools: `get_holdings`, `get_portfolio_summary`, `get_transactions`, `get_sips`, `search_knowledge`, and `get_source`. Details and examples are in [mcp-tools.md](docs/mcp-tools.md).

Example questions: “What are my current holdings?”, “What is my total portfolio value?”, “Which AMC am I most exposed to?”, “Which SIP/payment transactions failed?”, and “What does diversification mean?”

## Current uploaded CAS

The current project has been ingested from `data/cas_detailed_report_2026_08_21_222901.pdf`: 12 holdings and 101 transactions were parsed. To re-run that ingest:

```bash
cp data/cas_detailed_report_2026_08_21_222901.pdf data/cas.pdf
python scripts/ingest.py data/cas.pdf
```

`data/portfolio.db` is the resulting local database. It is excluded from Git.

## Validation, privacy, and limitations

The parser stores a source page with every holding and transaction. Values are retained as `Decimal`; failed payments, address changes and SIP registrations are not purchases. Before relying on a statement, review the ingestion result and reconcile closing units and valuation (`units × NAV`) against the CAS. The current parser is intentionally conservative and may need layout rules for a particular CAS edition; scanned/image-only PDFs require OCR, which is outside V1.

See [parsing-and-validation.md](docs/parsing-and-validation.md) for the parsing rules and checks, and [privacy-and-limitations.md](docs/privacy-and-limitations.md) for data-handling guidance.

## Project map

```text
server.py             MCP server and tools
parser.py             CAS parser and event normalization
database.py           SQLite schema and queries
analysis.py           deterministic calculations and validation helpers
scripts/ingest.py     command-line ingest entry point
knowledge/            local general-education Markdown
docs/                 implementation and operation documentation
tests/                automated tests
```

## Roadmap

Future phases only: upload UI; multiple historical CAS statements; official external educational sources; web-search context; and additional banking, brokerage, insurance and loan documents.
