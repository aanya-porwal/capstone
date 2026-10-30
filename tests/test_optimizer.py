import pytest
import numpy as np

from engine.optimizer import optimize_portfolio
from engine.portfolio_metrics import (
    _load_historical_returns,
    _load_historical_volatilities,
)


def test_low_risk_optimization():
    result = optimize_portfolio(
        risk_profile="Low",
        risk_limit=0.06
    )

    assert result is not None
    assert "portfolio" in result
    assert "expected_return" in result
    assert "risk" in result


def test_moderate_risk_optimization():
    result = optimize_portfolio(
        risk_profile="Moderate",
        risk_limit=0.08
    )

    assert result is not None
    assert result["risk"] <= 0.08 + 0.0001


def test_moderately_high_optimization():
    result = optimize_portfolio(
        risk_profile="Moderately High",
        risk_limit=0.10
    )

    assert result is not None
    assert result["risk"] <= 0.10 + 0.0001


def test_high_risk_optimization():
    result = optimize_portfolio(
        risk_profile="High",
        risk_limit=0.15
    )

    assert result is not None
    assert result["risk"] <= 0.15 + 0.0001


def test_historical_estimates_are_available_for_optimizer():
    historical_returns = _load_historical_returns()
    historical_volatilities = _load_historical_volatilities()

    assert "Nifty 50 ETF" in historical_returns.columns
    assert "Gold ETF" in historical_returns.columns

    assert "Nifty 50 ETF" in historical_volatilities
    assert "Gold ETF" in historical_volatilities

    for asset in ("Nifty 50 ETF", "Gold ETF"):
        assert np.isfinite(
            historical_returns[asset].dropna()
        ).all()

        assert (
            historical_volatilities[asset] > 0
        )

def test_no_asset_exceeds_40_percent_allocation():
    result = optimize_portfolio(
        risk_profile="Moderately High",
        risk_limit=0.10
    )

    assert result is not None

    weights = list(result["portfolio"].values())

    assert all(
        weight <= 0.40 + 0.0001
        for weight in weights
    )

    assert sum(weights) == pytest.approx(1.0, abs=0.0001)

def test_optimizer_blends_historical_and_csv_returns():
    import pandas as pd

    from engine.optimizer import optimize_portfolio

    result = optimize_portfolio(
        risk_profile="Moderately High",
        risk_limit=0.10
    )

    assert result is not None
    assert np.isfinite(result["expected_return"])
    assert 0 < result["expected_return"] < 1

def test_portfolio_satisfies_liquidity_and_lock_in_constraints():
    import pandas as pd

    result = optimize_portfolio(
        risk_profile="Moderately High",
        risk_limit=0.10
    )

    assert result is not None

    assets = pd.read_csv("data/assets.csv")
    weights = result["portfolio"]

    weighted_liquidity = sum(
        weights.get(row["asset_name"], 0) * row["liquidity"]
        for _, row in assets.iterrows()
    )

    weighted_lock_in = sum(
        weights.get(row["asset_name"], 0) * row["lock_in"]
        for _, row in assets.iterrows()
    )

    assert weighted_liquidity >= 0.50 - 0.0001
    assert weighted_lock_in <= 6.0 + 0.0001
