"""Expanded material must reach retrieval and actual verifiable findings."""
from datetime import date

from ai_cio.services.agents.skills_loader import load_domain_skills
from ai_cio.services.finance_standards import source_context_for_skills
from ai_cio.services.grounded_reviews import build_grounded_reviews
from ai_cio.services.knowledge_retriever import retrieve_knowledge
from ai_cio.services.skill_principles import resolve_principle


def test_new_topics_retrieve_distinct_source_bounded_material():
    rows = retrieve_knowledge(topics=['inflation','sequence_risk','bond','fees','investment_budget','covariance'], limit=6)
    assert len(rows) == len({r['reference'] for r in rows}) == 6
    assert all(r['source_ids'] and 'https://' in r['text'] for r in rows)
    budget = next(r for r in rows if r['section'] == 'investment_budget')
    assert 'not an agreed investment budget' in budget['text']


def test_new_skills_are_available_with_current_primary_source_context():
    skills = ('purchasing-power-and-sequence','fixed-income-first-principles','cost-and-cashflow-first-principles','market-evidence-and-uncertainty')
    text = load_domain_skills(skills)
    assert all('### Skill: '+name in text for name in skills)
    assert 'Coupon rate is not yield' in text
    sources = source_context_for_skills(skills, as_of=date(2026,10,20))
    assert len(sources) == 6
    assert all(not row['review_due'] and row['scope'] for row in sources)


def test_goal_review_cites_unconfirmed_commitment_without_inventing_budget():
    twin = {'financial_position':{'income':{'value':'100000'},'expenses':{'value':'60000'},'cashflow_cadence':'monthly'},
            'goals':{'items':[{'name':'A','target_amount':'100000','current_funding':'0','horizon_years':1},
                              {'name':'B','target_amount':'200000','current_funding':'0','horizon_years':2}]}}
    reviews = build_grounded_reviews(twin)['items']
    goal = next(r for r in reviews if r['theme']=='goals')
    ids = [p['id'] for p in goal['proof']['principles']]
    assert 'investment_commitment' in ids
    assert any('investment budget' in item for item in goal['proof']['missing_information'])
    assert not any('confirmed' in fact['label'].lower() and fact['value'] for fact in goal['proof']['facts'])
    principle = resolve_principle('investment_commitment')
    assert principle['excerpt'] == 'Available surplus is not consent to invest that amount.'
