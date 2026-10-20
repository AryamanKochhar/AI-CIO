"""MF evidence must affect final decisions, with scoped reproducible proof."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib

import pytest

from ai_cio import settings
from ai_cio.services.agents.skills_loader import agent_resource_pack, load_agent_skills
from ai_cio.services.agents.decision_suggestions import build_decision_suggestions
from ai_cio.services.finance_standards import load_source_manifest
from ai_cio.services.grounded_reviews import build_grounded_reviews
from ai_cio.services.mutual_funds_action_checks import evaluate_mutual_fund_action_checks
from ai_cio.services.skill_principles import resolve_principle


def fund(fid="FUND-A", *, returns=(8, 9), rolling=25):
    return {"fund_id":fid,"scheme_name":"Synthetic fund "+fid,"isin":fid,"identity_status":"verified",
            "benchmark":{"available":True,"kind":"TRI","name":"Disclosed TRI","source_url":"https://example.test/official-fixture"},
            "disclosure":{"available":True,"stale":False,"observed_on":"2026-09-30"},
            "metrics":{"returns":[{"period":period,"fund_return_pct":str(value),"benchmark_return_pct":"12",
                "start_date":start,"end_date":"2026-10-19","annualized":True}
                for period,value,start in zip(("1y","3y"),returns,("2025-10-19","2023-10-19"))],
                "rolling":{"observations":24,"outperformance_pct":rolling,"median_excess_pp":-2 if rolling<50 else 2}}}


def payload():
    return {"result_version":"mf-intelligence-v1","status":"complete","available":True,"as_of":"2026-10-20",
            "funds":[fund(),fund("FUND-B",returns=(14,15),rolling=75)],
            "overlaps":[],"correlations":[],"findings":[],"data_quality":{"missing":[]}}


def suggestions(mf):
    return build_decision_suggestions(twin={},analysis_bits={"mutual_fund_intelligence":mf},sector_opportunity={})


@pytest.mark.parametrize("agent",["equity_agent","mutual_fund_agent","bond_agent","fd_agent","tax_agent","trajectory_agent"])
def test_specialists_receive_their_own_at_least_six_resources(agent):
    pack=agent_resource_pack(agent)
    assert len(pack["source_ids"])>=6
    assert len(pack["source_ids"])==len(set(pack["source_ids"]))
    assert all(r["scope"] and r["url"].startswith("https://") for r in pack["resources"])
    assert len(pack["portfolio_source_ids"])==3
    assert all(name in load_agent_skills(agent) for name in pack["skill_names"])
    assert "not proof of application" in pack["scope"]
    assert pack["principles"]


def test_scoped_prompts_are_not_a_global_unrelated_source_dump():
    mf=load_agent_skills("mutual_fund_agent")
    tax=load_agent_skills("tax_agent")
    assert "Compare matched total returns" in mf and "Reconcile specialist proposals" in mf
    assert "Establish period and classification" in tax
    assert "Establish period and classification" not in mf
    assert "Compare matched total returns" not in tax
    assert agent_resource_pack("../../private")["resources"]==[]
    assert load_agent_skills("../../private")==""


def test_applied_principle_has_exact_whole_skill_and_section_hash():
    p=resolve_principle("mf_benchmark")
    text=(settings.ROOT/p["path"]).read_text(encoding="utf-8-sig")
    start=text.index("## "+p["section"]);end=text.find("\n## ",start+3)
    section=text[start:end if end>=0 else len(text)]
    assert p["skill_sha256"]==hashlib.sha256(text.encode()).hexdigest()
    assert p["section_sha256"]==hashlib.sha256(section.encode()).hexdigest()
    assert p["excerpt"] in section
    assert {r["id"] for r in p["source_refs"]}=={"mf_nism_distributors","mf_sebi_master_2026","cfa_performance"}
    assert all(r["kind"]!="book_metadata" for r in p["source_refs"])


def test_book_metadata_never_claims_full_text_or_quoted_pages():
    manifest=load_source_manifest()
    books=[r for r in manifest["sources"] if r["kind"]=="book_metadata"]
    assert len(books)>=2
    assert all("unavailable" in r["scope"].lower() or "not bundled" in r["scope"].lower() for r in books)
    assert all("bibliographic" in r["scope"].lower() for r in books)


def test_mf_evidence_changes_final_ranked_decision_not_just_a_panel():
    empty=suggestions({})
    result=suggestions(payload())
    assert empty["items"][0]["id"]=="establish-inputs"
    leading=result["items"][0]
    assert leading["owner"]=="mutual_fund_agent"
    assert leading["theme"]=="mf_performance"
    assert leading["id"]=="mf-benchmark-FUND-A"
    assert {p["id"] for p in leading["proof"]["principles"]}=={"mf_benchmark","mf_persistence"}
    assert leading["proof"]["digest"]
    assert leading["calibrated_probability"] is False
    assert sum(Decimal(str(r["relative_support_percent"])) for r in result["items"])==100
    for c in leading["proof"]["calculations"]:
        assert Decimal(c["result"])==Decimal(c["operands"][0])-Decimal(c["operands"][1])


@pytest.mark.parametrize("mutation",["one_period","bad_identity","price_index","no_rolling","future_date","duplicate_period","only_one_negative"])
def test_one_weak_period_or_unusable_evidence_does_not_become_persistent_lag(mutation):
    mf=payload();mf["funds"]=mf["funds"][:1]; f=mf["funds"][0]
    if mutation=="one_period":f["metrics"]["returns"]=f["metrics"]["returns"][:1]
    elif mutation=="bad_identity":f["identity_status"]="unresolved"
    elif mutation=="price_index":f["benchmark"]["kind"]="PRI"
    elif mutation=="no_rolling":f["metrics"]["rolling"]["observations"]=2
    elif mutation=="future_date":f["metrics"]["returns"][0]["end_date"]="2027-01-01"
    elif mutation=="duplicate_period":f["metrics"]["returns"][1]["period"]="1y"
    else:f["metrics"]["returns"][1]["fund_return_pct"]="20"
    assert not any(r["theme"]=="mf_performance" for r in suggestions(mf)["items"])


def test_supported_benchmark_strengths_are_visible_without_a_buy_claim():
    mf=payload();mf["funds"]=mf["funds"][1:]
    row=suggestions(mf)["items"][0]
    assert "strengths" in row["title"]
    assert "not an automatic trade" in row["detail"]
    assert not any("buy" in v.lower() for v in (row["title"],row["action"]["label"]))


def test_overlap_and_correlation_are_distinct_and_partial_coverage_not_rescaled():
    mf=payload();mf["overlaps"]=[{"fund_a":"FUND-A","fund_b":"FUND-B","weighted_overlap_pct":"60","coverage_a_pct":"75","coverage_b_pct":"80","status":"partial"}]
    mf["correlations"]=[{"fund_a":"FUND-A","fund_b":"FUND-B","correlation":"0.92","observations":24,"frequency":"monthly","status":"ok","end_date":"2026-10-19"}]
    row=next(r for r in suggestions(mf)["items"] if r["theme"]=="mf_overlap")
    facts={r["label"]:r["value"] for r in row["proof"]["facts"]}
    assert facts["Disclosed weighted overlap"]=="60"
    assert facts["First disclosure coverage"]=="75"
    assert facts["Historical aligned return correlation"]=="0.92"
    assert any("lower bound" in r for r in row["proof"]["assumptions"])
    mf["correlations"][0]["observations"]=3
    row=next(r for r in suggestions(mf)["items"] if r["theme"]=="mf_overlap")
    assert "correlation is not evaluated" in row["detail"]


def test_missing_scheme_data_is_not_a_good_health_score_or_fabricated_fund():
    mf=payload();mf["funds"][0]["identity_status"]="unresolved";mf["funds"][0]["benchmark"]={"available":False}
    mf["data_quality"]["missing"]=["Unresolved scheme needs exact plan/ISIN"]
    result=suggestions(mf)
    row=next(r for r in result["coverage"]["deferred_reviews"] if r["theme"]=="mf_data")
    assert not any(r["theme"]=="mf_data" for r in result["items"])
    assert row["proof"]["calculations"]==[]
    assert "not evaluated" in str(row["proof"]["alternatives"])
    assert "probability" in str(row["proof"]["assumptions"])


def test_lost_exact_skill_citation_rejects_mf_action(monkeypatch):
    from ai_cio.services import grounded_reviews
    monkeypatch.setattr(grounded_reviews,"applied_principles",lambda ids:[])
    result=build_grounded_reviews({}, {"mutual_fund_intelligence":payload()})
    assert result["items"]==[]
    assert any(r["id"].startswith("mf-benchmark-") for r in result["coverage"]["rejected"])


def test_action_checks_do_not_treat_debt_name_or_realized_tax_as_switch_tax():
    mf=payload();mf["funds"][0]["scheme_name"]="Debt Liquid Arbitrage Fund"
    result=evaluate_mutual_fund_action_checks({},mf,tax_payload={"available":True,"summary":{"estimated_tax":"0"}},as_of=date(2026,10,20))
    row=result["funds"][0]
    assert row["classification_status"]=="not_verified"
    assert row["estimated_switch_tax"] is None and row["estimated_exit_load"] is None
    assert result["realized_tax_summary_reused"] is False
    assert result["execution_allowed"] is False
    assert len(result["fd_comparison"]["products"])==9
    assert "not promised MF replacement returns" in result["fd_comparison"]["scope"]


def test_purchase_dates_change_tax_scope_but_not_an_unsupported_rate():
    mf=payload();mf["funds"]=mf["funds"][:1]
    f=mf["funds"][0];f["tax_classification"]={"verified":True,"category":"specified_mutual_fund","source_url":"https://example.test/scheme-fixture","observed_on":"2026-10-20"}
    tx=[{"isin":"FUND-A","transaction_type":"purchase","date":"2022-01-01","amount":"100","units":"10"},
        {"isin":"FUND-A","transaction_type":"purchase","date":"2024-01-01","amount":"100","units":"10"}]
    row=evaluate_mutual_fund_action_checks({},mf,transactions=tx,as_of=date(2026,10,20))["funds"][0]
    assert row["classification_status"]=="verified"
    assert row["acquisition_periods_observed"]==["before_2023_04_01","on_or_after_2023_04_01"]
    assert row["estimated_switch_tax"] is None
    assert any("redemption date" in value for value in row["missing_information"])


def test_stale_fd_catalogue_never_supplies_current_comparison_rates():
    result=evaluate_mutual_fund_action_checks({},payload(),as_of=date(2027,1,1))
    assert result["fd_comparison"]["available"] is False
    assert result["fd_comparison"]["products"]==[]


def test_stale_or_unresolved_holdings_cannot_create_overlap_recommendations():
    mf=payload();mf["overlaps"]=[{"fund_a":"FUND-A","fund_b":"FUND-B","weighted_overlap_pct":"60","coverage_a_pct":"75","coverage_b_pct":"80","status":"partial"}]
    mf["funds"][0]["disclosure"]["stale"]=True
    assert not any(r["theme"]=="mf_overlap" for r in suggestions(mf)["items"])
    mf["funds"][0]["disclosure"]["stale"]=False;mf["funds"][0]["identity_status"]="unresolved"
    assert not any(r["theme"]=="mf_overlap" for r in suggestions(mf)["items"])


def test_suitability_requires_real_matching_twin_scores_not_just_a_flag():
    mf=payload();mf["funds"][0]["category"]="Equity Scheme - Small Cap Fund"
    mf["findings"]=[{"type":"psychometric_suitability","fund_id":"FUND-A","severity":"review"}]
    mf["data_quality"]["psychometrics"]={"effective_risk_score":20}
    assert not any(r["theme"]=="mf_suitability" for r in suggestions(mf)["items"])
    twin={"behaviour":{"status":"known","scores":{"risk_score":25,"loss_aversion_score":20}}}
    result=build_decision_suggestions(twin=twin,analysis_bits={"mutual_fund_intelligence":mf},sector_opportunity={})
    assert any(r["theme"]=="mf_suitability" for r in result["items"])


def test_regular_plan_cost_review_does_not_invent_ter_savings():
    mf=payload();mf["funds"][0]["plan"]="Regular"
    mf["findings"]=[{"type":"regular_plan_cost_review","fund_id":"FUND-A","severity":"review"}]
    twin={"portfolio":{"holdings":[{"scheme_name":"Synthetic fund FUND-A","isin":"FUND-A","asset_class":"mutual_fund","valuation":"1000"}]}}
    result=build_decision_suggestions(twin=twin,analysis_bits={"mutual_fund_intelligence":mf},sector_opportunity={})
    row=next(r for r in result["items"] if r["theme"]=="mf_costs")
    assert sum(r["theme"] in {"costs","mf_costs"} for r in result["items"])==1
    assert row["proof"]["calculations"]==[]
    assert any(f["label"]=="Disclosed expense ratio" and f["status"]=="not_recorded" for f in row["proof"]["facts"])
    assert "No savings amount" in str(row["proof"]["assumptions"])


def test_nav_correlation_remains_separate_when_holdings_overlap_is_unavailable():
    mf=payload();mf["correlations"]=[{"fund_a":"FUND-A","fund_b":"FUND-B","correlation":"0.94","observations":36,"frequency":"monthly","status":"ok","start_date":"2023-10-19","end_date":"2026-10-19"}]
    row=next(r for r in suggestions(mf)["items"] if r["theme"]=="mf_overlap")
    assert row["id"]=="mf-correlation-FUND-A-FUND-B"
    assert "does not establish" in row["detail"]
    assert all(f["label"]!="Disclosed weighted overlap" for f in row["proof"]["facts"])
    mf["correlations"][0]["observations"]=10
    assert not any(r["theme"]=="mf_overlap" for r in suggestions(mf)["items"])


def test_future_tax_classification_document_cannot_verify_current_scope():
    mf=payload();mf["funds"][0]["tax_classification"]={"verified":True,"category":"equity_oriented_mf","source_url":"https://example.test/scheme","observed_on":"2027-01-01"}
    row=evaluate_mutual_fund_action_checks({},mf,as_of=date(2026,10,20))["funds"][0]
    assert row["classification_status"]=="not_verified"


def test_old_matched_benchmark_windows_are_not_promoted_as_a_current_review():
    mf=payload()
    for f in mf["funds"]:
        for r in f["metrics"]["returns"]:
            r["end_date"]="2025-10-19"
    assert not any(r["theme"]=="mf_performance" for r in suggestions(mf)["items"])
