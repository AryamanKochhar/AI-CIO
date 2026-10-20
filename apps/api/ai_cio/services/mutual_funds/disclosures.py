"""Validated, provenance-preserving disclosure and total-return imports.

An official-looking URL supplied with an upload is NOT independently verified.
Imports retain that distinction. User uploads are scoped to that user's data
directory; public documents fetched by a configured adapter are separately
identified. These functions never fetch arbitrary URLs or read caller paths.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO, BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlparse
import zipfile
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from .cache import PublicDataCache

OFFICIAL_HOSTS = (
    "amfiindia.com", "sebi.gov.in", "niftyindices.com", "nseindia.com", "bseindia.com",
    "bseindices.com", "hdfcfund.com", "icicipruamc.com", "sbimf.com", "axismf.com",
    "ppfas.com", "ppfas.in", "kotakmf.com", "nipponindiamf.com", "utimf.com",
    "dspim.com", "adityabirlacapital.com", "miraeassetmf.co.in", "franklintempletonindia.com",
    "quantmutual.com", "tataamc.com", "bandhanmutual.com", "edelweissmf.com",
    "sundarammutual.com", "canararobeco.com", "motilaloswalmf.com", "invescomutualfund.com",
)
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def number(value, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError("A finite numeric value is required")
    from math import isfinite
    result = float(str(value).strip().rstrip("%"))
    if not isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        raise ValueError("Numeric value is outside the supported range")
    return result


def iso_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError("Date must identify a calendar day")


def official_url(value: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Source URL must use HTTPS on an official publisher")
    if not any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_HOSTS):
        raise ValueError("Source URL is not on a supported official AMC, AMFI or index publisher domain")
    return text


def _stamp(payload: dict, as_of: date) -> dict:
    observed = iso_date(payload.get("observed_on"))
    if observed > as_of:
        raise ValueError("Future-dated observations cannot be imported")
    return {"source_url": official_url(payload.get("source_url")), "observed_on": observed.isoformat(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "provenance": "user_supplied_source_document",
            "verification": "Source URL and input structure validated; document not independently fetched or authenticated."}


def validate_disclosure(payload: dict, *, as_of: date | None = None) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if not isinstance(payload, dict):
        raise ValueError("A disclosure object is required")
    stamp = _stamp(payload, as_of)
    code = payload.get("scheme_code")
    if isinstance(code, bool) or not str(code or "").isdigit() or not 10000 <= int(code) <= 999999:
        raise ValueError("A valid MFAPI scheme code is required")
    scheme_isin = str(payload.get("scheme_isin") or "").upper().strip() or None
    if scheme_isin and not ISIN.fullmatch(scheme_isin):
        raise ValueError("Scheme ISIN has an invalid format")
    rows = payload.get("holdings")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise ValueError("Disclosure must contain 1 to 2000 normalized holdings")
    combined = {}
    unknown_weight = 0.0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each disclosed holding must be an object")
        weight = number(row.get("weight_pct"), minimum=0, maximum=100)
        isin = str(row.get("isin") or "").strip().upper()
        name = str(row.get("name") or "").strip()[:200]
        if not name:
            raise ValueError("Each disclosed holding needs its security name")
        if not isin:
            unknown_weight += weight
            continue
        if not ISIN.fullmatch(isin):
            raise ValueError("An underlying security has an invalid ISIN format")
        asset = str(row.get("asset_class") or "unknown").lower()
        if asset not in {"equity", "debt", "cash", "fund", "derivative", "unknown"}:
            raise ValueError("Unsupported disclosed asset class")
        if isin in combined:
            existing = combined[isin]
            if existing["asset_class"] != asset:
                raise ValueError("Duplicate security has conflicting asset classes")
            existing["weight_pct"] += weight
        else:
            combined[isin] = {"isin": isin, "name": name, "weight_pct": weight, "asset_class": asset,
                              "sector": str(row.get("sector") or "").strip()[:150] or None}
    known = sum(row["weight_pct"] for row in combined.values())
    if known + unknown_weight > 100.000001 or any(row["weight_pct"] > 100 for row in combined.values()):
        raise ValueError("Disclosed portfolio weights exceed 100%; use full scheme NAV weights. Leveraged or negative-cash gross exposures require a separate supported adapter, not renormalization.")
    if known <= 0:
        raise ValueError("At least one positive-weight identified security is required")
    if payload.get("coverage_pct") is not None and abs(number(payload["coverage_pct"], minimum=0, maximum=100) - known) > .05:
        raise ValueError("Coverage must equal the identified securities' full-NAV weights, not a renormalized sample")
    result = {**stamp, "scheme_code": int(code), "scheme_isin": scheme_isin,
              "holdings": sorted(combined.values(), key=lambda item: (-item["weight_pct"], item["isin"])),
              "coverage_pct": round(known, 6), "unidentified_weight_pct": round(unknown_weight, 6),
              "benchmark_id": str(payload.get("benchmark_id") or "")[:100] or None,
              "benchmark_name": str(payload.get("benchmark_name") or "")[:200] or None,
              "benchmark_source_url": official_url(payload["benchmark_source_url"]) if payload.get("benchmark_source_url") else None,
              "ter_percent": number(payload["ter_percent"], minimum=0, maximum=10) if payload.get("ter_percent") is not None else None,
              "exit_load": str(payload.get("exit_load") or "")[:2000] or None,
              "mandate": str(payload.get("mandate") or "")[:2000] or None,
              "riskometer": str(payload.get("riskometer") or "")[:200] or None}
    result["sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def validate_benchmark(payload: dict, *, as_of: date | None = None) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if not isinstance(payload, dict):
        raise ValueError("A benchmark object is required")
    stamp = _stamp(payload, as_of)
    benchmark_id = str(payload.get("benchmark_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not benchmark_id or len(benchmark_id) > 100 or not name or len(name) > 200:
        raise ValueError("Benchmark ID and full official name are required")
    if str(payload.get("kind") or "").lower() not in {"tri", "total_return"}:
        raise ValueError("Only an explicitly identified total-return benchmark is supported; a price index is not equivalent")
    rows = payload.get("points")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 15000:
        raise ValueError("Benchmark requires 2 to 15000 dated total-return observations")
    points = {}
    for row in rows:
        when = iso_date(row.get("date"))
        if when > iso_date(stamp["observed_on"]):
            raise ValueError("Benchmark points cannot be later than their observation date")
        value = number(row.get("value"), minimum=0.000000001)
        key = when.isoformat()
        if key in points and points[key] != value:
            raise ValueError("Conflicting benchmark values for the same day")
        points[key] = value
    result = {**stamp, "benchmark_id": benchmark_id, "name": name, "kind": "TRI",
              "points": [{"date": key, "value": points[key]} for key in sorted(points)]}
    result["sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def _scope(user_id: int | None) -> str:
    if user_id is None:
        return "public"
    if isinstance(user_id, bool) or not str(user_id).isdigit() or int(user_id) < 1:
        raise ValueError("Invalid user data scope")
    return "user:" + str(int(user_id))


def import_disclosure(payload: dict, *, cache_dir: str | Path, user_id: int | None = None,
                      as_of: date | None = None) -> dict:
    record = validate_disclosure(payload, as_of=as_of)
    scope = _scope(user_id)
    cache = PublicDataCache(Path(cache_dir) / "imports")
    key = f"{scope}:disclosure:{record['scheme_code']}"
    with cache.locked(key):
        previous = cache.read(key)
        if previous and previous["payload"].get("observed_on", "") > record["observed_on"]:
            raise ValueError("An older disclosure cannot replace a newer observation")
        cache.write(key, record)
    return {"kind": "disclosure", "scheme_code": record["scheme_code"], "observed_on": record["observed_on"],
            "sha256": record["sha256"], "coverage_pct": record["coverage_pct"], "holdings_count": len(record["holdings"]),
            "provenance": record["provenance"], "source_url": record["source_url"]}


def import_benchmark(payload: dict, *, cache_dir: str | Path, user_id: int | None = None,
                     as_of: date | None = None) -> dict:
    record = validate_benchmark(payload, as_of=as_of)
    scope = _scope(user_id)
    cache = PublicDataCache(Path(cache_dir) / "imports")
    key = f"{scope}:benchmark:{record['benchmark_id']}"
    with cache.locked(key):
        previous = cache.read(key)
        if previous and previous["payload"].get("observed_on", "") > record["observed_on"]:
            raise ValueError("An older benchmark cannot replace a newer observation")
        cache.write(key, record)
    return {"kind": "benchmark", "benchmark_id": record["benchmark_id"], "observed_on": record["observed_on"],
            "sha256": record["sha256"], "points_count": len(record["points"]),
            "provenance": record["provenance"], "source_url": record["source_url"]}


def rows_from_document(content: bytes, *, format: str) -> list[dict]:
    """Read normalized CSV/XLSX data without formulas, macros or filesystem paths.

    AMC layouts vary: their rows must explicitly identify the full-scheme NAV
    percentage. This reader accepts standardized headers, not guessed column
    positions or conversion of a market-value column into a weight.
    """
    if len(content) > 8_000_000:
        raise ValueError("Disclosure document exceeds the 8 MB bound")
    if format.lower() == "csv":
        try:
            rows = list(csv.reader(StringIO(content.decode("utf-8-sig"))))
        except UnicodeDecodeError as exc:
            raise ValueError("CSV must use UTF-8 encoding") from exc
    elif format.lower() == "xlsx":
        rows = _xlsx_rows(content)
    else:
        raise ValueError("Only normalized CSV and XLSX documents are supported")
    rows = [row for row in rows if any(str(cell).strip() for cell in row)]
    if not rows or len(rows) > 16001:
        raise ValueError("Document has no rows or exceeds the row bound")
    aliases = {"security isin": "isin", "isin code": "isin", "security name": "name",
               "name of instrument": "name", "% to net assets": "weight_pct", "% to nav": "weight_pct",
               "weight pct": "weight_pct", "asset class": "asset_class", "date": "date", "value": "value"}
    header = [aliases.get(str(x).strip().lower().replace("_", " "), str(x).strip().lower()) for x in rows[0]]
    if len(set(header)) != len(header):
        raise ValueError("Document has duplicate column headers")
    return [{key: row[i] if i < len(row) else "" for i, key in enumerate(header)} for row in rows[1:]]


def _xlsx_rows(content: bytes, *, allow_cached_formulas: bool = False) -> list[list[str]]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if len(archive.infolist()) > 1000 or sum(info.file_size for info in archive.infolist()) > 24_000_000:
                raise ValueError("Workbook expands beyond the supported size")
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(node.itertext()) for node in root.findall("s:si", NS)]
            names = sorted(name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
            if len(names) != 1:
                raise ValueError("Use a normalized single-sheet workbook")
            tree = ET.fromstring(archive.read(names[0]))
            rows = []
            for row in tree.findall(".//s:sheetData/s:row", NS):
                cells = []
                for cell in row.findall("s:c", NS):
                    if cell.find("s:f", NS) is not None and not allow_cached_formulas:
                        raise ValueError("Formula cells are not accepted; export values first")
                    reference = cell.get("r", "")
                    letters = re.match(r"[A-Z]+", reference)
                    if not letters:
                        raise ValueError("Invalid workbook cell reference")
                    column = 0
                    for char in letters.group():
                        column = column * 26 + ord(char) - 64
                    if column > 100:
                        raise ValueError("Workbook exceeds the column bound")
                    while len(cells) < column:
                        cells.append("")
                    node = cell.find("s:v", NS)
                    value = node.text or "" if node is not None else ""
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find("s:is", NS).itertext())
                    cells[column - 1] = value
                rows.append(cells)
            return rows
    except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid normalized XLSX workbook") from exc
