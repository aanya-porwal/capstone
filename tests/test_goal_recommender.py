
import pandas as pd
import pytest

from engine.goal_recommender import recommend_goal_investments


@pytest.fixture
def sample_assets():
    return pd.DataFrame([
        {
            "asset_name": "Fixed Deposit",
            "category": "Debt",
            "expected_return": 0.07,
            "volatility": 0.02,
            "risk_level": 1,
            "liquidity": 0.9,
            "lock_in": 0,
        },
        {
            "asset_name": "Government Bond",
            "category": "Debt",
            "expected_return": 0.07,
            "volatility": 0.04,
            "risk_level": 1,
            "liquidity": 0.8,
            "lock_in": 0,
        },
        {
            "asset_name": "Nifty 50 ETF",
            "category": "Equity",
            "expected_return": 0.12,
            "volatility": 0.18,
            "risk_level": 4,
            "liquidity": 0.9,
            "lock_in": 0,
        },
    ])


def test_short_term_goal_avoids_high_volatility_assets(sample_assets):
    result = recommend_goal_investments(
        goal_name="Emergency Fund",
        goal_amount=200000,
        years=2,
        monthly_contribution=10000,
        risk_profile="Moderate",
        assets=sample_assets,
    )

    assert result["suggested_mix"]
    assert all(
        item["recorded_volatility"] <= 0.05
        for item in result["suggested_mix"]
    )
    assert all(
        item["allocation_percent"] >= 0
        for item in result["suggested_mix"]
    )


def test_long_term_goal_can_consider_equity(sample_assets):
    result = recommend_goal_investments(
        goal_name="Retirement",
        goal_amount=5000000,
        years=15,
        monthly_contribution=20000,
        risk_profile="High",
        assets=sample_assets,
    )

    asset_names = {
        item["asset_name"] for item in result["suggested_mix"]
    }
    assert "Nifty 50 ETF" in asset_names


def test_rejects_invalid_timeline(sample_assets):
    with pytest.raises(ValueError):
        recommend_goal_investments(
            goal_name="House",
            goal_amount=1000000,
            years=0,
            monthly_contribution=10000,
            risk_profile="Moderate",
            assets=sample_assets,
        )


def test_rejects_unknown_risk_profile(sample_assets):
    with pytest.raises(ValueError):
        recommend_goal_investments(
            goal_name="House",
            goal_amount=1000000,
            years=10,
            monthly_contribution=10000,
            risk_profile="Unknown",
            assets=sample_assets,
        )


def test_no_eligible_asset_returns_explanation(sample_assets):
    result = recommend_goal_investments(
        goal_name="Short Goal",
        goal_amount=100000,
        years=1,
        monthly_contribution=5000,
        risk_profile="Low",
        assets=sample_assets.assign(lock_in=5),
    )

    assert result["suggested_mix"] == []
    assert result["explanation"]
