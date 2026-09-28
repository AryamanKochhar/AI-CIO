"""Configurable sector universe, Dhan instrument IDs, and portfolio exposure for the POC.

Security IDs were filled from Dhan's public instrument CSV:
  GET https://api.dhan.co/v2/instrument/IDX_I
Override any ID here if Dhan updates the master list.

NIFTY FINANCIAL SERVICES maps to FINNIFTY (security_id 27) — Dhan lists it as
"Finnifty" / FINNIFTY; there is no separate plain "Nifty Financial Services" row.
"""

from __future__ import annotations

# Benchmark
BENCHMARK = {
    "key": "NIFTY_50",
    "name": "NIFTY 50",
    "security_id": "13",
    "exchange_segment": "IDX_I",
    "instrument": "INDEX",
}

# Sector indices to score (exclude benchmark)
SECTORS = [
    {
        "key": "NIFTY_IT",
        "name": "NIFTY IT",
        "security_id": "29",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": None,  # Unmapped → diversification 50
    },
    {
        "key": "NIFTY_PHARMA",
        "name": "NIFTY PHARMA",
        "security_id": "32",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Healthcare / Pharma",
    },
    {
        "key": "NIFTY_AUTO",
        "name": "NIFTY AUTO",
        "security_id": "14",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": None,
    },
    {
        "key": "NIFTY_FMCG",
        "name": "NIFTY FMCG",
        "security_id": "28",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "FMCG / Consumer",
    },
    {
        "key": "NIFTY_METAL",
        "name": "NIFTY METAL",
        "security_id": "31",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Metals / Resources",
    },
    {
        "key": "NIFTY_REALTY",
        "name": "NIFTY REALTY",
        "security_id": "34",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": None,
    },
    {
        "key": "NIFTY_ENERGY",
        "name": "NIFTY ENERGY",
        "security_id": "42",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": None,
    },
    {
        "key": "NIFTY_INFRASTRUCTURE",
        "name": "NIFTY INFRASTRUCTURE",
        "security_id": "43",  # Dhan display name: NIFTY Infra
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Industrials / Capital Goods",
    },
    {
        "key": "NIFTY_CONSUMER_DURABLES",
        "name": "NIFTY CONSUMER DURABLES",
        "security_id": "466",  # Dhan: Nifty Consumer Durable
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "FMCG / Consumer",
    },
    {
        "key": "NIFTY_HEALTHCARE",
        "name": "NIFTY HEALTHCARE",
        "security_id": "447",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Healthcare / Pharma",
    },
    {
        "key": "NIFTY_MEDIA",
        "name": "NIFTY MEDIA",
        "security_id": "30",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": None,
    },
    {
        "key": "NIFTY_PSU_BANK",
        "name": "NIFTY PSU BANK",
        "security_id": "33",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Financials / Banks",
    },
    {
        "key": "NIFTY_FINANCIAL_SERVICES",
        "name": "NIFTY FINANCIAL SERVICES",
        "security_id": "27",  # FINNIFTY on Dhan master
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Financials / Banks",
    },
    {
        "key": "NIFTY_BANK",
        "name": "NIFTY BANK",
        "security_id": "25",
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "portfolio_category": "Financials / Banks",
    },
]

# From CIO Decisions true-exposure snapshot (direct equity sleeve labels)
PORTFOLIO_EXPOSURE_PCT = {
    "Financials / Banks": 63.20,
    "Financials / Market Infrastructure": 28.72,
    "Metals / Resources": 4.37,
    "Industrials / Capital Goods": 1.57,
    "FMCG / Consumer": 0.91,
    "Healthcare / Pharma": 0.48,
    "Cement / Materials": 0.06,
    "Unclassified": 0.69,
}

# How many calendar days of history to request (~100–150 trading days)
HISTORY_CALENDAR_DAYS = 220
MIN_CANDLES_REQUIRED = 55  # need 50 lookback + cushion

DHAN_HISTORICAL_URL = "https://api.dhan.co/v2/charts/historical"
DHAN_INSTRUMENT_CSV_URL = "https://api.dhan.co/v2/instrument/IDX_I"
DHAN_GENERATE_TOKEN_URL = "https://auth.dhan.co/app/generateAccessToken"
