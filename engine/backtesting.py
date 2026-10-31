"""Walk-forward portfolio evaluation with explicit trading frictions."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf


def _metrics(returns: pd.Series) -> dict:
    s = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < 2 or (s <= -1).any():
        raise ValueError("At least two valid simple-return observations above -100% are required")
    wealth = (1 + s).cumprod()
    years = len(s) / 252.0
    cagr = float(wealth.iloc[-1] ** (1 / years) - 1) if wealth.iloc[-1] > 0 else np.nan
    vol = float(s.std(ddof=1) * np.sqrt(252))
    downside = np.minimum(s.to_numpy(), 0.0)
    downside_vol = float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(252)) if np.any(downside < 0) else np.nan
    drawdown = wealth / wealth.cummax() - 1
    max_dd = float(drawdown.min())
    return {
        "observations": int(len(s)),
        "total_return": float(wealth.iloc[-1] - 1),
        "cagr": cagr,
        "annual_volatility": vol,
        "sharpe_zero_rf": float(s.mean() * 252 / vol) if vol > 0 else np.nan,
        "sortino_zero_rf": float(s.mean() * 252 / downside_vol) if downside_vol > 0 else np.nan,
        "max_drawdown": max_dd,
        "calmar": float(cagr / abs(max_dd)) if max_dd < 0 else np.nan,
    }


def walk_forward_compare(
    returns: pd.DataFrame,
    *,
    benchmark: str,
    lookback: int = 252,
    rebalance_every: int = 21,
    max_weight: float = 0.40,
    transaction_cost_bps: float = 10.0,
    min_assets: int = 2,
) -> dict:
    """Compare rolling minimum-variance, equal-weight and buy/hold benchmark.

    Covariance is estimated only on each trailing training window. Trading costs
    are charged on one-way turnover at each rebalance date. Missing observations
    are not forward-filled; a complete-case panel is used within each test block.
    """
    if not isinstance(returns, pd.DataFrame) or returns.empty:
        raise ValueError("returns must be a non-empty DataFrame")
    if benchmark not in returns:
        raise ValueError(f"Benchmark '{benchmark}' is not in returns")
    if lookback < 60 or rebalance_every < 1 or min_assets < 1:
        raise ValueError("lookback must be >=60, rebalance_every and min_assets must be positive")
    if not np.isfinite(max_weight) or not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1]")
    if not np.isfinite(transaction_cost_bps) or transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps must be finite and non-negative")
    data = returns.copy().sort_index()
    data = data.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if data.columns.has_duplicates:
        raise ValueError("Return columns must be unique")
    candidates = [c for c in data.columns if c != benchmark]
    if len(candidates) < min_assets:
        raise ValueError("Not enough non-benchmark assets")
    opt_parts, equal_parts, benchmark_parts, records = [], [], [], []
    prior = pd.Series(dtype=float)
    prior_equal = pd.Series(dtype=float)
    turnover_total = 0.0
    equal_turnover_total = 0.0
    for start in range(lookback, len(data), rebalance_every):
        train = data.iloc[start-lookback:start]
        test = data.iloc[start:min(start+rebalance_every, len(data))]
        coverage = train[candidates].notna().mean()
        selected = coverage[coverage >= 0.80].index.tolist()
        if len(selected) < min_assets:
            continue
        fit = train[selected].dropna()
        held = test[selected].dropna()
        if len(fit) < 60 or held.empty:
            continue
        cov = LedoitWolf().fit(fit.to_numpy()).covariance_ * 252
        n = len(selected)
        if max_weight * n < 1 - 1e-10:
            raise ValueError("max_weight makes full investment infeasible for selected assets")
        result = minimize(
            lambda w: float(w @ cov @ w), np.full(n, 1/n), method="SLSQP",
            bounds=[(0.0, max_weight)] * n,
            constraints=[{"type": "eq", "fun": lambda w: float(w.sum()-1)}],
            options={"maxiter": 1000, "ftol": 1e-10},
        )
        if not result.success:
            continue
        weights = pd.Series(result.x, index=selected)
        turnover = 1.0 if prior.empty else float(weights.subtract(prior, fill_value=0).abs().sum()/2)
        equal_weights = pd.Series(1.0 / len(selected), index=selected)
        equal_turnover = 1.0 if prior_equal.empty else float(equal_weights.subtract(prior_equal, fill_value=0).abs().sum()/2)
        net = held.dot(weights)
        net.iloc[0] -= turnover * transaction_cost_bps / 10000
        equal_net = held.dot(equal_weights)
        equal_net.iloc[0] -= equal_turnover * transaction_cost_bps / 10000
        equal_turnover_total += equal_turnover
        prior_equal = equal_weights
        opt_parts.append(net.rename("optimised"))
        equal_parts.append(equal_net.rename("equal_weight"))
        benchmark_parts.append(test[benchmark].dropna().rename("benchmark"))
        records.append({"date": test.index[0], "one_way_turnover": turnover, **weights.to_dict()})
        turnover_total += turnover
        prior = weights
    if not opt_parts:
        raise ValueError("No valid out-of-sample windows; inspect coverage or reduce lookback")
    opt = pd.concat(opt_parts).sort_index()
    equal = pd.concat(equal_parts).sort_index()
    bench = pd.concat(benchmark_parts).sort_index()
    aligned = pd.concat([opt, equal, bench], axis=1).dropna()
    if len(aligned) < 20:
        raise ValueError("Fewer than 20 aligned out-of-sample observations")
    return {
        "metrics": {name: _metrics(aligned[name]) for name in aligned.columns},
        "returns": aligned,
        "rebalance_log": pd.DataFrame(records),
        "out_of_sample_start": str(aligned.index.min()),
        "out_of_sample_end": str(aligned.index.max()),
        "average_one_way_turnover": float(turnover_total / len(records)),
        "cumulative_one_way_turnover": float(turnover_total),
        "equal_weight_average_one_way_turnover": float(equal_turnover_total / len(records)),
        "equal_weight_cumulative_one_way_turnover": float(equal_turnover_total),
        "transaction_cost_bps": float(transaction_cost_bps),
        "method": "Expanding calendar; trailing-window Ledoit-Wolf minimum variance; monthly rebalance; transaction costs applied at rebalance",
    }
