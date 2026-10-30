import numpy as np
import pandas as pd
import pytest

from engine.backtesting import walk_forward_compare


def _returns(n=900):
    rng = np.random.default_rng(17)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({
        "Benchmark": rng.normal(0.0003, 0.009, n),
        "Equity A": rng.normal(0.0004, 0.012, n),
        "Bond proxy": rng.normal(0.00015, 0.003, n),
        "Gold proxy": rng.normal(0.0002, 0.007, n),
    }, index=idx)


def test_walk_forward_compare_reports_three_strategies_and_costs():
    result = walk_forward_compare(
        _returns(), benchmark="Benchmark", lookback=252,
        rebalance_every=21, transaction_cost_bps=15,
    )
    assert set(result["metrics"]) == {"optimised", "equal_weight", "benchmark"}
    assert result["metrics"]["optimised"]["observations"] >= 20
    assert result["transaction_cost_bps"] == 15
    assert result["average_one_way_turnover"] >= 0
    assert {"one_way_turnover", "date"}.issubset(result["rebalance_log"].columns)


def test_walk_forward_compare_rejects_invalid_costs():
    with pytest.raises(ValueError, match="transaction_cost_bps"):
        walk_forward_compare(_returns(), benchmark="Benchmark", transaction_cost_bps=-1)


def test_walk_forward_compare_requires_benchmark():
    with pytest.raises(ValueError, match="Benchmark"):
        walk_forward_compare(_returns(), benchmark="missing")
