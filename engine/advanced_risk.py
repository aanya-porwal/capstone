"""Research-grade risk experiments: regime simulation, CVaR and walk-forward tests.

These functions are analytical research tools, not investment recommendations.
All inputs are daily simple returns. Missing-data policy is explicit in each
function; no future observations are used to estimate backtest weights.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import LedoitWolf


def portfolio_return_series(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Create a daily portfolio return series using only named assets."""
    if not weights:
        raise ValueError("At least one portfolio weight is required")
    missing = set(weights) - set(returns.columns)
    if missing:
        raise ValueError(f"Missing return columns: {sorted(missing)}")
    w = pd.Series(weights, dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1.0, atol=1e-5):
        raise ValueError("Weights must be finite, non-negative and sum to one")
    aligned = returns[list(w.index)].apply(pd.to_numeric, errors="coerce").dropna()
    if len(aligned) < 2:
        raise ValueError("Insufficient aligned daily return observations")
    return aligned.dot(w)


def historical_cvar(returns, confidence: float = 0.95) -> dict:
    """Historical one-period VaR and CVaR, expressed as positive loss fractions."""
    x = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < 20:
        raise ValueError("At least 20 valid returns are required for CVaR")
    if not 0.5 < confidence < 1:
        raise ValueError("confidence must be between 0.5 and 1")
    losses = -x.to_numpy()
    var = float(np.quantile(losses, confidence))
    tail = losses[losses >= var]
    return {
        "confidence": float(confidence),
        "observations": int(len(x)),
        "var": var,
        "cvar": float(tail.mean()) if len(tail) else var,
        "worst_return": float(x.min()),
        "method": "historical empirical loss quantile",
    }


def _regime_features(benchmark: pd.Series) -> pd.DataFrame:
    s = pd.Series(benchmark, dtype=float).dropna().sort_index()
    if len(s) < 150:
        raise ValueError("At least 150 benchmark daily returns are required")
    wealth = (1 + s).cumprod()
    f = pd.DataFrame(index=s.index)
    f["vol_21"] = s.rolling(21).std() * np.sqrt(252)
    f["vol_63"] = s.rolling(63).std() * np.sqrt(252)
    f["momentum_63"] = (1 + s).rolling(63).apply(np.prod, raw=True) - 1
    f["drawdown"] = wealth / wealth.cummax() - 1
    return f.replace([np.inf, -np.inf], np.nan).dropna()


def regime_switching_monte_carlo(
    returns: pd.DataFrame,
    weights: dict[str, float],
    benchmark: str = "Nifty 50 ETF",
    horizon_months: int = 60,
    simulations: int = 5000,
    seed: int = 42,
) -> dict:
    """Simulate monthly wealth with a Markov chain of empirical market regimes.

    Regimes are descriptive clusters of trailing benchmark volatility,
    momentum and drawdown. Portfolio return distributions are fitted within
    each regime from aligned historical observations.
    """
    if horizon_months < 1 or simulations < 1:
        raise ValueError("horizon_months and simulations must be positive")
    if benchmark not in returns:
        raise ValueError(f"Benchmark column '{benchmark}' is required")
    p = portfolio_return_series(returns, weights)
    features = _regime_features(returns[benchmark])
    common = pd.concat([p.rename("portfolio"), features], axis=1).dropna()
    if len(common) < 120:
        raise ValueError("Insufficient aligned portfolio and regime history")
    scaler = StandardScaler()
    x = scaler.fit_transform(common[["vol_21", "vol_63", "momentum_63", "drawdown"]])
    model = KMeans(n_clusters=3, random_state=42, n_init=20)
    labels = model.fit_predict(x)
    common["regime"] = labels

    summary = common.groupby("regime")["portfolio"].agg(["mean", "std", "count"])
    # Order regimes by return adjusted for volatility; names are descriptive only.
    score = summary["mean"] - 0.5 * summary["std"].fillna(0)
    order = score.sort_values().index.tolist()
    names = {order[0]: "Defensive/stress", order[1]: "Transition", order[2]: "Risk-on"}
    # Transition matrix from consecutive daily regime labels.
    states = common["regime"].to_numpy()
    transition = np.ones((3, 3), dtype=float)  # Laplace smoothing
    for a, b in zip(states[:-1], states[1:]):
        transition[int(a), int(b)] += 1
    transition /= transition.sum(axis=1, keepdims=True)

    means = np.zeros(3)
    stds = np.zeros(3)
    for state in range(3):
        subset = summary.loc[state] if state in summary.index else None
        if subset is None or int(subset["count"]) < 20:
            means[state] = float(common["portfolio"].mean())
            stds[state] = float(common["portfolio"].std())
        else:
            means[state] = float(subset["mean"])
            stds[state] = float(subset["std"])
    stds = np.nan_to_num(stds, nan=float(common["portfolio"].std()))
    stds = np.maximum(stds, 1e-8)

    rng = np.random.default_rng(seed)
    wealth = np.ones(simulations, dtype=float)
    current = np.full(simulations, int(states[-1]), dtype=int)
    monthly_paths = np.empty((simulations, horizon_months), dtype=float)
    for month in range(horizon_months):
        probs = transition[current]
        u = rng.random(simulations)
        cdf = np.cumsum(probs, axis=1)
        current = (u[:, None] > cdf).sum(axis=1).clip(0, 2)
        # Convert empirical daily regime moments to an approximate monthly distribution.
        monthly_mu = np.power(np.maximum(1 + means[current], 0.01), 21) - 1
        monthly_sigma = stds[current] * np.sqrt(21)
        r = rng.normal(monthly_mu, monthly_sigma)
        r = np.maximum(r, -0.95)
        monthly_paths[:, month] = r
        wealth *= 1 + r
    return {
        "simulations": int(simulations),
        "horizon_months": int(horizon_months),
        "median_terminal_wealth_multiple": float(np.median(wealth)),
        "p05_terminal_wealth_multiple": float(np.percentile(wealth, 5)),
        "p95_terminal_wealth_multiple": float(np.percentile(wealth, 95)),
        "probability_of_loss": float(np.mean(wealth < 1)),
        "regime_summary": summary.assign(label=[names.get(i, "Unknown") for i in summary.index]),
        "transition_matrix": transition,
        "current_regime": names[int(states[-1])],
        "method": "Markov regime switching with Gaussian within-regime monthly approximation",
        "monthly_returns": monthly_paths,
    }


def walk_forward_backtest(
    returns: pd.DataFrame,
    benchmark: str = "Nifty 50 ETF",
    lookback: int = 252,
    rebalance_every: int = 21,
    max_weight: float = 0.40,
    min_assets: int = 2,
) -> dict:
    """Long-only walk-forward minimum-variance backtest with no look-ahead.

    At each rebalance date, select assets with sufficient training coverage,
    estimate covariance on the trailing window, optimise weights, then hold
    those weights over the next test window. Benchmark is buy-and-hold.
    """
    if benchmark not in returns:
        raise ValueError(f"Benchmark column '{benchmark}' is required")
    if lookback < 60 or rebalance_every < 1:
        raise ValueError("lookback must be >=60 and rebalance_every must be positive")
    data = returns.copy().sort_index().replace([np.inf, -np.inf], np.nan)
    candidates = [c for c in data.columns if c != benchmark]
    if len(candidates) < min_assets:
        raise ValueError("Not enough candidate assets for a portfolio backtest")
    portfolio_parts = []
    weight_records = []
    start = lookback
    while start < len(data):
        train = data.iloc[max(0, start - lookback):start]
        test = data.iloc[start:min(start + rebalance_every, len(data))]
        coverage = train[candidates].notna().mean()
        selected = coverage[coverage >= 0.80].index.tolist()
        if len(selected) < min_assets:
            start += rebalance_every
            continue
        fit = train[selected].dropna()
        if len(fit) < 60:
            start += rebalance_every
            continue
        # Winsorise only the training sample to reduce single-observation optimiser instability.
        lo, hi = fit.quantile(0.01), fit.quantile(0.99)
        fit = fit.clip(lower=lo, upper=hi, axis=1)
        cov = LedoitWolf().fit(fit.to_numpy()).covariance_ * 252
        n = len(selected)
        from scipy.optimize import minimize
        x0 = np.full(n, 1 / n)
        bounds = [(0.0, max(max_weight, 1.0 / n))] * n
        cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
        result = minimize(lambda w: float(w @ cov @ w), x0, method="SLSQP",
                          bounds=bounds, constraints=cons,
                          options={"maxiter": 1000, "ftol": 1e-10})
        if not result.success:
            start += rebalance_every
            continue
        weights = pd.Series(result.x, index=selected)
        # Require all held assets on each test day; no forward filling of returns.
        held = test[selected].dropna()
        if held.empty:
            start += rebalance_every
            continue
        pr = held.dot(weights).rename("portfolio")
        portfolio_parts.append(pr)
        weight_records.append({"date": str(test.index[0]), **weights.to_dict()})
        start += rebalance_every
    if not portfolio_parts:
        raise ValueError("No valid out-of-sample periods; increase data coverage or reduce lookback")
    portfolio = pd.concat(portfolio_parts).sort_index()
    portfolio = portfolio[~portfolio.index.duplicated(keep="last")]
    bench = data.loc[portfolio.index, benchmark].dropna()
    aligned = pd.concat([portfolio, bench.rename("benchmark")], axis=1).dropna()
    if len(aligned) < 20:
        raise ValueError("Insufficient out-of-sample observations after benchmark alignment")

    def metrics(s):
        wealth = (1 + s).cumprod()
        years = len(s) / 252
        cagr = float(wealth.iloc[-1] ** (1 / years) - 1) if years > 0 and wealth.iloc[-1] > 0 else np.nan
        vol = float(s.std(ddof=1) * np.sqrt(252))
        drawdown = float((wealth / wealth.cummax() - 1).min())
        return {"observations": int(len(s)), "cagr": cagr, "volatility": vol,
                "max_drawdown": drawdown, "total_return": float(wealth.iloc[-1] - 1)}
    return {
        "portfolio_metrics": metrics(aligned["portfolio"]),
        "benchmark_metrics": metrics(aligned["benchmark"]),
        "portfolio_returns": aligned["portfolio"],
        "benchmark_returns": aligned["benchmark"],
        "rebalance_weights": pd.DataFrame(weight_records),
        "out_of_sample_start": str(aligned.index.min()),
        "out_of_sample_end": str(aligned.index.max()),
        "method": "Walk-forward long-only minimum variance; trailing-only estimation",
    }
