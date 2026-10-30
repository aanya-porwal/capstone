import pytest

from engine.multi_goal import evaluate_multi_goal_plan


def test_multi_goal_budget_is_never_double_counted():
    result = evaluate_multi_goal_plan(
        [
            {"name": "Home", "target_today": 5000000, "years": 8,
             "monthly_contribution": 30000, "current_corpus": 200000},
            {"name": "Education", "target_today": 2000000, "years": 5,
             "monthly_contribution": 20000, "current_corpus": 100000},
        ],
        monthly_budget=40000,
        simulations=100,
    )
    assert result["requested_total"] == 50000
    assert result["funded_total"] == pytest.approx(40000)
    assert sum(g["funded_monthly"] for g in result["goals"]) <= 40000
    assert result["contribution_scale"] == pytest.approx(0.8)


def test_each_goal_gets_its_own_horizon_and_inflation_target():
    result = evaluate_multi_goal_plan(
        [
            {"name": "Near term", "target_today": 100000, "years": 2,
             "monthly_contribution": 1000, "inflation": 0.05},
            {"name": "Long term", "target_today": 100000, "years": 10,
             "monthly_contribution": 1000, "inflation": 0.05},
        ],
        monthly_budget=5000,
        simulations=100,
    )
    near, long = result["goals"]
    assert near["inflation_adjusted_target"] < long["inflation_adjusted_target"]
    assert near["years"] == 2
    assert long["years"] == 10
    assert 0 <= near["goal_probability"] <= 1
    assert 0 <= long["goal_probability"] <= 1


def test_rejects_invalid_goal_and_budget():
    with pytest.raises(ValueError):
        evaluate_multi_goal_plan([{"name": "Bad", "years": 0}], 1000)
    with pytest.raises(ValueError):
        evaluate_multi_goal_plan([], -1)


def test_zero_requested_contributions_are_safe():
    result = evaluate_multi_goal_plan(
        [{"name": "Funded from corpus", "target_today": 10000, "years": 5,
          "monthly_contribution": 0, "current_corpus": 20000}],
        monthly_budget=1000,
        simulations=50,
    )
    assert result["funded_total"] == 0
    assert result["goals"][0]["funded_monthly"] == 0


def test_goal_specific_portfolios_use_distinct_horizon_risk_constraints():
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2022-01-01", periods=320)
    returns = pd.DataFrame({
        "Nifty 50 ETF": rng.normal(0.0004, 0.01, len(dates)),
        "Gold ETF": rng.normal(0.0002, 0.006, len(dates)),
    }, index=dates)
    result = evaluate_multi_goal_plan(
        [
            {"name": "Near-term deposit", "target_today": 500000, "years": 2,
             "monthly_contribution": 5000},
            {"name": "Retirement", "target_today": 5000000, "years": 25,
             "monthly_contribution": 5000},
        ],
        monthly_budget=10000,
        returns=returns,
        household_risk_score=60,
        simulations=50,
    )
    near, long = result["goals"]
    assert near["risk_score"] < long["risk_score"]
    assert near["portfolio_allocation"]
    assert long["portfolio_allocation"]
    assert sum(x["weight"] for x in near["portfolio_allocation"]) == pytest.approx(1)
    assert sum(x["weight"] for x in long["portfolio_allocation"]) == pytest.approx(1)
