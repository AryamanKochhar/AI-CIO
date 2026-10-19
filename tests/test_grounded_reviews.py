from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP

import pytest

from ai_cio import settings
from ai_cio.services.agents.decision_suggestions import build_decision_suggestions
from ai_cio.services.demo_personas import launch_persona
from ai_cio.services.grounded_reviews import build_grounded_reviews, calculation, number
from ai_cio.services.skill_principles import PRINCIPLES, resolve_principle
from ai_cio.services.twin import assemble_twin


def reviewed(db, persona):
    launched = launch_persona(db, persona)
    twin = assemble_twin(db, launched["user"].id)
    bits = {"specialist_checks":{"tax":{"available":True,"rule_version":"fixture-rule","financial_year":"2026-27","summary":{"realized_gains":"10"},"missing_data":[{"security":"Fixture debt record","reason":"missing buy date"}]}},
            "holding_market_data":{"available":True,"holdings":[{"symbol":{"tom":"TCS","maya":"INFY","arjun":"LT"}[persona],"as_of":"2026-10-16","indicators":{"return_20d":"9.69","rsi_14":"69.8"}}]}}
    return twin, bits, build_decision_suggestions(twin=twin,analysis_bits=bits,sector_opportunity={})


def test_all_principles_resolve_to_actual_section_and_line_range():
    for identifier in PRINCIPLES:
        p = resolve_principle(identifier)
        assert p is not None
        text = (settings.ROOT / p["path"]).read_text(encoding="utf-8-sig")
        assert p["excerpt"] in "\n".join(text.splitlines()[p["line_start"]-1:p["line_end"]])
        assert f"## {p['section']}" in text
        assert len(p["skill_sha256"]) == 64
    assert resolve_principle("invented-book-page") is None


def test_changed_skill_excerpt_fails_closed(tmp_path,monkeypatch):
    from ai_cio.services import skill_principles
    skill,section,excerpt = PRINCIPLES["liquidity"]
    path = tmp_path/".cursor"/"skills"/skill/"SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"# Guide\n## {section}\nA changed principle, not the expected excerpt.\n")
    monkeypatch.setattr(skill_principles.settings,"ROOT",tmp_path)
    assert resolve_principle("liquidity") is None


@pytest.mark.parametrize("persona,first_theme",[("tom","retirement"),("maya","liquidity"),("arjun","goals")])
def test_personas_have_distinct_leading_reviews_and_no_synonym_filler(db,persona,first_theme):
    _,_,result = reviewed(db,persona)
    items = result["items"]
    assert items[0]["theme"] == first_theme
    assert len(items) == len({r["theme"] for r in items}) <= 8
    assert sum(r["theme"] == "concentration" for r in items) <= 1
    assert len({r["theme"] for r in items[:4]}) == 4
    assert sum(Decimal(str(r["relative_support_percent"])) for r in items) == 100
    assert result["ai_used"] is False
    for row in items:
        assert row["proof"]["principles"]
        assert row["proof"]["facts"]
        assert row["action"]["href"].startswith(("/","#"))
        assert row["calibrated_probability"] is False


def test_published_derivations_are_independently_reproducible(db):
    _,_,result = reviewed(db,"arjun")
    for row in result["items"]:
        for calc in row["proof"]["calculations"]:
            xs = [Decimal(x) for x in calc["operands"]]
            operation = calc["operation"]
            expected = xs[0]-xs[1] if operation == "difference" else max(xs[0]-xs[1],0) if operation == "positive_gap" else sum(xs) if operation == "sum" else xs[0]/xs[1]*(100 if operation == "percent" else 1)
            assert Decimal(calc["result"]) == expected.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)


def test_shared_budget_does_not_subtract_emi_twice_or_assign_surplus_to_each_goal(db):
    _,_,result = reviewed(db,"arjun")
    goal = next(r for r in result["items"] if r["theme"] == "goals")
    calculations = goal["proof"]["calculations"]
    assert next(c["result"] for c in calculations if c["label"] == "Recorded monthly surplus") == "55000.00"
    combined = next(c for c in calculations if c["label"] == "Combined no-return monthly baseline")
    assert len(combined["operands"]) == 3
    assert Decimal(combined["result"]) > 55000
    assert "not a minimum contribution" in " ".join(goal["proof"]["assumptions"])


def test_annual_cadence_is_normalized_and_its_derivation_is_visible(db):
    twin,bits,monthly = reviewed(db,"arjun")
    annual = deepcopy(twin)
    annual["financial_position"]["cashflow_cadence"] = "annual"
    for name in ("income","expenses"):
        annual["financial_position"][name]["value"] = str(Decimal(annual["financial_position"][name]["value"])*12)
    result = build_grounded_reviews(annual,bits)
    goals = next(r for r in result["items"] if r["theme"] == "goals")
    assert next(c["result"] for c in goals["proof"]["calculations"] if c["label"] == "Recorded monthly surplus") == "55000.00"
    assert sum(c["label"].startswith("Normalize annual") for c in goals["proof"]["calculations"]) == 2


def test_unknown_cadence_does_not_manufacture_monthly_capacity(db):
    twin,bits,_ = reviewed(db,"maya")
    twin["financial_position"].pop("cashflow_cadence")
    result = build_grounded_reviews(twin,bits)
    assert not any(r["theme"] in {"debt","goals"} for r in result["items"])
    assert not any(c["label"] == "Cash / recorded outgoings" for r in result["items"] for c in r["proof"]["calculations"])


def test_empty_context_requests_inputs_instead_of_inventing_numbers():
    result = build_grounded_reviews({})
    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["theme"] == "data"
    assert row["proof"]["calculations"] == []
    assert row["proof"]["missing_information"]


def test_missing_sources_never_fall_back_to_uncited_action_items(monkeypatch):
    from ai_cio.services import grounded_reviews
    monkeypatch.setattr(grounded_reviews,"applied_principles",lambda ids: [])
    result = build_decision_suggestions(twin={},analysis_bits={},sector_opportunity={})
    assert result["items"] == []
    assert result["available"] is False
    assert result["coverage"]["rejected"]


def test_tax_gaps_are_not_zero_liability_and_deposit_eligibility_is_not_assumed(db):
    _,_,result = reviewed(db,"tom")
    tax = next(r for r in result["items"] if r["theme"] == "tax")
    assert tax["proof"]["calculations"] == []
    assert any("not zero tax" in s for s in tax["proof"]["assumptions"])
    fd = next(r for r in result["items"] if r["theme"] == "fd")
    assert "no covered/uncovered balance is calculated" in fd["proof"]["conclusion"]
    assert "Ownership/right/capacity" in fd["proof"]["missing_information"]


@pytest.mark.parametrize("value",[float("nan"),float("inf"),True,"NaN",None])
def test_non_finite_and_boolean_values_are_not_financial_inputs(value):
    assert number(value) is None


def test_calculations_require_a_positive_denominator():
    with pytest.raises(ValueError): calculation("coverage","ratio",[Decimal(5),Decimal(0)],unit="months",formula="cash/outgoings")


def test_source_endpoint_has_an_allowlist(client):
    result = client.get("/knowledge/principles/liquidity")
    assert result.status_code == 200
    assert result.json()["integrity"] == "exact_section_excerpt_verified"
    assert client.get("/knowledge/principles/unknown-file").status_code == 404


def test_annual_normalization_reaches_trajectory_and_preanalysis(db):
    from ai_cio.services.finances import replace_finances
    from ai_cio.services.trajectory.engine import build_financial_snapshot
    user = launch_persona(db,"maya")["user"]
    replace_finances(db,user.id,income="1440000",expenses="780000",liquid="250000",cadence="annual")
    twin = assemble_twin(db,user.id)
    assert twin["preanalysis"]["financial_health"]["monthly_surplus"] == "55000.00"
    snapshot = build_financial_snapshot(twin)
    assert snapshot["monthly_income"] == "120000.00"
    assert snapshot["monthly_surplus"] == "55000.00"


def test_missing_goal_funding_is_not_assumed_zero(db):
    twin,bits,_ = reviewed(db,"maya")
    twin["goals"]["items"][0]["current_funding"] = None
    result = build_grounded_reviews(twin,bits)
    row = next(r for r in result["items"] if r["theme"] == "goals")
    assert row["id"] == "goal-inputs"
    assert row["proof"]["calculations"] == []


def test_specialist_pages_receive_cited_findings(client,db,monkeypatch):
    from ai_cio.api import routes
    user = launch_persona(db,"tom")["user"]
    monkeypatch.setattr(routes,"run_tax_agent",lambda *a,**k:{"available":True,"rule_version":"fixture-rule","summary":{"realized_gains":"10"},"missing_data":[]})
    monkeypatch.setattr(routes,"run_fd_agent",lambda *a,**k:{"available":True,"fixed_deposits":[{"bank_name":"Example Bank","principal":"600000","maturity_date":"2027-01-01"}]})
    for path,owner in [("tax/summary","tax_agent"),("fd/summary","fd_agent")]:
        response = client.get(f"/users/{user.id}/{path}")
        assert response.status_code == 200
        row = response.json()["review_findings"][0]
        assert row["owner"] == owner
        assert row["proof"]["principles"]
