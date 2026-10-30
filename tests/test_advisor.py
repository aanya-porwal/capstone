import pytest

from engine.advisor import build_mix, build_plan
from engine.goal_recommender import load_assets
from engine.goals import future_value, required_monthly_investment


# ---- core maths, checked against hand-calculated values -------------------

def test_future_value_matches_hand_calculation():
    # Rs 15,000/month, 10 years, 8% effective annual, month-end contributions.
    # r = 1.08 ** (1/12) - 1 ; FV = 15000 * ((1+r)**120 - 1) / r
    assert future_value(0, 15000, 0.08, 10) == pytest.approx(2_701_864, abs=2)


def test_one_year_of_growth_equals_the_quoted_annual_return():
    assert future_value(100_000, 0, 0.08, 1) == pytest.approx(108_000, abs=0.01)


def test_required_monthly_round_trips():
    needed = required_monthly_investment(5_000_000, 100_000, 0.12, 15)
    assert future_value(100_000, needed, 0.12, 15) == pytest.approx(5_000_000, abs=1)


# ---- recommendation rules --------------------------------------------------

@pytest.fixture(scope="module")
def assets():
    return load_assets()


def test_short_goals_get_no_equity(assets):
    mix, _ = build_mix("Emergency fund", 2, "High", assets)
    assert set(mix) <= {"Fixed Deposit", "Government Bond"}


def test_long_goals_use_equity_and_depend_on_risk(assets):
    low, _ = build_mix("House", 20, "Low", assets)
    high, _ = build_mix("House", 20, "High", assets)
    equity = {"Nifty 50 ETF", "Large Cap Mutual Fund", "ELSS"}
    assert sum(w for a, w in high.items() if a in equity) > sum(
        w for a, w in low.items() if a in equity
    )


@pytest.mark.parametrize("years", [1, 3, 5, 10, 20, 30])
@pytest.mark.parametrize("risk", ["Low", "Moderate", "Moderately High", "High"])
def test_weights_sum_to_one_and_respect_lock_in(assets, years, risk):
    mix, rows = build_mix("Goal", years, risk, assets)
    assert sum(mix.values()) == pytest.approx(1.0)
    for asset in mix:
        assert float(rows[asset][0]["lock_in"]) <= years


def test_ppf_is_capped(assets):
    mix, _ = build_mix("House", 20, "Low", assets)
    assert mix.get("PPF", 0) <= 0.30 + 1e-9


# ---- both planning modes ---------------------------------------------------

GOALS = [
    {"name": "Emergency fund", "amount": 300_000, "years": 2},
    {"name": "Car", "amount": 1_000_000, "years": 5},
    {"name": "House", "amount": 8_000_000, "years": 15},
]


def test_budget_mode_never_exceeds_budget():
    plan = build_plan("budget", GOALS, 30_000, 100_000, "Moderately High", seed=1)
    assert plan["summary"]["monthly_allocated"] <= 30_000 + 0.01
    # earliest deadline is funded first
    assert plan["goals"][0]["monthly_gap"] == pytest.approx(0, abs=0.01)
    assert plan["goals"][2]["status"] == "short"


def test_goal_mode_reaches_every_target_and_reports_affordability():
    plan = build_plan("goal", GOALS, 30_000, 100_000, "Moderately High", seed=1)
    for g in plan["goals"]:
        assert g["projected_value"] >= g["target_amount"] * 0.999
    assert plan["summary"]["affordable"] is False
    assert plan["summary"]["extra_needed_per_month"] > 0


def test_per_asset_numbers_add_up_to_goal_totals():
    plan = build_plan("goal", GOALS, 50_000, 100_000, "Moderate", seed=1)
    for g in plan["goals"]:
        assert sum(m["projected_value"] for m in g["mix"]) == pytest.approx(
            g["projected_value"], abs=1
        )
        assert sum(m["monthly_amount"] for m in g["mix"]) == pytest.approx(
            g["monthly_amount"], abs=1
        )
        assert sum(m["percent"] for m in g["mix"]) == 100


def test_scenarios_are_ordered():
    plan = build_plan("budget", GOALS, 60_000, 0, "Moderate", seed=1)
    for g in plan["goals"]:
        s = g["scenarios"]
        assert (
            s["conservative"]["projected_value"]
            < s["expected"]["projected_value"]
            < s["optimistic"]["projected_value"]
        )


def test_invalid_input_is_rejected():
    with pytest.raises(ValueError):
        build_plan("budget", [], 10_000, 0, "Moderate")
    with pytest.raises(ValueError):
        build_plan("budget", GOALS, 0, 0, "Moderate")
    with pytest.raises(ValueError):
        build_plan("goal", [{"name": "x", "amount": 0, "years": 5}], 0, 0, "Moderate")
