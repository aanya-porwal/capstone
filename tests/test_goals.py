from engine.goals import future_value, check_goal


def test_future_value():
    result = future_value(
        current_savings=100000,
        monthly_investment=10000,
        annual_return=0.10,
        years=10
    )

    assert result > 2000000
    assert result < 2500000


def test_goal_achievable():
    result = check_goal(
        projected_value=3000000,
        goal_amount=2500000
    )

    assert result == "Goal achievable"


def test_goal_not_achievable():
    result = check_goal(
        projected_value=2000000,
        goal_amount=2500000
    )

    assert result == "Goal not achievable"
    

def test_evaluate_financial_goal_returns_expected_fields():
    from engine.goals import evaluate_financial_goal

    result = evaluate_financial_goal(
        name="House",
        goal_amount=3000000,
        goal_years=10,
        current_savings=500000,
        monthly_investment=30000,
        annual_return=0.08,
        volatility=0.10,
        simulations=100,
    )

    assert result["name"] == "House"
    assert result["goal_amount"] == 3000000.0
    assert result["goal_years"] == 10
    assert result["projected_value"] > 0
    assert result["goal_status"] in [
        "Goal achievable",
        "Goal not achievable",
    ]
    assert 0 <= result["monte_carlo"]["goal_probability"] <= 1


def test_evaluate_financial_goal_rejects_invalid_timeline():
    import pytest
    from engine.goals import evaluate_financial_goal

    with pytest.raises(ValueError):
        evaluate_financial_goal(
            name="House",
            goal_amount=3000000,
            goal_years=0,
            current_savings=500000,
            monthly_investment=30000,
            annual_return=0.08,
            volatility=0.10,
        )
