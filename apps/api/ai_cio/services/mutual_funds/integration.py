"""Reconcile older portfolio views with the canonical joined MF evidence.

This is a deterministic projection of evidence already calculated by the MF
worker. It performs no fetch, LLM request, scoring, asset reclassification or
second allocation. In particular, a measured overlap is not a health score.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
import re


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None
    except (ValueError, TypeError):
        return None


def _get(analysis, key, default=None):
    return analysis.get(key, default) if isinstance(analysis, dict) else getattr(analysis, key, default)


def _set(analysis, key, value):
    if isinstance(analysis, dict):
        analysis[key] = value
    else:
        setattr(analysis, key, value)


def _mapping(analysis, key, *, create=False):
    current = _get(analysis, key)
    if not isinstance(current, dict):
        if not create:
            return None
        current = {}
        _set(analysis, key, current)
    return current


def _dated(value):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _blanket_overlap_gap(row):
    if not isinstance(row, dict):
        return False
    title = re.sub(r"[-_\s]+", " ", str(row.get("title") or "").lower())
    return "overlap" in title and any(phrase in title for phrase in ("not measured", "not available", "unavailable", "not evaluated"))


def reconcile_portfolio_analysis(analysis, mf_payload: dict) -> None:
    """Mutate AnalysisResult or a plain mapping from trusted deterministic MF data.

    Only a recognized MF result version is projected. Unknown/unavailable
    dimensions stay explicit, and existing portfolio scores and heuristic
    classification tables are preserved with their original scope identified.
    """
    if not isinstance(mf_payload, dict) or mf_payload.get("result_version") != "mf-intelligence-v1":
        return
    as_of = _dated(mf_payload.get("as_of"))
    funds = [f for f in mf_payload.get("funds", []) if isinstance(f, dict)]
    verified = {str(f.get("fund_id")): f for f in funds if f.get("identity_status") == "verified"}
    pairs = [p for p in mf_payload.get("overlaps", []) if isinstance(p, dict)]
    eligible = []
    for pair in pairs:
        if pair.get("status") not in {"supported", "partial_coverage"}:
            continue
        a, b = str(pair.get("fund_a")), str(pair.get("fund_b"))
        if a == b or a not in verified or b not in verified or as_of is None:
            continue
        dates = []
        usable = True
        for fid in (a, b):
            disclosure = verified[fid].get("disclosure") or {}
            observed = _dated(disclosure.get("observed_on"))
            max_age = _number(disclosure.get("max_age_days")) or 45
            usable = usable and disclosure.get("available") is True and disclosure.get("stale") is False and observed is not None and 0 <= (as_of - observed).days <= max_age
            dates.append(observed)
        value, ca, cb = (_number(pair.get(key)) for key in ("weighted_overlap_pct", "coverage_a_pct", "coverage_b_pct"))
        if not usable or abs((dates[0] - dates[1]).days) > 7 or value is None or ca is None or cb is None or not (0 <= value <= min(ca, cb) <= 100):
            continue
        # A duplicate/reversed pair must not inflate coverage.
        if any({str(old["fund_a"]), str(old["fund_b"])} == {a, b} for old in eligible):
            continue
        eligible.append(pair)
    expected = len(funds) * (len(funds) - 1) // 2
    full_security_coverage = bool(eligible) and all(min(float(p["coverage_a_pct"]), float(p["coverage_b_pct"])) >= 99.999999 for p in eligible)
    overlap_complete = expected > 0 and len(eligible) == expected and full_security_coverage
    measured = bool(eligible)
    maximum = max(float(p["weighted_overlap_pct"]) for p in eligible) if measured else None
    overlap = {"available": measured, "status": "complete" if overlap_complete else "partial" if measured else "unavailable",
               "result_version": mf_payload["result_version"], "as_of": mf_payload.get("as_of"),
               "pairs": deepcopy(pairs), "measured_pairs": deepcopy(eligible),
               "measured_pair_count": len(eligible), "expected_pair_count": expected,
               "pair_coverage_pct": round(len(eligible) / expected * 100, 6) if expected else None,
               "maximum_weighted_overlap_pct": maximum,
               "note": "Known overlap sums minimum full-NAV weights of common underlying ISINs. Unmeasured pairs stay unknown; partial security coverage makes a measured value a lower bound. Holdings overlap is separate from return correlation and is not a score or a sale rule."}

    combined = deepcopy(mf_payload.get("combined_exposure") or {})
    securities = [row for row in combined.get("securities", []) if isinstance(row, dict)]
    mf_known_value = sum(_number(row.get("mf_value")) or 0 for row in securities)
    mf_total = sum(_number(fund.get("known_statement_value", fund.get("valuation"))) or 0 for fund in funds)
    mf_coverage = min(mf_known_value / mf_total * 100, 100) if mf_total > 0 else None
    mf_unknown_values = any(fund.get("valuation") is None for fund in funds)
    mf_complete = bool(funds) and mf_coverage is not None and mf_coverage >= 99.999999 and not mf_unknown_values
    lookthrough = {**combined, "available": mf_known_value > 0,
                   "result_version": mf_payload["result_version"], "as_of": mf_payload.get("as_of"),
                   "mutual_fund_known_value": round(mf_known_value, 6),
                   "mutual_fund_valued_total": round(mf_total, 6),
                   "mutual_fund_coverage_pct": round(mf_coverage, 6) if mf_coverage is not None else None,
                   "mutual_fund_coverage_status": "complete" if mf_complete else "partial" if mf_known_value > 0 else "unavailable",
                   "note": str(combined.get("note") or "") + " Canonical MF evidence replaces the former blanket unavailable label. Combined investment coverage and MF-only coverage have different denominators; none implies complete sector, market-cap or country classification."}

    true_exposure = _mapping(analysis, "true_exposure", create=True)
    true_exposure["mutual_fund_lookthrough"] = lookthrough
    true_exposure["market_cap_exposure_basis"] = "Existing scheme-name/style heuristics; not underlying-security market-cap classification. Canonical MF look-through does not validate these labels."
    true_exposure["economic_themes_basis"] = "Existing name-based heuristic themes, separate from disclosed underlying security exposure."
    true_exposure["sector_exposure_basis"] = "Existing direct-stock classification/name hints retain their prior scope. AMC industry/rating columns are not silently converted to a common sector taxonomy."
    concentration = _mapping(analysis, "concentration_analysis", create=True)
    concentration["fund_overlap"] = overlap
    concentration["market_cap_concentration_basis"] = true_exposure["market_cap_exposure_basis"]
    concentration["sector_concentration_basis"] = true_exposure["sector_exposure_basis"]
    if concentration.get("geographic_concentration"):
        concentration["geographic_concentration_basis"] = "Existing domestic-statement assumption is unverified underlying geography. A domestic mutual fund can hold foreign securities; no country percentages were inferred from the wrapper or ISIN prefix."
        for row in concentration["geographic_concentration"]:
            if isinstance(row, dict):
                row["basis"] = "unverified_statement_domicile_assumption"
                row["underlying_geography_verified"] = False

    worries = _get(analysis, "top_worries")
    if isinstance(worries, list) and measured:
        _set(analysis, "top_worries", [row for row in worries if not _blanket_overlap_gap(row)])

    health = _mapping(analysis, "portfolio_health")
    if health is not None:
        components = health.setdefault("components", {})
        if isinstance(components, dict):
            components["fund_overlap"] = {"score": None, "available": measured, "status": overlap["status"],
                                          "maximum_weighted_overlap_pct": maximum,
                                          "measured_pair_count": len(eligible), "expected_pair_count": expected,
                                          "note": overlap["note"] + " This measured dimension has no validated scalar health score and remains outside the existing score average."}
        health["methodology"] = "Existing scored components retain their original calculation and scope. MF overlap is now reported from canonical dated evidence where supported; it has no scalar health score and is excluded from that average. Valuation and quality remain separately unevaluated where their feeds are absent."
    for container_name in ("financial_health", "data_gaps", "portfolio_flags", "overlap"):
        container = _mapping(analysis, container_name)
        if container is None:
            continue
        if container_name == "financial_health":
            container["mutual_fund_evidence"] = {"lookthrough_available": mf_known_value > 0, "mf_coverage_pct": lookthrough["mutual_fund_coverage_pct"], "overlap_available": measured, "measured_pairs": len(eligible), "expected_pairs": expected}
        elif container_name == "data_gaps":
            container["fund_lookthrough"] = bool(funds) and not mf_complete
            container["fund_overlap"] = expected > 0 and not overlap_complete
        elif container_name == "portfolio_flags":
            container["high_fund_overlap"] = maximum >= 50 if maximum is not None else None
            container.setdefault("thresholds", {})["fund_overlap_percent"] = "50 (application review policy; partial coverage is a lower bound)"
        else:
            container.update({"fund_overlap_available": measured, "reason": overlap["note"], "measured_pairs": deepcopy(eligible),
                              "pair_coverage_pct": overlap["pair_coverage_pct"]})
