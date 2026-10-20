"""Cadence boundaries must not grant unverified passive-fund exceptions."""
from datetime import date, timedelta

import pytest

from ai_cio.services.mutual_funds.disclosures import validate_disclosure
from ai_cio.services.mutual_funds.freshness import disclosure_freshness

OBSERVED = date(2026, 9, 30)


@pytest.mark.parametrize("category,days,frequency", [
    ("Debt Scheme - Banking and PSU Fund", 21, "fortnightly"),
    ("Open Ended Schemes(Debt Scheme - Gilt Fund)", 21, "fortnightly"),
    ("Equity Scheme - Flexi Cap Fund", 45, "monthly"),
    ("Other Scheme - Index Funds", 45, "unverified"),
    (None, 45, "unverified"),
])
def test_category_review_boundaries_are_explicit_application_policy(category, days, frequency):
    record = {"observed_on": OBSERVED.isoformat(), "provenance": "user_supplied_source_document"}
    at_boundary = disclosure_freshness(record, as_of=OBSERVED + timedelta(days=days), scheme_category=category,
                                        category_verified=True, category_source_url="https://api.mfapi.in/mf/123456")
    after = disclosure_freshness(record, as_of=OBSERVED + timedelta(days=days + 1), scheme_category=category,
                                category_verified=True, category_source_url="https://api.mfapi.in/mf/123456")
    assert at_boundary["frequency"] == frequency
    assert at_boundary["max_age_days"] == days
    assert at_boundary["stale"] is False
    assert after["stale"] is True
    assert "application" in at_boundary["frequency_basis"].lower()
    assert at_boundary["frequency_verified"] is False


def test_unverified_category_or_passive_looking_fund_name_cannot_lengthen_cadence():
    record = {"observed_on": OBSERVED.isoformat(), "scheme_name": "Quarterly Equity Passive Index Fund"}
    result = disclosure_freshness(record, as_of=OBSERVED + timedelta(days=46),
                                  scheme_category="Debt Scheme - Gilt Fund", category_verified=False)
    assert result["frequency"] == "unverified"
    assert result["max_age_days"] == 45 and result["stale"] is True


def _cadence():
    return {"frequency": "quarterly", "asset_class": "equity", "management_style": "passive", "verified_by_adapter": True,
            "adapter": "tested_official_cadence_adapter", "source_url": "https://www.sebi.gov.in/legal/example.html",
            "basis": "Exact scheme classification and published disclosure cadence were checked by the adapter."}


def test_quarterly_exception_requires_official_adapter_metadata_and_keeps_its_source():
    record = {"observed_on": OBSERVED.isoformat(), "provenance": "official_publisher_fetched", "verified_disclosure_cadence": _cadence()}
    at_boundary = disclosure_freshness(record, as_of=OBSERVED + timedelta(days=110))
    assert at_boundary["frequency"] == "quarterly" and at_boundary["frequency_verified"] is True
    assert at_boundary["frequency_source_url"] == _cadence()["source_url"]
    assert at_boundary["max_age_days"] == 110 and at_boundary["stale"] is False
    assert disclosure_freshness(record, as_of=OBSERVED + timedelta(days=111))["stale"] is True
    record["provenance"] = "user_supplied_source_document"
    untrusted = disclosure_freshness(record, as_of=OBSERVED + timedelta(days=46))
    assert untrusted["frequency"] == "unverified" and untrusted["max_age_days"] == 45 and untrusted["stale"] is True


def test_upload_normalizer_strips_cadence_claim_instead_of_authenticating_it():
    uploaded = validate_disclosure({"scheme_code": 123456, "source_url": "https://amc.ppfas.com/example.xlsx",
                                    "observed_on": OBSERVED.isoformat(), "verified_disclosure_cadence": _cadence(),
                                    "holdings": [{"isin": "INE040A01034", "name": "HDFC Bank", "weight_pct": 10}]},
                                   as_of=OBSERVED + timedelta(days=50))
    assert "verified_disclosure_cadence" not in uploaded
    result = disclosure_freshness(uploaded, as_of=OBSERVED + timedelta(days=50))
    assert result["max_age_days"] == 45 and result["stale"] is True


def test_future_observation_is_unusable_even_with_long_review_window():
    record = {"observed_on": "2026-10-21"}
    result = disclosure_freshness(record, as_of=date(2026, 10, 20))
    assert result["stale"] is True and result["freshness_status"] == "future_observation_rejected"
