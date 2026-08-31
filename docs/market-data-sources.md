# Market Data Sources — AI-CIO

## Primary: NSE India

### Broad market

`GET https://www.nseindia.com/api/heatmap-index?type=Broad%20Market%20Indices`

Fields used: `index`, `indexLongName`, `current`, `close`, `pChange`, `timeStamp`, `yrHigh`, `yrLow`

### Sectoral indices

`GET https://www.nseindia.com/api/heatmap-index?type=Sectoral%20Indices`

Fallback per index:

`GET https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20IT`

### Sector classification

Constituents from `equity-stockIndices` per Nifty sector index — authoritative NSE/Nifty Indices membership.

**Do not** infer sector from company names or LLM.

## Access rules

- Fetch only from FastAPI backend (`NSEProvider`)
- Session warm-up, retries, cache, stale fallback
- Frontend never calls NSE directly

## Freshness labels

Snapshots expose `freshness`: Live / Recent / Stale. Cached data is never labelled Live.
