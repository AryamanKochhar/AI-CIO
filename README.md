# CAS Financial Intelligence MCP (V1)

A local-only MCP server that turns a text-based MFCentral CAMS/KFintech mutual-fund CAS into traceable holdings, transactions, deterministic portfolio calculations, and a small educational knowledge base. It does not provide personalised financial advice.

## Architecture

```text
CAS PDF → PyMuPDF parser → SQLite → MCP tools → MCP-compatible AI client
                              ↑              ↘ local Markdown knowledge
                         source pages
```

## Setup and ingestion

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p data
cp /path/to/your/CAS.pdf data/cas.pdf
.venv/bin/python scripts/ingest.py data/cas.pdf
```

The supplied PDF is deliberately not tracked. Place it at `data/cas.pdf`; PDF and database files are ignored by Git. The parser never logs raw CAS text or PII. It only supports text-extractable MFCentral CAMS/KFintech statements in V1 and reports unsupported/image-only pages rather than guessing.

## Run and inspect

```bash
.venv/bin/python server.py
# or, if uv is installed
uv run mcp dev server.py
pytest -q
```

Available tools: `get_holdings`, `get_portfolio_summary`, `get_transactions`, `get_sips`, `search_knowledge`, and `get_source`.

Example questions: “What are my current holdings?”, “What is my total portfolio value?”, “Which AMC am I most exposed to?”, “Which SIP/payment transactions failed?”, and “What does diversification mean?”

## Validation and limitations

The parser stores a source page with every holding and transaction. Values are retained as `Decimal`; failed payments, address changes and SIP registrations are not purchases. Before relying on a statement, review the ingestion result and reconcile closing units and valuation (`units × NAV`) against the CAS. The current parser is intentionally conservative and may need layout rules for a particular CAS edition; scanned/image-only PDFs require OCR, which is outside V1.

## Roadmap

Future phases only: upload UI; multiple historical CAS statements; official external educational sources; web-search context; and additional banking, brokerage, insurance and loan documents.
