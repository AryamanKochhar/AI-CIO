# Mutual fund source audit

Verified on 20 October 2026. This records public source coverage, not the contents of any investor's account. No fund units, cash balances, goals or psychometric answers are created or changed by the adapters.

## New directly fetched evidence

| Exact direct-growth scheme | Source observation | Identified securities | Full-scheme NAV coverage | Source |
| --- | --- | ---: | ---: | --- |
| Nippon India Small Cap Fund, INF204K01K15 / MFAPI 118778 | 30 September 2026 | 256 | 97.38% | [Official monthly workbook](https://mf.nipponindiaim.com/InvestorServices/FactsheetsDocuments/NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls) |
| PGIM India Midcap Fund, INF663L01DV3 / MFAPI 125307 | 30 September 2026 | 103 | 98.23% | [Official scheme workbook](https://www.pgimindia.com/api/v1/brochure/about-us/image/PGIM%20INDIA%20MIDCAP%20FUND%20Sep%202026.xlsx) |

The Nippon file has an `.xls` URL but contains an XLSX archive. The adapter reads only the exact `SC` worksheet and verifies the `RLMF200` scheme identifier. The numerical percentage cells are Excel fractions, so `0.0188` becomes 1.88 percentage points. The PGIM `Mid Cap` worksheet already expresses weights in percentage points. The parser does not rescale either portfolio to 100%. Cash, receivables and securities without an identified ISIN remain outside measured look-through. A partial-coverage overlap remains a lower bound.

Both workbooks confirm their scheme benchmark: NIFTY Smallcap 250 TRI for Nippon Small Cap and Nifty Midcap 150 TRI for PGIM Midcap. A confirmed benchmark name does not supply the underlying daily total-return series.

Nippon download discovery starts at its [official disclosures page](https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures/). PGIM uses the read-only public disclosure form called by its [monthly portfolio page](https://www.pgimindia.com/mutual-funds/disclosures/Portfolios/Monthly-Portfolio), followed by an exact official-host workbook URL. It does not require investor credentials or account access. Returned external hosts, different scheme names, inconsistent dates, unsupported columns and future observations are rejected.

## Additional published comparison

The [Nippon September factsheet](https://mf.nipponindiaim.com/InvestorServices/FactsheetsDocuments/Fundamentals-September-2026/Innerpage/Small-Cap.html) states **31 August 2026** as its performance date. The folder month is not used as the observation date.

| Published period | Direct-plan return | Nifty Smallcap 250 TRI return | Difference |
| --- | ---: | ---: | ---: |
| 1 year | 14.17% | 11.88% | +2.29 percentage points |
| 3 years | 16.32% | 16.15% | +0.17 percentage points |
| 5 years | 20.07% | 16.55% | +3.52 percentage points |

These are AMC-reported plan comparisons, separate from performance computed from NAV and an independently obtained TRI series. The table does not explicitly establish a Growth/IDCW basis or exact starting market dates. It cannot establish rolling consistency, predict a return, or justify a fund-switch recommendation by itself. Its expense disclosure says BER; the adapter does not call that value TER.

## Coverage limits and bounded operation

The existing PPFAS Flexi Cap and ELSS adapters remain active. The new Nippon and PGIM families increase automatically supported holdings disclosure coverage from two to four of the eight exact schemes inspected for this task. MFAPI provides exact-identity NAV history for the other schemes; a NAV series can still support historical fund growth, drawdown and pairwise monthly return correlation without a holdings disclosure.

Kotak's two scheme/API routes redirected to a bot challenge in this environment. That challenge was not bypassed. SBI's public page requires its own tested download integration. HDFC's official September index factsheet provides scheme terms and a partial named portfolio, but it is not an ISIN-identified full holdings file. No unsupported holdings or TRI history have been invented for these schemes. Validated user-scoped disclosure/TRI imports remain supported.

All new network requests share the existing provider's per-analysis deadline and response-size limit, use its atomic public cache and single-flight locks, and do not follow off-host redirects. Public source caches contain no investor account data. A changed source does not silently become an authenticated user upload, and an uploaded official-looking URL is still marked as user supplied.

## Validation

Focused tests passed: **92 tests** across publisher adapters, disclosure/import boundaries, published comparisons, MF analysis, freshness and shared exposure integration. The new fixtures are small synthetic examples of the publisher layouts. They test distinct percentage units, exact scheme/sheet binding, changed titles/dates/headers/benchmarks, full-NAV coverage, nonfinite values, public read-only request payloads, URL allowlists, cache reuse and the distinction between published trailing comparisons and TRI history. Explicit direct bond classes are excluded from MF identity resolution while their value remains an unknown slice in MF look-through; generic debt-fund rows remain eligible.

Live adapter checks downloaded and parsed both official workbooks and the Nippon factsheet. Public document hashes:

- Nippon portfolio: `f8b25cedeecdd9912e0b4b19f74714fc849bae4dae0cb494c4863fde42a178d1`
- PGIM portfolio: `f55d89942a15f65c2b99549332c7ebf6c2ef9b00d0c56fd454f71f256c73af47`
- Nippon published comparison: `0771d4a62174df58f8cd3c670fac8f149c97a114a6e696fa984d6f04eae013e6`
