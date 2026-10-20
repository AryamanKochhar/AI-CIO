"""FIRE assumptions persist as validated JSON and remain scoped to one owner."""
import pytest

from ai_cio.db.models import Goal
from ai_cio.services.goals import create_goal, update_goal, list_goals, serialize_goal
from ai_cio.services.identity import create_user
from ai_cio.services.instruments import DomainError

pytestmark = pytest.mark.integration


def data(**overrides):
    return {"name": "Independence at 65", "goal_type": "fire", "planning_inputs": {
        "current_age": 35, "retirement_age": 65, "monthly_spending_today": 40000,
        "monthly_investment_budget": 20000, "annual_pension_today": 0, "earmarked_assets": 100000}, **overrides}


def test_goal_json_round_trip_and_update_without_duplicates(db):
    user = create_user(db, "FIRE owner")
    goal = create_goal(db, user.id, data(notes="Human notes, not a storage format"))
    goal_id = goal.id
    db.expire_all()
    stored = list_goals(db, user.id)[0]
    assert stored.planning_inputs["retirement_age"] == 65
    assert stored.planning_inputs["inflation_percent"] == 6
    assert stored.horizon_years == 30
    assert stored.notes == "Human notes, not a storage format"
    assert serialize_goal(stored)["planning_inputs"]["monthly_investment_budget"] == 20000
    changed = data(name="Reviewed independence plan")
    changed["planning_inputs"]["monthly_investment_budget"] = 25000
    update_goal(db, user.id, goal_id, changed)
    assert len(list_goals(db, user.id)) == 1
    assert stored.planning_inputs["monthly_investment_budget"] == 25000


def test_cross_user_update_cannot_access_or_change_goal(db):
    owner, other = create_user(db, "Owner"), create_user(db, "Other")
    goal = create_goal(db, owner.id, data())
    with pytest.raises(DomainError, match="not found"):
        update_goal(db, other.id, goal.id, data(name="Stolen"))
    assert list_goals(db, other.id) == []
    assert goal.name == "Independence at 65"


def test_invalid_update_is_atomic_and_old_goals_remain_supported(db):
    owner = create_user(db, "Owner")
    goal = create_goal(db, owner.id, data())
    bad = data(name="Must not be saved")
    bad["planning_inputs"]["retirement_age"] = 20
    with pytest.raises(DomainError, match="valid"):
        update_goal(db, owner.id, goal.id, bad)
    assert goal.name == "Independence at 65"
    assert goal.planning_inputs["retirement_age"] == 65
    ordinary = create_goal(db, owner.id, {"name": "Trip", "goal_type": "travel"})
    assert ordinary.planning_inputs is None
    with pytest.raises(DomainError, match="only supported"):
        create_goal(db, owner.id, data(goal_type="travel"))
    assert db.query(Goal).filter(Goal.user_id == owner.id).count() == 2


def test_fire_goal_requires_structured_inputs(db):
    owner = create_user(db, "Owner")
    with pytest.raises(DomainError, match="valid"):
        create_goal(db, owner.id, data(planning_inputs=None))


@pytest.mark.parametrize("field,value", [("target_amount", "NaN"), ("target_amount", "Infinity"),
                                       ("current_funding", True), ("target_date", "2026-02-30"),
                                       ("horizon_years", True), ("horizon_years", 3.5)])
def test_invalid_goal_money_or_dates_cannot_partially_update(db, field, value):
    owner = create_user(db, "Owner")
    goal = create_goal(db, owner.id, data())
    with pytest.raises(DomainError):
        update_goal(db, owner.id, goal.id, data(name="Invalid change", **{field: value}))
    assert goal.name == "Independence at 65"
