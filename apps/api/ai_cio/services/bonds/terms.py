"""Load the small independently sourced issue universe; no name-based filling."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path

from ai_cio import settings


def load_verified_terms(*, as_of: date) -> dict:
    path = Path(settings.ROOT) / "knowledge" / "bond_verified_terms.json"
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
        if date.fromisoformat(payload["verified_on"]) > as_of:
            raise ValueError("Terms snapshot was verified after the requested date")
        sources = {r["id"]: deepcopy(r) for r in payload["sources"]}
        rows, seen = [], set()
        for product in payload["products"]:
            isin = product.get("isin")
            if not isinstance(isin, str) or len(isin) != 12 or not isin.isalnum() or isin in seen:
                raise ValueError("Invalid or duplicate exact instrument identity")
            if not product.get("source_ids") or not set(product["source_ids"]).issubset(sources):
                raise ValueError("A product must reference resolved official term sources")
            date.fromisoformat(product["maturity_date"])
            seen.add(isin)
            rows.append(deepcopy(product))
        return {"products": rows, "sources": list(sources.values()), "version": payload["version"],
                "sha256": hashlib.sha256(raw).hexdigest(), "verified_on": payload["verified_on"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"products": [], "sources": [], "version": "unavailable", "sha256": None,
                "error": f"Verified issue terms unavailable ({type(exc).__name__}); no terms invented."}
