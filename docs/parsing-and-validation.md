# Parsing and validation

V1 supports text-extractable MFCentral CAMS/KFintech statements. The current CAS has a multi-line transaction layout:

```text
Date → transaction description → amount → units → price → unit balance
```

For failed-payment records, an instalment number can appear before the financial fields. The parser uses the final four numeric values as amount, units, NAV, and running balance, then classifies the record as `FAILED_PAYMENT`.

`validate_valuation()` compares reported valuation with `closing_units × NAV`, subject to a rounding tolerance. `reconcile_units()` compares opening units plus valid purchase/redemption movement with closing units. Neither function changes source data; they report discrepancies.

Run checks after changes:

```bash
pytest -q
python -c "import server; print(server.get_portfolio_summary())"
```

If ingestion reports no holdings, confirm the PDF contains selectable text and is an MFCentral detailed CAS. Do not make up values to bypass a parser failure.
