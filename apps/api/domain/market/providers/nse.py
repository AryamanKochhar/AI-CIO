"""NSE market data provider with session handling, retries, and validation."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from domain.market.contracts import MarketIndexSnapshot, SectorConstituent
from domain.market.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
BROAD_HEATMAP_URL = f"{NSE_BASE}/api/heatmap-index?type=Broad%20Market%20Indices"
SECTOR_HEATMAP_URL = f"{NSE_BASE}/api/heatmap-index?type=Sectoral%20Indices"
EQUITY_INDEX_URL = f"{NSE_BASE}/api/equity-stockIndices"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{NSE_BASE}/market-data/live-market-indices",
}

# Authoritative Nifty sector indices (NSE Indices). Used when heatmap unavailable.
NIFTY_SECTOR_INDICES: list[tuple[str, str]] = [
    ("NIFTY AUTO", "Auto"),
    ("NIFTY BANK", "Bank"),
    ("NIFTY FINANCIAL SERVICES", "Financial Services"),
    ("NIFTY FMCG", "FMCG"),
    ("NIFTY HEALTHCARE", "Healthcare"),
    ("NIFTY IT", "Information Technology"),
    ("NIFTY MEDIA", "Media"),
    ("NIFTY METAL", "Metal"),
    ("NIFTY OIL & GAS", "Oil & Gas"),
    ("NIFTY PHARMA", "Pharma"),
    ("NIFTY PSU BANK", "PSU Bank"),
    ("NIFTY PRIVATE BANK", "Private Bank"),
    ("NIFTY REALTY", "Realty"),
    ("NIFTY CONSUMER DURABLES", "Consumer Durables"),
    ("NIFTY CHEMICALS", "Chemicals"),
]


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_timestamp(raw: Any) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _normalize_heatmap_row(row: dict[str, Any], *, category: str) -> MarketIndexSnapshot | None:
    code = (row.get("index") or row.get("indexSymbol") or "").strip()
    if not code:
        return None
    current = _dec(row.get("current") or row.get("last"))
    close = _dec(row.get("close") or row.get("previousClose"))
    change = None
    if current is not None and close is not None:
        change = current - close
    pchange = _dec(row.get("pChange") or row.get("percentChange"))
    return MarketIndexSnapshot(
        provider="nse",
        index_code=code,
        index_name=(row.get("indexLongName") or row.get("index") or code).strip(),
        category=category,
        timestamp=_parse_timestamp(row.get("timeStamp") or row.get("lastUpdateTime")),
        current_value=current,
        previous_close=close,
        change=change,
        change_percent=pchange,
        day_high=_dec(row.get("high")),
        day_low=_dec(row.get("low")),
        year_high=_dec(row.get("yrHigh")),
        year_low=_dec(row.get("yrLow")),
        source="nse",
        is_stale=False,
    )


class NSEProvider(MarketDataProvider):
    provider_name = "nse"

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
            )
            self._warm_session(self._client)
        return self._client

    def _warm_session(self, client: httpx.Client) -> None:
        try:
            client.get(NSE_BASE)
        except httpx.HTTPError as exc:
            logger.warning("NSE session warm-up failed: %s", exc)

    def _request_json(self, url: str) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                client = self._get_client()
                response = client.get(url)
                if response.status_code == 429:
                    sleep_s = self.backoff_base * (2**attempt)
                    logger.warning("NSE rate limit (429); backing off %.1fs", sleep_s)
                    time.sleep(sleep_s)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                sleep_s = self.backoff_base * (2**attempt)
                logger.warning("NSE request failed (attempt %s): %s", attempt + 1, exc)
                if attempt < self.max_retries - 1:
                    time.sleep(sleep_s)
        raise RuntimeError(f"NSE request failed after {self.max_retries} attempts: {last_exc}")

    def _parse_heatmap(self, payload: Any, *, category: str) -> list[MarketIndexSnapshot]:
        rows = payload
        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("heatmap") or []
        if not isinstance(rows, list):
            raise ValueError("Unexpected NSE heatmap response shape")
        out: list[MarketIndexSnapshot] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            snap = _normalize_heatmap_row(row, category=category)
            if snap:
                out.append(snap)
        return out

    def get_broad_market_indices(self) -> list[MarketIndexSnapshot]:
        payload = self._request_json(BROAD_HEATMAP_URL)
        return self._parse_heatmap(payload, category="broad")

    def get_sectoral_indices(self) -> list[MarketIndexSnapshot]:
        try:
            payload = self._request_json(SECTOR_HEATMAP_URL)
            snaps = self._parse_heatmap(payload, category="sector")
            if snaps:
                return snaps
        except Exception as exc:
            logger.warning("Sector heatmap unavailable, falling back to per-index fetch: %s", exc)
        out: list[MarketIndexSnapshot] = []
        for code, _label in NIFTY_SECTOR_INDICES:
            try:
                out.append(self.get_index(code))
            except Exception as exc:
                logger.warning("Failed to fetch sector index %s: %s", code, exc)
        return out

    def get_index(self, index_code: str) -> MarketIndexSnapshot:
        from urllib.parse import quote

        url = f"{EQUITY_INDEX_URL}?index={quote(index_code)}"
        payload = self._request_json(url)
        meta = payload if isinstance(payload, dict) else {}
        if isinstance(meta.get("data"), list) and meta["data"]:
            # equity-stockIndices returns list of stocks; index metadata in payload root keys
            pass
        row = {
            "index": index_code,
            "indexLongName": meta.get("name") or index_code,
            "current": meta.get("last"),
            "close": meta.get("previousClose"),
            "open": meta.get("open"),
            "high": meta.get("dayHigh"),
            "low": meta.get("dayLow"),
            "pChange": meta.get("pChange"),
            "yrHigh": meta.get("yearHigh"),
            "yrLow": meta.get("yearLow"),
            "timeStamp": meta.get("timestamp") or meta.get("lastUpdateTime"),
        }
        category = "broad" if index_code in {"NIFTY 50", "NIFTY 100", "NIFTY 500"} else "sector"
        snap = _normalize_heatmap_row(row, category=category)
        if not snap:
            raise ValueError(f"Could not normalize index {index_code}")
        return snap

    def get_sector_constituents(self, sector_index_code: str, sector_name: str) -> list[SectorConstituent]:
        from urllib.parse import quote

        url = f"{EQUITY_INDEX_URL}?index={quote(sector_index_code)}"
        payload = self._request_json(url)
        rows = payload.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("data") or []
        out: list[SectorConstituent] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = (row.get("symbol") or "").strip()
            if not symbol or symbol == sector_index_code:
                continue
            out.append(
                SectorConstituent(
                    symbol=symbol,
                    name=(row.get("meta") or row.get("companyName") or symbol).strip(),
                    isin=(row.get("isin") or row.get("identifier") or None),
                    sector_index_code=sector_index_code,
                    sector_name=sector_name,
                )
            )
        return out

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
