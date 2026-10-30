from engine.planner import create_financial_assessment


def test_financial_assessment():
    user = {
        "age": 25,
        "income": 100000,
        "expenses": 50000,
        "debt": 10000,
        "dependents": 0,
        "current_savings": 500000,
        "monthly_investment": 30000,
        "goal_amount": 3000000,
        "goal_years": 10
    }

    result = create_financial_assessment(user)

    assert isinstance(result, dict)

    assert "risk_score" in result
    assert "risk_profile" in result
    assert "portfolio" in result
    assert "expected_return" in result
    assert "portfolio_volatility" in result
    assert "projected_value" in result
    assert "goal_status" in result


def test_financial_assessment_values():
    user = {
        "age": 25,
        "income": 100000,
        "expenses": 50000,
        "debt": 10000,
        "dependents": 0,
        "current_savings": 500000,
        "monthly_investment": 30000,
        "goal_amount": 3000000,
        "goal_years": 10
    }

    result = create_financial_assessment(user)

    assert result["risk_score"] == 6
    assert result["risk_profile"] == "Moderately High"
    assert result["expected_return"] > 0
    assert result["portfolio_volatility"] > 0
    assert result["projected_value"] > 0
    assert result["goal_status"] in [
        "Goal achievable",
        "Goal not achievable"
    ]