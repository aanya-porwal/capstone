import numpy as np
import pandas as pd
import pytest
from engine.ml_forecasting import build_forecast_dataset, walk_forward_forecast


def sample_returns(n=1100):
    rng = np.random.default_rng(55)
    dates = pd.bdate_range("2018-01-01", periods=n)
    x = rng.normal(.0003, .01, n)
    # Add weak serial structure to give the models a learnable signal.
    for i in range(1, n):
        x[i] += .08*x[i-1]
    return pd.Series(x, index=dates)


def test_dataset_uses_forward_compounded_target():
    r = pd.Series([.01, .02, -.01, .03, .02], index=pd.bdate_range("2024-01-01", periods=5))
    d = build_forecast_dataset(r, horizon=2)
    # At t=day 2, next two returns are day 3 and day 4.
    expected = (1-.01)*(1+.03)-1
    assert d.iloc[0]["target"] == pytest.approx(expected)


def test_walk_forward_forecast_is_reproducible_and_time_ordered():
    result = walk_forward_forecast(sample_returns(), horizon=10, min_train=400, step=10)
    pred = result["predictions"]
    assert len(pred) > 10
    assert pred["date"].is_monotonic_increasing
    assert set(["ridge", "hist_gradient_boosting", "historical_mean"]).issubset(pred.columns)
    assert result["validation"].startswith("expanding window")
    assert all(0 <= result["metrics"][m]["directional_accuracy"] <= 1
               for m in result["metrics"])


def test_rejects_insufficient_history_and_invalid_horizon():
    with pytest.raises(ValueError, match="positive"):
        build_forecast_dataset(sample_returns(), horizon=0)
    with pytest.raises(ValueError, match="Insufficient history"):
        walk_forward_forecast(sample_returns(200), min_train=150, horizon=21)
