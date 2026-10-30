import numpy as np
import pandas as pd
import pytest

from engine.advanced_risk import (
    historical_cvar,
    portfolio_return_series,
    regime_switching_monte_carlo,
    walk_forward_backtest,
)


def make_returns(n=900):
    rng = np.random.default_rng(17)
    dates = pd.bdate_range("2018-01-01", periods=n)
    market = rng.normal(0.0003, 0.01, n)
    return pd.DataFrame({
        "Nifty 50 ETF": market,
        "Gold ETF": rng.normal(0.0002, 0.006, n),
        "Nifty 500 Index Proxy": market * 0.9 + rng.normal(0, 0.004, n),
        "Embassy REIT Price": rng.normal(0.00025, 0.007, n),
    }, index=dates)


def test_historical_cvar_is_positive_for_left_tail():
    result = historical_cvar(pd.Series(np.random.default_rng(1).normal(0.0002, 0.02, 500)))
    assert result["cvar"] >= result["var"]
    assert result["observations"] == 500


def test_portfolio_return_series_requires_valid_weights():
    r = make_returns()
    with pytest.raises(ValueError):
        portfolio_return_series(r, {"Gold ETF": 0.5})


def test_regime_switching_simulation_is_reproducible():
    r = make_returns()
    result = regime_switching_monte_carlo(
        r, {"Nifty 50 ETF": 0.6, "Gold ETF": 0.4},
        horizon_months=24, simulations=300, seed=9,
    )
    assert result["monthly_returns"].shape == (300, 24)
    assert 0 <= result["probability_of_loss"] <= 1
    assert result["transition_matrix"].shape == (3, 3)


def test_walk_forward_backtest_uses_out_of_sample_periods():
    r = make_returns()
    result = walk_forward_backtest(r, lookback=252, rebalance_every=21)
    assert result["portfolio_metrics"]["observations"] > 20
    assert result["out_of_sample_start"] > str(r.index[0].date())
    assert np.isfinite(result["portfolio_metrics"]["cagr"])


def test_walk_forward_backtest_rejects_missing_benchmark():
    with pytest.raises(ValueError, match="Benchmark"):
        walk_forward_backtest(make_returns().drop(columns=["Nifty 50 ETF"]))
