"""Bounded read-only Dhan bond catalogue/quotes; never broker account data.

The detailed master supplies routing identity, not contractual bond cashflows.
No login or forced token mint is performed for a decision page refresh.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import threading
import time

import httpx

from ai_cio import settings
from ai_cio.services.mutual_funds.cache import PublicDataCache

MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
QUOTE_URL = "https://api.dhan.co/v2/marketfeed/quote"
_quote_lock = threading.Lock()
_last_quote = 0.0


@contextmanager
def _bounded_lock(lock, timeout: float = 1.5):
    if not lock.acquire(timeout=timeout):
        raise RuntimeError("Public market request governor is busy; retry without blocking the decision")
    try:
        yield
    finally:
        lock.release()


def cache_root() -> Path:
    return Path(os.getenv("BOND_CACHE_DIR", str(Path(settings.ROOT) / ".dev" / "bond-cache")))


def cache_fingerprint() -> str:
    """Cheap public-source cache revision, with no account or credential material."""
    root = cache_root()
    try:
        entries = sorted(f"{p.name}:{p.stat().st_size}:{p.stat().st_mtime_ns}"
                         for p in root.glob("*.json") if p.is_file())
    except OSError:
        entries = ["cache_unavailable"]
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def classify_row(row: dict) -> str | None:
    if row.get("SEGMENT") != "E":
        return None
    exchange, kind, series = row.get("EXCH_ID"), row.get("INSTRUMENT_TYPE"), row.get("SERIES")
    if exchange == "NSE" and kind == "DBT" and series == "GS":
        return "government_dated"
    if exchange == "NSE" and kind == "DBT" and series == "SG":
        return "state_development"
    if kind == "TB" and ((exchange == "NSE" and series == "TB") or (exchange == "BSE" and series == "G")):
        return "treasury_bill"
    if exchange == "NSE" and kind == "Other" and series == "GB":
        return "sovereign_gold"
    # BSE series G alone also contains non-gold securities. BSE SGB mapping is
    # joined by exact ISIN to an independently classified NSE SGB record.
    if kind in ("DEB", "GB"):
        return "corporate"
    return None


def parse_master(text: str) -> dict:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    needed = {"EXCH_ID", "SEGMENT", "SECURITY_ID", "ISIN", "INSTRUMENT", "INSTRUMENT_TYPE", "SERIES", "LOT_SIZE"}
    if not needed.issubset(set(reader.fieldnames or [])):
        raise ValueError("Dhan detailed catalogue schema is not recognized")
    rows, count = [], 0
    for row in reader:
        count += 1
        if count > 600_000:
            raise ValueError("Dhan catalogue exceeds bounded row count")
        category = classify_row(row)
        if category is None:
            continue
        isin = str(row.get("ISIN") or "").strip().upper()
        sid = str(row.get("SECURITY_ID") or "").strip()
        if len(isin) != 12 or not isin.isalnum() or not sid.isdigit():
            continue
        rows.append({"isin": isin, "security_id": sid, "exchange": row["EXCH_ID"],
                     "exchange_segment": row["EXCH_ID"] + "_EQ", "instrument": row["INSTRUMENT"],
                     "instrument_type": row["INSTRUMENT_TYPE"], "series": row["SERIES"],
                     "category": category, "name": row.get("DISPLAY_NAME") or row.get("SYMBOL_NAME") or isin,
                     "lot_size": row.get("LOT_SIZE"), "raw_tick_size": row.get("TICK_SIZE"),
                     "buy_sell_indicator": row.get("BUY_SELL_INDICATOR"),
                     "derivative_expiry_unused": row.get("SM_EXPIRY_DATE")})
    if not rows:
        raise ValueError("No bond identities found in detailed catalogue")
    return {"rows": rows, "total_rows": count, "sha256": hashlib.sha256(text.encode()).hexdigest()}


class DhanBondProvider:
    """One batched quote for the verified universe; repeated reloads share cache."""

    def __init__(self, *, cache: PublicDataCache | None = None, transport=None):
        self.cache = cache or PublicDataCache(cache_root())
        self.transport = transport

    def _master(self) -> dict:
        def load():
            with httpx.Client(timeout=httpx.Timeout(12, connect=4), transport=self.transport,
                              follow_redirects=True) as client:
                with client.stream("GET", MASTER_URL) as response:
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes(128_000):
                        content.extend(chunk)
                        if len(content) > 64_000_000:
                            raise ValueError("Master exceeds bounded response size")
                return parse_master(content.decode("utf-8-sig"))
        return self.cache.get("dhan-bond-catalogue-v1", 86400, load, max_stale=0)

    def _quote(self, routes: list[dict]) -> dict:
        key = "dhan-bond-quote-v1:" + ":".join(sorted(f"{r['exchange_segment']}/{r['security_id']}" for r in routes))

        def load():
            from ai_cio.services import holding_market_data as shared
            from ai_cio.services.sector_opportunity import _dhan_client, _live_dhan_env, _load_cached_token, resolve_dhan_auth
            creds = _live_dhan_env()
            # Preflight prevents resolve_dhan_auth from minting when no reusable
            # token exists. All failures are reported by type, never raw headers.
            if not creds["client_id"] or not (creds["access_token"] or _load_cached_token(creds["client_id"])):
                raise RuntimeError("Reusable Dhan token unavailable")
            client_id, token = resolve_dhan_auth(force_refresh=False)
            payload = {}
            for route in routes[:24]:
                payload.setdefault(route["exchange_segment"], []).append(int(route["security_id"]))
            global _last_quote
            with _bounded_lock(_quote_lock):
                # Share the existing equity history lock and request clock. Bond
                # quotes also keep their stricter one-request/second clock.
                with _bounded_lock(shared._lock):
                    wait = max(0, 1 - (time.monotonic() - _last_quote),
                               0.25 - (time.monotonic() - shared._last_request))
                    if wait:
                        time.sleep(min(wait, 1))
                    try:
                        with _dhan_client(client_id, token) as client:
                            client.timeout = httpx.Timeout(8, connect=3)
                            response = client.post(QUOTE_URL, json=payload)
                    finally:
                        _last_quote = shared._last_request = time.monotonic()
            if response.status_code != 200:
                raise RuntimeError(f"Dhan quote HTTP {response.status_code}")
            if len(response.content) > 2_000_000:
                raise ValueError("Quote exceeds bounded response size")
            body = response.json()
            if body.get("status") != "success" or not isinstance(body.get("data"), dict):
                raise ValueError("Dhan quote response did not contain a successful data object")
            quotes = {}
            for route in routes:
                segment = body["data"].get(route["exchange_segment"])
                raw = segment.get(route["security_id"]) if isinstance(segment, dict) else None
                if isinstance(raw, dict):
                    # Strict public-market allowlist: never persist headers,
                    # client IDs, access tokens or unrelated response fields.
                    quotes[route["isin"]] = {k: deepcopy(raw.get(k)) for k in (
                        "last_price", "last_trade_time", "volume", "depth", "buy_quantity", "sell_quantity")}
            return {"quotes": quotes, "provider_status": "success", "requested_instruments": len(routes),
                    "returned_instruments": len(quotes), "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "http_status": 200}
        return self.cache.get(key, 120, load, max_stale=0)

    def market_snapshot(self, products: list[dict], *, as_of: date) -> dict:
        result = {"master": {}, "quotes": {}, "sources": [], "errors": [], "status": "unavailable"}
        if os.getenv("AICIO_TESTING") == "1" and self.transport is None:
            result["errors"] = ["External Dhan access is disabled in tests; inject a provider fixture."]
            return result
        try:
            master = self._master()
            rows = master["payload"]["rows"]
            source = {"id": "bond_dhan_master", "title": "Dhan detailed instrument master", "url": MASTER_URL,
                      "observed_on": master["retrieved_at"], "sha256": master["payload"]["sha256"]}
            result["sources"].append(source)
            for product in products[:24]:
                route = next((r for r in rows if r["isin"] == product["isin"] and r["exchange"] == "NSE"
                              and r["category"] == product["category"]), None)
                if route:
                    result["master"][product["isin"]] = deepcopy(route)
            if not result["master"]:
                result["errors"].append("No verified catalogue products matched the current Dhan routing master.")
                return result
            quote = self._quote(list(result["master"].values()))
            result["quotes"] = quote["payload"]["quotes"]
            for row in result["quotes"].values():
                row["fetched_at"] = quote["payload"]["fetched_at"]
            result["sources"].append({"id": "bond_dhan_quotes", "title": "Dhan batched public market quotes",
                                      "url": "https://dhanhq.co/docs/v2/market-quote/",
                                      "observed_on": quote["retrieved_at"],
                                      "returned_instruments": len(result["quotes"])})
            result["status"] = "quotes_returned" if result["quotes"] else "empty_quote_response"
            if not result["quotes"]:
                result["errors"].append("Dhan returned no instrument rows for the requested bond quote batch; no price or entitlement cause is inferred.")
        except Exception as exc:
            result["errors"].append(f"Public bond market evidence unavailable ({type(exc).__name__}); no prices invented.")
        return result
