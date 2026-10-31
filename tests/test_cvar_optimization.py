import numpy as np
import pandas as pd
import pytest

from engine.cvar_optimization import optimise_cvar


def scenario_data(n=600):
    rng = np.random.default_rng(812)
    dates = pd.bdate_range("2020-01-01", periods=n)
    equity = rng.normal(.0005, .015, n)
    shock_indices = [i for i in (100, 240, 410) if i < n]
    equity[shock_indices] -= .12
    gold = rng.normal(.00025, .007, n)
    debt = rng.normal(.00018, .002, n)
    return pd.DataFrame({"Equity ETF": equity, "Gold ETF": gold,
                         "Debt ETF": debt}, index=dates)


def test_cvar_optimizer_returns_valid_long_only_weights():
    result = optimise_cvar(scenario_data(), confidence=.95, max_weight=.7)
    weights = result["allocation"]["weight"]
    assert weights.sum() == pytest.approx(1.0)
    assert (weights >= 0).all()
    assert weights.max() <= .7 + 1e-8
    assert result["historical_cvar"] >= result["historical_var"]
    assert result["solver_success"]


def test_cvar_optimizer_respects_equity_cap_and_return_floor():
    result = optimise_cvar(
        scenario_data(), max_weight=.8, equity_columns=["Equity ETF"],
        equity_cap=.35, min_annual_return=-.10,
    )
    equity_weight = result["allocation"].set_index("asset").loc["Equity ETF", "weight"]
    assert equity_weight <= .35 + 1e-7
    assert result["expected_annual_return"] >= -.10 - 1e-7


def test_cvar_optimizer_respects_asset_specific_caps():
    result = optimise_cvar(
        scenario_data(), max_weight={"Equity ETF": .2, "Gold ETF": .6, "Debt ETF": .8}
    )
    weights = result["allocation"].set_index("asset")["weight"]
    assert weights["Equity ETF"] <= .2 + 1e-7
    assert weights["Gold ETF"] <= .6 + 1e-7


def test_cvar_optimizer_rejects_infeasible_caps_and_bad_inputs():
    with pytest.raises(ValueError, match="infeasible"):
        optimise_cvar(scenario_data(), max_weight=.2)
    with pytest.raises(ValueError, match="equity_columns"):
        optimise_cvar(scenario_data(), equity_cap=.5)
    with pytest.raises(ValueError, match="30 complete"):
        optimise_cvar(scenario_data(20))


def test_cvar_optimizer_uses_complete_case_scenarios():
    data = scenario_data()
    data.iloc[0, 0] = np.nan
    result = optimise_cvar(data)
    assert result["observations"] == len(data) - 1
    assert result["scenario_policy"].startswith("complete-case")
