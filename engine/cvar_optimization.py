"""Scenario-based long-only CVaR portfolio optimisation.

Implements the Rockafellar-Uryasev linear-programming formulation.
Inputs are aligned daily simple-return scenarios. This is a historical-scenario
research optimiser, not a forecast or a guarantee of future tail risk.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog


def optimise_cvar(
    returns: pd.DataFrame,
    *,
    confidence: float = 0.95,
    max_weight: float | dict[str, float] = 1.0,
    equity_columns: list[str] | None = None,
    equity_cap: float | None = None,
    min_annual_return: float | None = None,
) -> dict:
    """Minimise empirical CVaR under long-only, fully-invested constraints."""
    if not isinstance(returns, pd.DataFrame) or returns.empty:
        raise ValueError("returns must be a non-empty DataFrame")
    if not np.isfinite(confidence) or not 0.5 < confidence < 1:
        raise ValueError("confidence must be finite and between 0.5 and 1")
    if equity_cap is not None and (
        not np.isfinite(equity_cap) or not 0 <= equity_cap <= 1
    ):
        raise ValueError("equity_cap must be between zero and one")
    if min_annual_return is not None and not np.isfinite(min_annual_return):
        raise ValueError("min_annual_return must be finite")

    data = returns.apply(pd.to_numeric, errors="coerce")
    data = data.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how="any")
    if data.shape[0] < 30 or data.shape[1] < 1:
        raise ValueError("At least 30 complete scenarios and one asset are required")
    if data.columns.has_duplicates:
        raise ValueError("Asset columns must be unique")

    names = list(data.columns)
    scenarios = data.to_numpy(dtype=float)
    t_count, n_assets = scenarios.shape
    if isinstance(max_weight, dict):
        caps = np.array([float(max_weight.get(name, 1.0)) for name in names])
    else:
        if not np.isfinite(max_weight):
            raise ValueError("max_weight must be finite")
        caps = np.full(n_assets, float(max_weight))
    if not np.isfinite(caps).all() or (caps < 0).any() or (caps > 1).any():
        raise ValueError("Each asset weight cap must be between zero and one")
    if caps.sum() < 1 - 1e-10:
        raise ValueError("Weight caps make the fully-invested constraint infeasible")

    # Variables: n weights, eta (VaR threshold), and T tail slacks.
    variable_count = n_assets + 1 + t_count
    objective = np.zeros(variable_count)
    objective[n_assets] = 1.0
    objective[n_assets + 1:] = 1.0 / ((1.0 - confidence) * t_count)

    # -R w - eta - u <= 0, equivalent to u >= loss - eta.
    a_ub = np.zeros((t_count, variable_count))
    a_ub[:, :n_assets] = -scenarios
    a_ub[:, n_assets] = -1.0
    a_ub[np.arange(t_count), n_assets + 1 + np.arange(t_count)] = -1.0
    b_ub = np.zeros(t_count)

    if equity_cap is not None:
        if not equity_columns:
            raise ValueError("equity_columns are required when equity_cap is set")
        missing = set(equity_columns) - set(names)
        if missing:
            raise ValueError(f"Unknown equity columns: {sorted(missing)}")
        row = np.zeros(variable_count)
        row[[names.index(name) for name in equity_columns]] = 1.0
        a_ub = np.vstack([a_ub, row])
        b_ub = np.append(b_ub, float(equity_cap))

    if min_annual_return is not None:
        row = np.zeros(variable_count)
        row[:n_assets] = -scenarios.mean(axis=0) * 252.0
        a_ub = np.vstack([a_ub, row])
        b_ub = np.append(b_ub, -float(min_annual_return))

    a_eq = np.zeros((1, variable_count))
    a_eq[0, :n_assets] = 1.0
    bounds = ([(0.0, float(cap)) for cap in caps]
              + [(None, None)] + [(0.0, None)] * t_count)
    result = linprog(
        objective, A_ub=a_ub, b_ub=b_ub,
        A_eq=a_eq, b_eq=np.array([1.0]),
        bounds=bounds, method="highs",
    )
    if not result.success:
        raise ValueError(f"CVaR optimisation infeasible or failed: {result.message}")

    weights = np.clip(result.x[:n_assets], 0.0, 1.0)
    weights /= weights.sum()
    portfolio = scenarios @ weights
    losses = -portfolio
    var = float(np.quantile(losses, confidence))
    cvar = float(losses[losses >= var].mean())
    annual_return = float(portfolio.mean() * 252.0)
    annual_volatility = float(portfolio.std(ddof=1) * np.sqrt(252.0))
    allocation = pd.DataFrame({
        "asset": names,
        "weight": weights,
        "annual_scenario_mean": data.mean().to_numpy() * 252.0,
    }).sort_values("weight", ascending=False).reset_index(drop=True)

    return {
        "allocation": allocation,
        "expected_annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "historical_var": var,
        "historical_cvar": cvar,
        "confidence": float(confidence),
        "observations": int(t_count),
        "assets": int(n_assets),
        "equity_weight": float(sum(weights[names.index(x)] for x in (equity_columns or []))),
        "min_annual_return": min_annual_return,
        "solver_success": bool(result.success),
        "solver_status": int(result.status),
        "objective_value": float(result.fun),
        "method": "Rockafellar-Uryasev historical-scenario CVaR linear programme",
        "scenario_policy": "complete-case daily simple returns; no imputation",
    }
