"""MFAPI identity/NAV, AMFI fallback, and scoped disclosure/benchmark access.

MFAPI is a convenient public aggregator, not an official NAV publisher. AMFI's
current file is an independent latest-observation fallback, never fabricated
history. mftool is not installed: its history wraps MFAPI and would not add an
independent data source. All network operations have size and time bounds.
"""
from __future__ import annotations

import csv
from datetime import date
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import threading
import time

import httpx

from .cache import PublicDataCache
from .disclosures import ISIN, _scope, iso_date, number

MFAPI_CATALOGUE = "https://api.mfapi.in/mf"
AMFI_NAV = "https://portal.amfiindia.com/spages/NAVAll.txt"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[5] / "data" / "mutual_funds"


def plan_option(name: str) -> tuple[str, str]:
    name = str(name or "").lower()
    plan = "direct" if re.search(r"\bdirect\b", name) else "regular" if re.search(r"\bregular\b", name) else "unknown"
    option = "idcw" if re.search(r"\bidcw\b|\bdividend\b|\bdiv\b|\bpayout\b|\breinvestment\b", name) else "growth" if re.search(r"\bgrowth\b", name) else "unknown"
    return plan, option


def parse_amfi(text: str) -> list[dict]:
    """Header-driven parser for both historic six-column and current 8-column file.

    AMFI added separate Plan and Option columns. Positional parsing would turn
    'Direct Plan' into NAV; that is explicitly avoided here.
    """
    rows = csv.reader(StringIO(text), delimiter=";")
    header = None
    house = None
    category = None
    output = []
    for row in rows:
        if not row or not any(cell.strip() for cell in row):
            continue
        if row[0].strip().lower() == "scheme code":
            header = {re.sub(r"\s+", " ", cell.strip().lower()): i for i, cell in enumerate(row)}
            required = {"scheme code", "scheme name", "net asset value", "date"}
            if not required <= set(header):
                raise ValueError("AMFI NAV header lacks required fields")
            continue
        if len(row) == 1:
            label = row[0].strip()
            if "mutual fund" in label.lower():
                house = label
            elif "scheme" in label.lower():
                category = label
            continue
        if not header or not row[0].strip().isdigit():
            continue
        def get(key):
            idx = header.get(key)
            return row[idx].strip() if idx is not None and idx < len(row) else ""
        try:
            nav = number(get("net asset value"), minimum=0.000000001)
            observed = iso_date(get("date"))
        except ValueError:
            continue
        name = " - ".join(x for x in (get("scheme name"), get("plan"), get("option")) if x)
        isins = [get("isin div payout/ isin growth"), get("isin div reinvestment")]
        output.append({"scheme_code": int(get("scheme code")), "scheme_name": name,
                       "fund_house": house, "scheme_category": category,
                       "isins": sorted(set(x.upper() for x in isins if ISIN.fullmatch(x.upper()))),
                       "current_nav": {"date": observed.isoformat(), "value": nav}})
    if not header:
        raise ValueError("AMFI NAV header not found")
    return output


def normalize_nav(rows: list[dict], *, as_of: date) -> list[dict]:
    if not isinstance(rows, list) or len(rows) > 20000:
        raise ValueError("NAV history has invalid size")
    values = {}
    for row in rows:
        try:
            when = iso_date(row.get("date"))
            value = number(row.get("nav", row.get("value")), minimum=0.000000001)
        except (ValueError, TypeError, AttributeError):
            continue
        if when > as_of:
            continue
        key = when.isoformat()
        if key in values and abs(values[key] - value) > 1e-9:
            raise ValueError("Conflicting NAV values for a single date")
        values[key] = value
    return [{"date": key, "value": values[key]} for key in sorted(values)]


def _catalogue_rows(payload) -> list[dict]:
    if not isinstance(payload, list) or not payload or len(payload) > 100000:
        raise ValueError("MFAPI catalogue has an unsupported shape")
    rows = []
    for row in payload:
        code = row.get("schemeCode", row.get("scheme_code"))
        if isinstance(code, bool) or not str(code or "").isdigit():
            continue
        isins = [row.get("isinGrowth", row.get("isin_growth")), row.get("isinDivReinvestment", row.get("isin_div_reinvestment"))]
        rows.append({"scheme_code": int(code), "scheme_name": row.get("schemeName", row.get("scheme_name", "")),
                     "isins": sorted(set(str(x).upper() for x in isins if x and ISIN.fullmatch(str(x).upper())))})
    return rows


class MutualFundProvider:
    def __init__(self, *, cache_dir: str | Path | None = None, user_id: int | None = None,
                 transport=None, allow_network: bool = True, max_duration_seconds: float = 24):
        self.cache_dir = Path(cache_dir or os.getenv("MUTUAL_FUND_CACHE_DIR") or DEFAULT_CACHE_DIR)
        self.user_id = user_id
        self.cache = PublicDataCache(self.cache_dir / "public")
        self.imports = PublicDataCache(self.cache_dir / "imports")
        self.transport = transport
        self.allow_network = allow_network
        self._catalogue = None
        self._catalogue_lock = threading.RLock()
        self.max_duration_seconds = max(1, min(float(max_duration_seconds), 60))
        self._network_deadline = None
        self._deadline_lock = threading.Lock()

    def begin_run(self):
        """One provider per analysis; public-cache reads remain available after budget expiry."""
        with self._deadline_lock:
            self._network_deadline = time.monotonic() + self.max_duration_seconds

    def _get(self, url: str, *, json_response: bool = True):
        if not self.allow_network:
            raise ValueError("Public market-data network access disabled")
        # Only hard-coded MFAPI/AMFI or configured official adapter URLs reach
        # this method; caller input is never interpolated into an arbitrary URL.
        with self._deadline_lock:
            if self._network_deadline is None:
                self._network_deadline = time.monotonic() + self.max_duration_seconds
            remaining = self._network_deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Mutual-fund analysis public-data time budget exhausted")
        deadline = min(time.monotonic() + 12, self._network_deadline)
        with httpx.Client(timeout=httpx.Timeout(min(6, remaining), connect=min(3, remaining)), transport=self.transport,
                          follow_redirects=False, headers={"User-Agent": "AI-cio-MF-Research/1.0"}) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                chunks = []
                length = 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 20_000_000 or time.monotonic() > deadline:
                        raise ValueError("Market-data response exceeds the size or duration bound")
                    chunks.append(chunk)
                raw = b"".join(chunks)
        return json.loads(raw) if json_response else raw

    def catalogue(self) -> list[dict]:
        with self._catalogue_lock:
            if self._catalogue is not None:
                return self._catalogue
            try:
                record = self.cache.get("mfapi:catalogue:v1", 86400,
                                        lambda: _catalogue_rows(self._get(MFAPI_CATALOGUE)), max_stale=7 * 86400)
                self._catalogue = record["payload"]
            except Exception:
                record = self.cache.get("amfi:catalogue:v2", 21600,
                                        lambda: parse_amfi(self._get(AMFI_NAV, json_response=False).decode("utf-8", errors="replace")),
                                        max_stale=7 * 86400)
                self._catalogue = record["payload"]
            return self._catalogue

    def resolve(self, holding: dict) -> dict:
        isin = str(holding.get("isin") or "").strip().upper()
        base = {"isin": isin or None, "identity_status": "unresolved", "scheme_code": None,
                "scheme_name": holding.get("scheme_name") or "Unnamed mutual fund", "plan": "unknown", "option": "unknown"}
        if not ISIN.fullmatch(isin):
            return {**base, "identity_reason": "Exact complete ISIN is missing or invalid; name-only matching is not authoritative."}
        try:
            candidates = {row["scheme_code"]: row for row in self.catalogue() if isin in row.get("isins", [])}
        except Exception:
            return {**base, "identity_reason": "Scheme catalogue could not be verified; no name-based substitution was made."}
        if len(candidates) != 1:
            return {**base, "identity_reason": "ISIN maps to no unique scheme code; verify the exact plan and option."}
        row = next(iter(candidates.values()))
        plan, option = plan_option(row["scheme_name"])
        expected_plan, expected_option = plan_option(holding.get("scheme_name", ""))
        if any(a != "unknown" and b != "unknown" and a != b for a, b in ((plan, expected_plan), (option, expected_option))):
            return {**base, "identity_status": "mismatch", "identity_reason": "ISIN catalogue plan/option conflicts with the statement label."}
        return {**base, **row, "identity_status": "verified", "plan": plan, "option": option,
                "identity_reason": "Exact ISIN matched to one scheme code; no fuzzy fund-name substitution."}

    def history(self, identity: dict, *, as_of: date) -> dict:
        code = int(identity["scheme_code"])
        url = f"{MFAPI_CATALOGUE}/{code}"
        try:
            record = self.cache.get(f"mfapi:history:{code}:v1", 21600, lambda: self._get(url), max_stale=7 * 86400)
            raw = record["payload"]
            meta = raw.get("meta") or {}
            if meta.get("scheme_code") is not None and int(meta["scheme_code"]) != code:
                raise ValueError("NAV metadata scheme code differs from resolved identity")
            isins = [meta.get("isin_growth"), meta.get("isin_div_reinvestment")]
            if any(isins) and identity["isin"] not in isins:
                raise ValueError("NAV history metadata ISIN differs from resolved identity")
            plan, option = plan_option(meta.get("scheme_name", ""))
            if any(a != "unknown" and b != "unknown" and a != b for a, b in ((plan, identity["plan"]), (option, identity["option"]))):
                raise ValueError("NAV history metadata has a different plan or option")
            points = normalize_nav(raw.get("data", []), as_of=as_of)
            if not points:
                raise ValueError("No supported dated NAV observations")
            return {"points": points, "meta": meta, "source_url": url, "retrieved_at": record["retrieved_at"],
                    "cache_status": record["cache_status"], "stale": record["stale"], "history_available": len(points) > 1,
                    "sha256": hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()}
        except Exception as error:
            # A verified identity mismatch is a hard failure. Do not hide it by
            # presenting a current AMFI quote as the rejected history.
            if isinstance(error, ValueError) and ("differs" in str(error) or "different" in str(error) or "Conflicting" in str(error)):
                return {"points": [], "history_available": False, "source_url": url, "error": str(error)}
            try:
                record = self.cache.get("amfi:catalogue:v2", 21600,
                                        lambda: parse_amfi(self._get(AMFI_NAV, json_response=False).decode("utf-8", errors="replace")),
                                        max_stale=7 * 86400)
                row = next(row for row in record["payload"] if row["scheme_code"] == code and identity["isin"] in row["isins"])
                points = [row["current_nav"]] if iso_date(row["current_nav"]["date"]) <= as_of else []
                return {"points": points, "meta": row, "source_url": AMFI_NAV, "retrieved_at": record["retrieved_at"],
                        "stale": record["stale"], "cache_status": record["cache_status"], "history_available": False,
                        "note": "AMFI current NAV only; historical performance is unavailable."}
            except Exception:
                return {"points": [], "history_available": False, "source_url": url,
                        "error": "NAV history and independent AMFI latest NAV are unavailable."}

    def _import(self, kind: str, identifier) -> dict | None:
        scopes = [_scope(self.user_id), "public"] if self.user_id is not None else ["public"]
        for scope in dict.fromkeys(scopes):
            record = self.imports.read(f"{scope}:{kind}:{identifier}")
            if record:
                return record["payload"]
        return None

    def disclosure(self, identity: dict, *, as_of: date) -> dict | None:
        imported = self._import("disclosure", identity["scheme_code"])
        if imported:
            if imported.get("scheme_isin") and imported["scheme_isin"] != identity["isin"]:
                return None
            return imported if iso_date(imported["observed_on"]) <= as_of else None
        from .official_adapters import fetch_ppfas_disclosure
        try:
            return fetch_ppfas_disclosure(self, identity, as_of=as_of)
        except Exception:
            return None

    def benchmark(self, benchmark_id: str | None, *, as_of: date) -> dict | None:
        if not benchmark_id:
            return None
        record = self._import("benchmark", benchmark_id)
        return record if record and iso_date(record["observed_on"]) <= as_of else None

    def published_comparison(self, identity: dict, *, as_of: date) -> dict | None:
        from .published_performance import fetch_ppfas_published_performance
        return fetch_ppfas_published_performance(self, identity, as_of=as_of)

    def fingerprint(self) -> str:
        return cache_fingerprint(self.user_id, cache_dir=self.cache_dir)


def cache_fingerprint(user_id: int | None = None, *, cache_dir: str | Path | None = None) -> str:
    """Cheap revision identity; excludes another user's imports and no raw PII."""
    return _evidence_fingerprint(user_id, cache_dir=cache_dir, folders=("public", "imports"))


def import_fingerprint(user_id: int | None = None, *, cache_dir: str | Path | None = None) -> str:
    """Revision of user/public imports, which analysis must never silently absorb.

    Public-provider cache population is expected during a fresh analysis. User
    imports are different inputs: a concurrent replacement must invalidate that
    analysis rather than attach its revision to previously consumed evidence.
    """
    return _evidence_fingerprint(user_id, cache_dir=cache_dir, folders=("imports",))


def _evidence_fingerprint(user_id: int | None, *, cache_dir: str | Path | None,
                          folders: tuple[str, ...]) -> str:
    root = Path(cache_dir or os.getenv("MUTUAL_FUND_CACHE_DIR") or DEFAULT_CACHE_DIR)
    digest = hashlib.sha256(b"mf-intelligence-v1")
    for folder in folders:
        directory = root / folder
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                if folder == "imports":
                    record = json.loads(path.read_text(encoding="utf-8"))
                    key = record.get("key", "")
                    allowed = ("public:",) if user_id is None else ("public:", _scope(user_id) + ":")
                    if not key.startswith(allowed):
                        continue
                stat = path.stat()
                digest.update(f"{folder}/{path.name}:{stat.st_mtime_ns}:{stat.st_size}".encode())
            except (OSError, ValueError):
                continue
    return digest.hexdigest()
