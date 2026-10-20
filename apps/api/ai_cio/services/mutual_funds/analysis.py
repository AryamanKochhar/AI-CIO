"""Twin-aware MF intelligence assembled from deterministic, dated evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from itertools import combinations
import math
import os
import re
from zoneinfo import ZoneInfo

from ai_cio.services.cashflow_math import monthly_field

from .disclosures import ISIN, iso_date, number
from .freshness import disclosure_freshness
from .metrics import correlation, investor_xirr, performance
from .provider import MutualFundProvider

RESULT_VERSION = "mf-intelligence-v1"
MAX_FUNDS = 24
DIRECT_BOND_ASSET_CLASSES = frozenset({"bond", "government_bond", "gsec", "t_bill", "treasury_bill",
                                      "sovereign_gold_bond", "sgb", "corporate_bond", "sdl"})


def _num(value, *, nonnegative=True):
    try:
        return number(value, minimum=0 if nonnegative else None)
    except (ValueError, TypeError):
        return None


def _r(value):
    return round(value, 6) if value is not None and math.isfinite(value) else None


def _equity(holding):
    return holding.get("asset_class") == "equity" or holding.get("amc") == "EQUITY"


def _finding(kind, title, detail, action, *, fund_id=None, severity="review", evidence=None,
             principles=None, source_ids=None):
    suffix = fund_id or "portfolio"
    return {"id": "mf_" + kind + ":" + str(suffix), "fund_id": fund_id, "type": kind,
            "title": title, "detail": detail, "severity": severity, "suggested_action": action,
            "evidence": evidence or {}, "principle_ids": principles or ["mf_data"],
            "source_ids": source_ids or []}


def _groups(holdings: list[dict]) -> list[dict]:
    groups = {}
    for i, holding in enumerate(holdings):
        # Explicit direct instruments belong to the parallel Bond Agent. A
        # generic 'debt' row can still be a debt fund and must remain eligible.
        if _equity(holding) or str(holding.get("asset_class") or "").strip().lower() in DIRECT_BOND_ASSET_CLASSES:
            continue
        isin = str(holding.get("isin") or "").strip().upper()
        key = isin if ISIN.fullmatch(isin) else f"unresolved:{i}"
        if key not in groups:
            groups[key] = {"fund_id": key, "rows": [], "valuation": 0.0, "valuation_known": True,
                           "scheme_name": holding.get("scheme_name") or "Unnamed mutual fund", "isin": isin or None}
        groups[key]["rows"].append(holding)
        value = _num(holding.get("valuation"))
        if value is None:
            groups[key]["valuation_known"] = False
        else:
            groups[key]["valuation"] += value
    return list(groups.values())


def _context(twin: dict, as_of: date) -> dict:
    behaviour = twin.get("behaviour") or {}
    scores = {}
    for key, value in (behaviour.get("scores") or {}).items():
        number_value = _num(value)
        scores[key] = number_value if number_value is not None and number_value <= 100 else None
    risk, loss = scores.get("risk_score"), scores.get("loss_aversion_score")
    effective = min(risk, loss) if risk is not None and loss is not None and behaviour.get("status") == "known" else None
    controls = []
    for key, action in (
        ("recency_bias_score", "Use multiple supported benchmark windows; recent returns do not justify chasing a fund."),
        ("herding_score", "Document an independent goal-and-cost rationale before adding a popular fund."),
        ("overconfidence_score", "Review aggregate underlying exposures and downside, not a belief in choosing the next winner."),
        ("anchoring_score", "Compare future suitability, exit costs and tax lots instead of waiting for an old purchase price."),
        ("decision_stability_score", "Record the review rationale and use a cooling-off review before discretionary switches."),
    ):
        score = scores.get(key)
        controls.append({"score_key": key, "score": score, "status": "not_evaluated" if score is None else "applied" if score < 35 else "no_extra_control", "rule": action})
    fp = twin.get("financial_position") or {}
    income, expenses = monthly_field(fp, "income"), monthly_field(fp, "expenses")
    constraints = twin.get("decision_constraints") or {}
    consent = _num(constraints.get("monthly_investment_budget"))
    if consent is None:
        node = fp.get("monthly_investment_budget")
        if isinstance(node, dict) and node.get("known") is not False:
            consent = _num(node.get("value"))
    surplus = max(float(income - expenses), 0) if income is not None and expenses is not None else None
    ceiling = min(consent, surplus) if consent is not None and surplus is not None else None
    other, reserve = _num(constraints.get("other_goal_monthly_commitments")), _num(constraints.get("reserve_monthly_commitment"))
    horizons = []
    for goal in (twin.get("goals") or {}).get("items", []):
        years = _num(goal.get("horizon_years"))
        if goal.get("target_date"):
            try:
                years = max((iso_date(goal["target_date"]) - as_of).days / 365.25, 0)
            except ValueError:
                pass
        if years is not None:
            horizons.append({"goal_id": goal.get("id"), "name": goal.get("name", goal.get("title", "Recorded goal")), "years": _r(years)})
    budget = {"declared_monthly_budget": consent, "positive_monthly_surplus": surplus,
              "consent_and_capacity_ceiling": ceiling, "other_goal_monthly_commitments": other,
              "reserve_monthly_commitment": reserve, "available_for_new_mf_contribution": None,
              "status": "shared_allocation_required" if ceiling is not None else "incomplete",
              "source": "standalone_twin_constraints",
              "reason": "Positive surplus is not consent. The lower of confirmed total willingness and surplus is a shared ceiling across all agents; existing goals/reserves and current SIPs must be reconciled centrally before any new MF amount. Unknown cashflow cadence is not assumed monthly."}
    central = twin.get("contribution_policy")
    if isinstance(central, dict):
        # The coordinator owns the one contribution constraint set. Do not
        # independently recompute or allocate its shared ceiling in a worker.
        budget = {"declared_monthly_budget": _num(central.get("declared_monthly_budget")),
                  "positive_monthly_surplus": _num(central.get("monthly_surplus")),
                  "consent_and_capacity_ceiling": _num(central.get("total_monthly_ceiling")),
                  "other_goal_monthly_commitments": _num(central.get("other_goal_commitments")),
                  "reserve_monthly_commitment": _num(central.get("reserve_commitment")),
                  "uncommitted_shared_monthly_ceiling": _num(central.get("uncommitted_monthly_ceiling")),
                  "earmarks_confirmed": central.get("earmarks_confirmed") is True,
                  "available_for_new_mf_contribution": None,
                  "status": central.get("status") or "incomplete", "source": "central_orchestration",
                  "reason": str(central.get("scope") or "One shared contribution policy governs all specialists.") + " The shared ceiling is not a separate MF allocation; no additional SIP amount is inferred."}
    return {"psychometrics": {"status": "applied" if effective is not None else "incomplete", "scores": scores,
                               "effective_risk_score": effective, "source": behaviour.get("source"),
                               "provenance": behaviour.get("provenance") or {}, "implementation_controls": controls,
                               "policy": "Application review policy v1 uses min(risk_score, loss_aversion_score); higher adaptive loss score means greater drawdown comfort. Values under 40 prompt risk-fit review, not an automatic sale. Behavioural controls below 35 are application thresholds, not validated clinical cutoffs."},
            "budget": budget,
            "goal_horizons": horizons}


def _analyse_fund(group, provider, as_of, twin) -> tuple[dict, dict | None, list[dict]]:
    identity = provider.resolve(group["rows"][0])
    if identity["identity_status"] == "verified" and any(provider.resolve(row)["identity_status"] != "verified" for row in group["rows"][1:]):
        identity = {**identity, "identity_status": "mismatch", "identity_reason": "Rows sharing this ISIN contain conflicting plan/option labels; reconcile the source statement."}
    base = {"fund_id": group["fund_id"], **{k: identity.get(k) for k in ("isin", "scheme_code", "scheme_name", "plan", "option", "identity_status", "identity_reason")},
            "statement_name": group["scheme_name"], "valuation": _r(group["valuation"]) if group["valuation_known"] else None,
            "known_statement_value": _r(group["valuation"]),
            "folio_count": len(set(str(row.get("folio") or "unknown") for row in group["rows"])),
            "weight_pct": None, "category": None, "result_version": RESULT_VERSION, "as_of": as_of.isoformat(),
            "metrics": performance([], as_of=as_of, option=identity.get("option", "unknown")),
            "nav_history": [], "benchmark_history": [], "findings": [], "source_ids": [],
            "published_comparison": None,
            "benchmark": {"id": None, "name": None, "kind": "TRI", "available": False, "source_url": None},
            "disclosure": {"available": False, "coverage_pct": None, **disclosure_freshness(None, as_of=as_of)},
            "ter_percent": None, "exit_load": None, "mandate": None, "riskometer": None}
    if identity["identity_status"] != "verified":
        return base, None, []
    history = provider.history(identity, as_of=as_of)
    source_id = "mf_nav_" + str(identity["scheme_code"])
    sources = [{"id": source_id, "title": "Scheme NAV history" if history.get("history_available") else "Current NAV / missing history",
                "url": history.get("source_url"), "observed_on": history["points"][-1]["date"] if history.get("points") else None,
                "retrieved_at": history.get("retrieved_at"), "sha256": history.get("sha256"),
                "publisher_type": "public_aggregator" if "mfapi.in" in history.get("source_url", "") else "official_publisher"}]
    base["source_ids"].append(source_id)
    base["nav_history"] = history.get("points", [])
    base["category"] = (history.get("meta") or {}).get("scheme_category") or identity.get("scheme_category")
    base["disclosure"].update(disclosure_freshness(None, as_of=as_of, scheme_category=base["category"],
                                                   category_verified=True, category_source_url=history.get("source_url")))
    base["nav_quality"] = {"available": bool(history.get("points")), "history_available": history.get("history_available", False),
                           "stale_cache": history.get("stale", False), "cache_status": history.get("cache_status"),
                           "last_observation": history["points"][-1]["date"] if history.get("points") else None,
                           "note": history.get("note") or history.get("error")}
    base["nav_quality"]["stale_observation"] = (as_of - iso_date(history["points"][-1]["date"])).days > 10 if history.get("points") else None
    disclosure = provider.disclosure(identity, as_of=as_of)
    benchmark = None
    if disclosure:
        freshness = disclosure_freshness(disclosure, as_of=as_of, scheme_category=base["category"],
                                         category_verified=True, category_source_url=history.get("source_url"))
        dsid = "mf_disclosure_" + str(identity["scheme_code"])
        base["source_ids"].append(dsid)
        sources.append({"id": dsid, "title": "Disclosed scheme portfolio", "url": disclosure["source_url"],
                        "observed_on": disclosure["observed_on"], "retrieved_at": disclosure.get("retrieved_at"),
                        "sha256": disclosure.get("sha256"), "provenance": disclosure.get("provenance"),
                        "verification": disclosure.get("verification")})
        base["disclosure"] = {"available": True, "observed_on": disclosure["observed_on"], "source_url": disclosure["source_url"],
                              "sha256": disclosure.get("sha256"), "coverage_pct": disclosure["coverage_pct"], **freshness,
                              "provenance": disclosure.get("provenance"), "verification": disclosure.get("verification"),
                              "method": "Cadence-specific application review window with source and basis shown; missing cash/unsupported instruments remain unknown.",
                              "holdings_count": len(disclosure["holdings"])}
        for key in ("ter_percent", "exit_load", "mandate", "riskometer"):
            base[key] = disclosure.get(key)
        benchmark = provider.benchmark(disclosure.get("benchmark_id"), as_of=as_of)
        base["benchmark"].update({"id": disclosure.get("benchmark_id"), "name": disclosure.get("benchmark_name"),
                                  "source_url": disclosure.get("benchmark_source_url")})
    # Published trailing tables are evidence in their own right, but do not
    # supply an independent benchmark series, precise start dates or rolling
    # consistency. Keep them separate from the calculated NAV/TRI metrics.
    published = provider.published_comparison(identity, as_of=as_of) if hasattr(provider, "published_comparison") else None
    if published and published.get("available"):
        base["published_comparison"] = published
        pid = published["source_id"]
        base["source_ids"].append(pid)
        sources.append({"id": pid, "title": "AMC published plan performance comparison",
                        "url": published["source_url"], "observed_on": published["observed_on"],
                        "retrieved_at": published.get("retrieved_at"), "sha256": published.get("sha256"),
                        "provenance": "official_publisher_fetched",
                        "verification": "Configured scheme ISIN, scheme panel, plan column, observation month and disclosed benchmark validated. The table does not state its option basis or exact starting market dates."})
        published_benchmark = published.get("benchmark") or {}
        if not base["benchmark"].get("id") and not published.get("stale"):
            base["benchmark"].update({key: published_benchmark.get(key) for key in ("id", "name", "kind", "source_url")})
            base["benchmark"]["identity_source"] = "official_amc_published_comparison"
            benchmark = provider.benchmark(published_benchmark.get("id"), as_of=as_of)
        elif base["benchmark"].get("id") and published_benchmark.get("id") != base["benchmark"]["id"]:
            base["benchmark"]["identity_conflict"] = True
            base["benchmark"]["identity_note"] = "Uploaded disclosure benchmark differs from the configured official factsheet; reconcile benchmark mandate and dates before relative analysis."
            benchmark = None
    if benchmark:
        base["benchmark"] = {"id": benchmark["benchmark_id"], "name": benchmark["name"], "kind": benchmark["kind"],
                              "available": True, "source_url": benchmark["source_url"],
                              "observed_on": benchmark["observed_on"], "provenance": benchmark.get("provenance"),
                              "verification": benchmark.get("verification")}
        base["benchmark_history"] = benchmark["points"]
        bsid = "mf_benchmark_" + benchmark["benchmark_id"]
        base["source_ids"].append(bsid)
        sources.append({"id": bsid, "title": benchmark["name"], "url": benchmark["source_url"],
                        "observed_on": benchmark["observed_on"], "retrieved_at": benchmark.get("retrieved_at"),
                        "sha256": benchmark.get("sha256"), "provenance": benchmark.get("provenance"),
                        "verification": benchmark.get("verification")})
    passive = bool(re.search(r"\bindex\b|\betf\b", (base["category"] or "") + " " + base["scheme_name"], re.I))
    base["passive"] = passive
    base["metrics"] = performance(base["nav_history"], base["benchmark_history"], as_of=as_of,
                                   option=base["option"], passive=passive)
    transactions = [t for t in (twin.get("portfolio") or {}).get("transactions", [])
                    if str(t.get("isin") or "").strip().upper() == identity["isin"]]
    # The terminal date belongs to the statement valuation, not today's quote.
    terminal_dates = {row.get("valuation_date") for row in group["rows"]}
    valuation_date = next(iter(terminal_dates)) if len(terminal_dates) == 1 else None
    xirr_result = investor_xirr(transactions, valuation=base["valuation"], valuation_date=valuation_date,
                                complete=(twin.get("portfolio") or {}).get("transactions_complete") is True)
    base["metrics"]["xirr_pct"] = xirr_result["xirr_pct"]
    base["metrics"]["investor_return"] = xirr_result
    return base, disclosure, sources


def _fund_findings(fund, context):
    out = []
    fid = fund["fund_id"]
    if fund["identity_status"] != "verified":
        return [_finding("identity_gap", "Verify the exact fund identity", fund["identity_reason"],
                         "Upload the complete ISIN and exact plan/option from the statement.", fund_id=fid,
                         severity="warning", principles=["mf_identity", "mf_data"],
                         evidence={"isin": fund["isin"], "statement_name": fund["statement_name"], "identity_status": fund["identity_status"]})]
    if not fund["benchmark"]["available"]:
        out.append(_finding("benchmark_gap", "Benchmark comparison needs verified data",
                            "Fund NAV growth can be calculated independently, but no matched total-return benchmark history is available. A price index is not substituted.",
                            "Import the scheme's disclosed benchmark and its official total-return series before judging relative performance.",
                            fund_id=fid, severity="info", principles=["mf_benchmark", "mf_data"], source_ids=fund["source_ids"]))
    if (fund.get("published_comparison") or {}).get("available"):
        published = fund["published_comparison"]
        out.append(_finding("published_performance_context", "Inspect the AMC's reported benchmark comparison",
                            "The official factsheet supplies a matched plan/benchmark trailing comparison. Its option basis and exact starting market dates are not stated, so it remains separate from independently calculated Growth NAV/TRI metrics and cannot establish rolling consistency.",
                            "Read the source table and its limitations; obtain an authorised matched benchmark series before judging persistent relative performance.",
                            fund_id=fid, severity="info", principles=["mf_benchmark", "mf_persistence", "mf_data"],
                            evidence={"basis": published["basis"], "observed_on": published["observed_on"],
                                      "returns": published["returns"], "option_basis": published["option_basis"],
                                      "stale": published.get("stale"), "limitations": published.get("limitations", [])},
                            source_ids=[published["source_id"]]))
    if not fund["disclosure"]["available"] or fund["disclosure"].get("stale"):
        out.append(_finding("disclosure_gap", "Underlying holdings need a current disclosure",
                            "No usable current holdings snapshot is available; underlying security exposure is unknown rather than zero.",
                            "Import the AMC monthly portfolio with its observation date and full-NAV security weights.",
                            fund_id=fid, severity="info", principles=["mf_overlap", "mf_data"],
                            evidence={"disclosure": fund["disclosure"]}, source_ids=fund["source_ids"]))
    metrics = fund["metrics"]
    compared = [r for r in metrics["returns"] if r.get("excess_return_pp") is not None]
    rolling = metrics["rolling"]
    recent_comparison = any(row.get("end_date") and (iso_date(fund["as_of"]) - iso_date(row["end_date"])).days <= 45 for row in compared)
    if recent_comparison and rolling.get("observations", 0) >= 12 and rolling.get("median_excess_pp") is not None:
        negative = [r for r in compared if r["excess_return_pp"] < 0]
        positive = [r for r in compared if r["excess_return_pp"] > 0]
        if len(negative) >= 2 and rolling["median_excess_pp"] < 0 and rolling.get("outperformance_pct", 100) < 50:
            out.append(_finding("persistent_underperformance", "Review repeated benchmark shortfalls",
                                "At least two supported matched periods lag the disclosed TRI, and most supported rolling windows also lag. This is a review screen, not proof of future underperformance.",
                                "Review mandate, management, costs and goal fit; obtain tax lots and exit conditions before assessing a switch.",
                                fund_id=fid, principles=["mf_persistence", "mf_benchmark", "mf_tax_scope"],
                                evidence={"compared_periods": compared, "rolling": rolling, "threshold_basis": "Application review policy v1: at least 2 negative matched periods, >=12 rolling observations, median excess <0, outperformance <50%. Overlapping windows are not independent."}, source_ids=fund["source_ids"]))
        elif len(positive) >= 2 and rolling["median_excess_pp"] > 0 and rolling.get("outperformance_pct", 0) > 50:
            out.append(_finding("persistent_outperformance", "Supported benchmark-relative strength",
                                "At least two matched periods and the median rolling window exceeded the disclosed TRI. Historical strength does not establish future returns or suitability.",
                                "Retain this evidence in the scheduled review and check goal fit before adding money.",
                                fund_id=fid, severity="info", principles=["mf_persistence", "mf_benchmark", "mf_suitability"],
                                evidence={"compared_periods": compared, "rolling": rolling}, source_ids=fund["source_ids"]))
    effective = context["psychometrics"]["effective_risk_score"]
    risk_name = (fund.get("category") or "") + " " + fund["scheme_name"]
    if effective is not None and effective < 40 and re.search(r"small\s*cap|mid\s*cap", risk_name, re.I):
        out.append(_finding("psychometric_suitability", "Check volatile-fund exposure against drawdown comfort",
                            "This small/mid-cap fund needs a risk-fit review because the lower of recorded risk willingness and adaptive loss score is below the application's 40/100 review threshold.",
                            "Review the fund's share of the whole portfolio and near-term goal funding; keep a written rationale before discretionary changes.",
                            fund_id=fid, principles=["mf_suitability", "portfolio_reconcile"],
                            evidence={"effective_risk_score": effective, "scores": context["psychometrics"]["scores"], "category": fund.get("category"), "threshold_basis": "Application review policy; not a regulatory cutoff or automatic sell rule."}, source_ids=fund["source_ids"]))
    equity_category = bool(re.search(r"equity|small\s*cap|mid\s*cap|flexi\s*cap|elss|nifty", risk_name, re.I))
    short_goals = [g for g in context["goal_horizons"] if g["years"] <= 3]
    if equity_category and short_goals:
        out.append(_finding("goal_horizon_review", "Separate near-term spending from equity-fund risk",
                            "Recorded goals due within three years coexist with equity-fund exposure. The system does not know which holdings are earmarked to each goal.",
                            "Confirm goal earmarks and accessible reserves centrally before allocating more to this fund.",
                            fund_id=fid, principles=["mf_suitability", "portfolio_reconcile"],
                            evidence={"goal_horizons": short_goals, "category": fund.get("category"), "threshold_basis": "Three-year application review horizon; no fund-to-goal earmark has been assumed."}, source_ids=fund["source_ids"]))
    if fund["plan"] == "regular":
        out.append(_finding("regular_plan_cost_review", "Compare the equivalent Direct plan's net costs",
                            "This holding is a Regular plan. No verified equivalent-plan TER difference or adviser-service value has been quantified, so a saving is not invented.",
                            "Compare the same scheme, mandate and option; include service needs, exit load and tax before choosing any switch.",
                            fund_id=fid, severity="info", principles=["mf_costs", "mf_tax_scope"],
                            evidence={"plan": fund["plan"], "option": fund["option"], "ter_percent": fund["ter_percent"]}, source_ids=fund["source_ids"]))
    return out


def _overlap(left, right, a, b):
    base = {"fund_a": left["fund_id"], "fund_b": right["fund_id"], "weighted_overlap_pct": None,
            "common_securities": [], "coverage_a_pct": a.get("coverage_pct") if a else None,
            "coverage_b_pct": b.get("coverage_pct") if b else None, "status": "unavailable",
            "method": "Sum of min(weight A, weight B) for common underlying ISINs; full-NAV percentage weights, never renormalized."}
    if not a or not b:
        return base
    if left["disclosure"].get("stale") or right["disclosure"].get("stale"):
        return {**base, "status": "stale_disclosure"}
    if abs((iso_date(a["observed_on"]) - iso_date(b["observed_on"])).days) > 7:
        return {**base, "status": "unaligned_disclosure_dates"}
    amap = {row["isin"]: row for row in a["holdings"]}
    bmap = {row["isin"]: row for row in b["holdings"]}
    common = [{"isin": isin, "name": amap[isin]["name"], "weight_a_pct": amap[isin]["weight_pct"],
               "weight_b_pct": bmap[isin]["weight_pct"], "overlap_pct": _r(min(amap[isin]["weight_pct"], bmap[isin]["weight_pct"]))}
              for isin in sorted(set(amap) & set(bmap))]
    return {**base, "weighted_overlap_pct": _r(sum(row["overlap_pct"] for row in common)),
            "common_securities": sorted(common, key=lambda row: -row["overlap_pct"]),
            "observed_on_a": a["observed_on"], "observed_on_b": b["observed_on"],
            "status": "supported" if min(a["coverage_pct"], b["coverage_pct"]) >= 95 else "partial_coverage",
            "note": "Measured known-security overlap is a lower bound when disclosure coverage is partial; it is not a correlation or a diversification guarantee."}


def _lookthrough(holdings, funds, disclosures):
    securities = {}
    known_value = 0.0
    total = 0.0
    missing_values = 0
    unmapped = 0.0
    def add(isin, name, value, kind, sector=None):
        entry = securities.setdefault(isin, {"isin": isin, "name": name, "direct_value": 0.0, "mf_value": 0.0, "total_value": 0.0, "portfolio_weight_pct": None, "sector": sector})
        entry[kind] += value
        entry["total_value"] += value
    for holding in holdings:
        value = _num(holding.get("valuation"))
        if value is None:
            missing_values += 1
            continue
        total += value
        if _equity(holding):
            isin = str(holding.get("isin") or "").strip().upper()
            if ISIN.fullmatch(isin):
                add(isin, holding.get("scheme_name") or isin, value, "direct_value")
                known_value += value
            else:
                unmapped += value
        elif str(holding.get("asset_class") or "").strip().lower() in DIRECT_BOND_ASSET_CLASSES:
            # This specialist does not estimate bond issuer/duration exposures.
            # The Bond Agent owns those measurements; retain the denominator.
            unmapped += value
    # MF wrappers are not added again as exposure rows. Their disclosed
    # securities replace only the known slice; residual wrapper value is unknown.
    for fund in funds:
        value = fund.get("known_statement_value", fund["valuation"])
        if value is None:
            continue
        disclosure = disclosures.get(fund["fund_id"])
        if not disclosure or fund["disclosure"].get("stale"):
            unmapped += value
            continue
        mapped = 0.0
        for row in disclosure["holdings"]:
            amount = value * row["weight_pct"] / 100
            add(row["isin"], row["name"], amount, "mf_value", row.get("sector"))
            mapped += amount
        known_value += mapped
        unmapped += max(value - mapped, 0)
    for row in securities.values():
        for key in ("direct_value", "mf_value", "total_value"):
            row[key] = _r(row[key])
        row["portfolio_weight_pct"] = _r(row["total_value"] / total * 100) if total > 0 else None
    return {"status": "complete" if missing_values == 0 and unmapped < .01 and total > 0 else "partial" if known_value > 0 else "unavailable",
            "known_coverage_pct": _r(min(known_value / total * 100, 100)) if total > 0 else None,
            "known_value": _r(known_value), "portfolio_value": _r(total), "unmapped_value": _r(unmapped),
            "holdings_with_unknown_valuation": missing_values,
            "securities": sorted(securities.values(), key=lambda row: -row["total_value"]),
            "note": "Denominator is valued statement investment holdings only, excluding cash/FD balances outside that portfolio. Direct securities and each known MF underlying slice are counted once. Disclosure weights are applied to statement valuations and can have different observation dates; this is indicative disclosed exposure, not a current executable position. Unknown security, cash and unsupported nested/derivative exposures remain unmapped; missing valuations prevent complete coverage."}


def analyse_mutual_funds(twin: dict, *, provider=None, as_of: date | None = None) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if not isinstance(as_of, date):
        as_of = iso_date(as_of)
    provider = provider or MutualFundProvider(user_id=(twin.get("user") or {}).get("id"),
                                             allow_network=os.getenv("AICIO_TESTING") != "1")
    if hasattr(provider, "begin_run"):
        provider.begin_run()
    holdings = (twin.get("portfolio") or {}).get("holdings") or []
    groups = _groups(holdings)
    context = _context(twin, as_of)
    quality = {**context, "warnings": [], "missing": []}
    if len(groups) > MAX_FUNDS:
        quality["warnings"].append(f"Deep data enrichment is bounded to the first {MAX_FUNDS} distinct funds; all remaining values stay in unknown exposure.")
    def run(group):
        try:
            return _analyse_fund(group, provider, as_of, twin)
        except Exception:
            # One malformed provider cannot cancel another specialist or fund.
            base = {"fund_id": group["fund_id"], "isin": group["isin"], "scheme_name": group["scheme_name"], "statement_name": group["scheme_name"],
                    "scheme_code": None, "identity_status": "unresolved", "identity_reason": "This fund's provider data failed validation; no metrics were fabricated.",
                    "plan": "unknown", "option": "unknown", "valuation": _r(group["valuation"]) if group["valuation_known"] else None,
                    "known_statement_value": _r(group["valuation"]),
                    "weight_pct": None, "category": None, "metrics": performance([], as_of=as_of, option="unknown"),
                    "nav_history": [], "benchmark_history": [], "source_ids": [], "findings": [], "ter_percent": None,
                    "published_comparison": None,
                    "benchmark": {"available": False, "id": None, "name": None, "kind": "TRI", "source_url": None},
                    "disclosure": {"available": False, "coverage_pct": None, **disclosure_freshness(None, as_of=as_of)}, "result_version": RESULT_VERSION, "as_of": as_of.isoformat()}
            return base, None, []
    # Four bounded public-data workers; the caller's database Session is never
    # shared. Per-key cache single-flight avoids duplicate catalogue requests.
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="mf-data") as executor:
        results = list(executor.map(run, groups[:MAX_FUNDS]))
    funds, disclosures, sources = [], {}, {}
    all_value = sum(_num(h.get("valuation")) or 0 for h in holdings)
    for fund, disclosure, fund_sources in results:
        if fund["valuation"] is not None and all_value > 0:
            fund["weight_pct"] = _r(fund["valuation"] / all_value * 100)
        fund["findings"] = _fund_findings(fund, context)
        funds.append(fund)
        if (fund.get("nav_quality") or {}).get("stale_observation"):
            quality["warnings"].append(f"{fund['scheme_name']}: latest NAV observation is more than 10 calendar days old under application freshness policy; metrics retain their historical observation date.")
        if disclosure:
            disclosures[fund["fund_id"]] = disclosure
        for source in fund_sources:
            sources[source["id"]] = source
    # Bounded-out funds remain explicit rather than disappearing from totals.
    for group in groups[MAX_FUNDS:]:
        fund, _, _ = run({**group, "rows": [{**group["rows"][0], "isin": None}]})
        fund["identity_reason"] = "Deep enrichment deferred by the per-request fund count bound."
        fund["findings"] = _fund_findings(fund, context)
        funds.append(fund)
    overlaps, correlations = [], []
    findings = [finding for fund in funds for finding in fund["findings"]]
    for left, right in combinations(funds[:MAX_FUNDS], 2):
        overlap = _overlap(left, right, disclosures.get(left["fund_id"]), disclosures.get(right["fund_id"]))
        overlaps.append(overlap)
        corr = correlation(left["nav_history"], right["nav_history"], as_of=as_of) if left["option"] == right["option"] == "growth" else {"correlation": None, "observations": 0, "frequency": "monthly", "status": "distribution_adjustment_required", "start_date": None, "end_date": None}
        corr.update({"fund_a": left["fund_id"], "fund_b": right["fund_id"]})
        correlations.append(corr)
        pair = left["fund_id"] + ":" + right["fund_id"]
        if overlap["weighted_overlap_pct"] is not None and overlap["weighted_overlap_pct"] >= 50:
            findings.append(_finding("overlap_review", "Review duplicated underlying holdings",
                                     "Known weighted security overlap exceeds the application's 50% review threshold. The mandates and goal roles may still differ.",
                                     "Compare fund roles, costs and tax/exit conditions before consolidating; first review future contributions rather than assume an immediate sale.",
                                     fund_id=pair, principles=["mf_overlap", "portfolio_lookthrough", "mf_tax_scope"],
                                     evidence={**overlap, "threshold_basis": "Application review threshold 50%; not a regulator-prescribed limit."}, source_ids=left["source_ids"] + right["source_ids"]))
        if corr.get("correlation") is not None and corr["correlation"] >= .9:
            findings.append(_finding("correlation_review", "Review funds with similar historical behaviour",
                                     "Aligned completed-month return correlation exceeds the application's 0.90 review threshold. Correlation can change and is separate from holdings overlap.",
                                     "Check whether the pair adds a distinct goal or risk role before adding another SIP.",
                                     fund_id=pair, severity="info", principles=["mf_correlation", "mf_suitability"],
                                     evidence={**corr, "threshold_basis": "Application review threshold 0.90, minimum 12 common months; no diversification guarantee."}, source_ids=left["source_ids"] + right["source_ids"]))
    combined = _lookthrough(holdings, funds, disclosures)
    if context["psychometrics"]["status"] != "applied":
        quality["missing"].append("Complete recorded risk willingness and adaptive loss score for personalized MF suitability.")
    if context["budget"]["consent_and_capacity_ceiling"] is None:
        quality["missing"].append("Confirmed monthly investment willingness and complete cashflow for any contribution amount.")
    if (twin.get("portfolio") or {}).get("transactions_complete") is not True and groups:
        quality["missing"].append("Complete inception/opening transaction history for investor XIRR; a statement-period subset is insufficient.")
    verified = sum(f["identity_status"] == "verified" for f in funds)
    nav_count = sum(bool(f["nav_history"]) for f in funds)
    disclosure_count = sum(f["disclosure"]["available"] and not f["disclosure"].get("stale") for f in funds)
    benchmark_count = sum(f["benchmark"]["available"] for f in funds)
    published_count = sum(bool((f.get("published_comparison") or {}).get("available")) for f in funds)
    quality["coverage"] = {"funds": len(funds), "verified_identities": verified, "nav_available": nav_count,
                           "current_holdings_disclosures": disclosure_count, "benchmark_series": benchmark_count,
                           "published_comparisons": published_count,
                           "return_comparable_growth_options": sum(f["option"] == "growth" for f in funds)}
    if groups and verified < len(groups):
        quality["warnings"].append("Unresolved fund identities retain their statement values but have no substituted NAV, benchmark or holdings.")
    if disclosure_count < len(funds):
        quality["missing"].append("Current official holdings disclosure for some funds; unknown exposure is not zero.")
    if benchmark_count < len(funds):
        quality["missing"].append("Disclosed benchmark identity and official matched total-return history for some funds.")
    complete = bool(funds) and verified == nav_count == disclosure_count == benchmark_count == len(funds) and not quality["missing"]
    status = "complete" if complete else "partial" if funds else "unavailable"
    return {"result_version": RESULT_VERSION, "available": bool(funds), "agent": "mutual_fund_agent",
            "status": status, "as_of": as_of.isoformat(),
            "summary": f"Reviewed {len(funds)} distinct mutual funds: {verified} exact identities, {nav_count} NAV series/quotes, {disclosure_count} current disclosures, {benchmark_count} benchmark series and {published_count} separate AMC-reported comparisons. Missing inputs remain unevaluated." if funds else "No mutual fund holdings are recorded in the Digital Financial Twin.",
            "funds": funds, "overlaps": overlaps, "correlations": correlations, "combined_exposure": combined,
            "findings": findings, "data_quality": quality, "sources": list(sources.values()),
            "methods": {"overlap": "sum(min(full-NAV security weight A, full-NAV security weight B)) by exact underlying ISIN",
                        "correlation": "Pearson correlation of aligned completed-month NAV returns; >=12 observations, up to 60",
                        "performance": "Matched total-return benchmark dates; >1y CAGR, 1y absolute. NAV already reflects scheme expenses.",
                        "investor_return": "Annual XIRR from complete dated external cashflows and same-scope terminal valuation, never NAV CAGR",
                        "action_policy": "Deterministic review findings only. No automatic fund sales, broker execution, predicted winner, guaranteed return or probability of future outperformance."}}
