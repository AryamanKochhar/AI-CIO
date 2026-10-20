"""Disclosure review windows with explicit cadence provenance.

These are application freshness policies, not certifications of statutory
publication compliance. Fund names cannot establish a passive-fund exception.
Only a trusted official fetch adapter can supply verified cadence metadata;
the user-upload normalizer intentionally does not accept that metadata.
"""
from __future__ import annotations

from datetime import date
import re

from .disclosures import iso_date, official_url


def disclosure_freshness(disclosure: dict | None, *, as_of: date,
                         scheme_category: str | None = None,
                         category_verified: bool = False,
                         category_source_url: str | None = None) -> dict:
    record = disclosure or {}
    category = re.sub(r"\s+", " ", str(scheme_category or "")).strip()
    passive_category = bool(re.search(r"\bindex\b|\betf\b|\bpassive\b", category, re.I))
    active_debt = category_verified and not passive_category and bool(re.search(r"\bdebt\s+schemes?\b", category, re.I))
    active_equity = category_verified and not passive_category and bool(re.search(r"\bequity\s+schemes?\b", category, re.I))
    frequency = "fortnightly" if active_debt else "monthly" if active_equity else "unverified"
    max_age = 21 if active_debt else 45
    source = category_source_url if category_verified else None
    verified_frequency = False
    basis = ("Verified provider category identifies an active debt scheme; application fortnightly review window is 21 calendar days."
             if active_debt else "Verified provider category identifies active equity; application monthly review window is 45 calendar days."
             if active_equity else "Disclosure cadence is unverified. The conservative application review window is 45 calendar days; no quarterly exception is inferred from a scheme name or passive-looking category.")
    # This structure is accepted only from trusted in-process official adapters.
    # validate_disclosure() does not copy it from user-supplied JSON/documents.
    cadence = record.get("verified_disclosure_cadence")
    if (record.get("provenance") == "official_publisher_fetched" and isinstance(cadence, dict)
            and cadence.get("verified_by_adapter") is True
            and cadence.get("frequency") == "quarterly"
            and cadence.get("asset_class") == "equity"
            and cadence.get("management_style") == "passive"
            and bool(str(cadence.get("basis") or "").strip())
            and bool(str(cadence.get("adapter") or "").strip())):
        try:
            source = official_url(cadence.get("source_url"))
        except ValueError:
            pass
        else:
            frequency, max_age, verified_frequency = "quarterly", 110, True
            basis = "Trusted official adapter established equity-passive quarterly cadence: " + str(cadence["basis"]).strip() + " The 110-calendar-day freshness window is application review policy, not legal certification."
    elif (record.get("provenance") == "official_publisher_fetched"
          and record.get("adapter") == "ppfas-monthly-xlsx-v1"):
        # This narrow tested adapter checks the actual 'Monthly Portfolio
        # Statement' heading and date, rather than inferring from a fund name.
        try:
            source = official_url(record.get("source_url"))
        except ValueError:
            pass
        else:
            frequency, max_age, verified_frequency = "monthly", 45, True
            basis = "The tested official PPFAS adapter validated the monthly statement heading and observation date. The 45-calendar-day freshness window is application review policy."
    try:
        observed = iso_date(record.get("observed_on"))
    except ValueError:
        observed = None
    age = (as_of - observed).days if observed is not None else None
    stale = age < 0 or age > max_age if age is not None else None
    return {"frequency": frequency, "frequency_verified": verified_frequency,
            "frequency_source_url": source, "frequency_basis": basis,
            "max_age_days": max_age, "age_days": age, "stale": stale,
            "freshness_status": "future_observation_rejected" if age is not None and age < 0 else "stale" if stale else "current" if age is not None else "unavailable",
            "freshness_policy": "mf-disclosure-review-v1; calendar-day application windows, not statutory compliance certification"}
