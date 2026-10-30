"""Household goal planning with shared-budget and correlated market-path simulation.

All goals on a household path experience the same simulated asset-market shocks.
This makes the all-goals success probability a joint event rather than a product
or sum of independently simulated goal probabilities.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np

from engine.goals import future_value, required_monthly_investment


def _joint_market_paths(portfolios, returns, simulations, max_months, seed):
    """Create common monthly asset shocks for every goal portfolio."""
    rng = np.random.default_rng(seed)
    available = [p for p in portfolios if isinstance(p, dict)]
    if available:
        moments = available[0]["moments"]
        assets = moments["assets"]["asset"].tolist()
        mu = np.asarray(moments["mu"], dtype=float)
        cov = np.asarray(moments["cov"], dtype=float)
        # Monthly Gaussian approximation from annual arithmetic moments.
        eig, vec = np.linalg.eigh((cov + cov.T) / 2)
        cov_psd = vec @ np.diag(np.maximum(eig, 1e-10)) @ vec.T
        shocks = rng.multivariate_normal(
            mean=mu / 12.0,
            cov=cov_psd / 12.0,
            size=(simulations, max_months),
            check_valid="ignore",
        )
        shocks = np.maximum(shocks, -0.95)
        paths = []
        for portfolio in portfolios:
            if portfolio is None:
                paths.append(None)
                continue
            weights = portfolio["allocation"].set_index("asset")["weight"]
            vector = np.array([float(weights.get(a, 0.0)) for a in assets])
            paths.append(np.maximum(shocks @ vector, -0.95))
        return paths, "shared multivariate Gaussian asset shocks using optimiser covariance"

    # Assumption-only fallback: common systematic factor plus goal-specific noise.
    common = rng.standard_normal((simulations, max_months))
    paths = []
    for i, (annual_return, annual_volatility) in enumerate(portfolios):
        idio = rng.standard_normal((simulations, max_months))
        z = np.sqrt(0.50) * common + np.sqrt(0.50) * idio
        path = annual_return / 12 + annual_volatility / np.sqrt(12) * z
        paths.append(np.maximum(path, -0.95))
    return paths, "assumption-only common-factor Gaussian proxy (0.50 cross-goal factor share)"


def evaluate_multi_goal_plan(
    goals: Iterable[dict],
    monthly_budget: float,
    *,
    default_return: float = 0.08,
    default_volatility: float = 0.12,
    simulations: int = 2500,
    seed: int = 42,
    returns=None,
    household_risk_score: int = 50,
    age: int = 30,
    tax_regime: str = 'New',
    existing_80c: float = 0,
) -> dict:
    """Evaluate multiple goals against one contribution budget and common market paths."""
    goals = list(goals)
    if not np.isfinite(monthly_budget) or monthly_budget < 0:
        raise ValueError("Monthly budget must be finite and non-negative.")
    if (not np.isfinite(default_return) or not np.isfinite(default_volatility)
            or default_return < 0 or default_volatility < 0):
        raise ValueError("Return and volatility assumptions must be finite and non-negative.")
    if not isinstance(simulations, (int, np.integer)) or simulations < 1:
        raise ValueError("Simulations must be a positive integer.")
    if not isinstance(seed, (int, np.integer)):
        raise ValueError("Seed must be an integer.")

    requests = []
    for goal in goals:
        name = str(goal.get("name", "")).strip()
        target = float(goal.get("target_today", goal.get("goal_amount", 0)))
        years = float(goal.get("years", goal.get("goal_years", 0)))
        contribution = float(goal.get("monthly_contribution", 0))
        corpus = float(goal.get("current_corpus", goal.get("current_savings", 0)))
        inflation = float(goal.get("inflation", 0.06))
        annual_return = float(goal.get("annual_return", default_return))
        volatility = float(goal.get("volatility", default_volatility))
        if not name:
            raise ValueError("Every goal must have a name.")
        numeric_values = (target, years, contribution, corpus, inflation, annual_return, volatility)
        if not all(np.isfinite(value) for value in numeric_values):
            raise ValueError(f"All financial inputs must be finite for {name}.")
        if target < 0 or years <= 0 or contribution < 0 or corpus < 0:
            raise ValueError(f"Invalid target, horizon, contribution or corpus for {name}.")
        if inflation < 0 or annual_return < 0 or volatility < 0:
            raise ValueError(f"Invalid inflation, return or volatility for {name}.")
        requests.append((name, target, years, contribution, corpus, inflation, annual_return, volatility))

    requested_total = sum(row[3] for row in requests)
    scale = min(1.0, monthly_budget / requested_total) if requested_total else 0.0
    prepared, portfolios = [], []
    for name, target, years, requested, corpus, inflation, annual_return, volatility in requests:
        funded = requested * scale
        inflated_target = target * (1 + inflation) ** years
        goal_risk = int(np.clip(household_risk_score + (-25 if years <= 3 else (-12 if years <= 5 else (0 if years <= 10 else 8))), 0, 100))
        portfolio = None
        allocation_rows = []
        if returns is not None and not getattr(returns, 'empty', True):
            from dwms.quant import optimise
            objective = 'min_variance' if years <= 3 else 'balanced_utility'
            portfolio = optimise(
                returns, risk_score=goal_risk, horizon=int(math.ceil(years)),
                monthly_budget=funded, objective=objective, age=age,
                tax_regime=tax_regime, existing_80c=existing_80c,
            )
            annual_return = float(portfolio['expected_return'])
            volatility = float(portfolio['volatility'])
            allocation_rows = portfolio['allocation'].to_dict('records')
        prepared.append({
            "name": name, "target_today": target,
            "inflation_adjusted_target": inflated_target, "years": years,
            "months": max(1, int(math.ceil(years * 12))),
            "current_corpus": corpus, "requested_monthly": requested,
            "funded_monthly": funded,
            "funding_ratio": funded / requested if requested else 0.0,
            "annual_return_assumption": annual_return,
            "volatility_assumption": volatility, "risk_score": goal_risk,
            "portfolio_allocation": allocation_rows,
            "projected_value": future_value(corpus, funded, annual_return, years),
            "required_monthly_at_assumed_return": required_monthly_investment(
                inflated_target, corpus, annual_return, years
            ),
        })
        portfolios.append(portfolio if portfolio is not None else (annual_return, volatility))

    max_months = max((g["months"] for g in prepared), default=1)
    # If at least one optimised portfolio exists, all goals use its common asset factor model.
    if any(p is not None and not isinstance(p, tuple) for p in portfolios):
        # Portfolios share the same asset universe/moments from optimise().
        market_inputs = [p if not isinstance(p, tuple) else None for p in portfolios]
        market_paths, simulation_method = _joint_market_paths(
            market_inputs, returns, simulations, max_months, seed
        )
        # Goals without a portfolio still receive the common market factor through
        # their own expected return/volatility rather than an independent MC run.
        common_rng = np.random.default_rng(seed + 991)
        common_factor = common_rng.standard_normal((simulations, max_months))
        for i, p in enumerate(portfolios):
            if isinstance(p, tuple):
                mu, vol = p
                idio = common_rng.standard_normal((simulations, max_months))
                market_paths[i] = np.maximum(
                    mu / 12 + vol / np.sqrt(12) *
                    (np.sqrt(.5) * common_factor + np.sqrt(.5) * idio), -.95
                )
    else:
        market_paths, simulation_method = _joint_market_paths(
            portfolios, returns, simulations, max_months, seed
        )

    success_matrix = np.zeros((simulations, len(prepared)), dtype=bool)
    results = []
    for i, goal in enumerate(prepared):
        wealth = np.full(simulations, float(goal["current_corpus"]))
        path = market_paths[i]
        for month in range(goal["months"]):
            wealth = wealth * (1 + path[:, month]) + goal["funded_monthly"]
        success = wealth >= goal["inflation_adjusted_target"]
        success_matrix[:, i] = success
        projected = goal["projected_value"]
        goal.update({
            "deterministic_shortfall": max(0.0, goal["inflation_adjusted_target"] - projected),
            "goal_probability": float(success.mean()),
            "p10": float(np.percentile(wealth, 10)),
            "median": float(np.percentile(wealth, 50)),
            "p90": float(np.percentile(wealth, 90)),
            "simulations": int(simulations),
            "status": "On track (deterministic)" if projected >= goal["inflation_adjusted_target"] else "Gap (deterministic)",
        })
        results.append(goal)

    joint_success = success_matrix.all(axis=1) if prepared else np.ones(simulations, dtype=bool)
    return {
        "goals": results,
        "monthly_budget": float(monthly_budget),
        "requested_total": float(requested_total),
        "funded_total": float(sum(row["funded_monthly"] for row in results)),
        "unallocated_budget": float(max(0.0, monthly_budget - sum(row["funded_monthly"] for row in results))),
        "contribution_scale": float(scale),
        "portfolio_method": "Goal-specific constrained optimisation" if returns is not None and not getattr(returns, "empty", True) else "Assumption-only simulation",
        "household_success_probability": float(joint_success.mean()),
        "all_goals_successes": int(joint_success.sum()),
        "joint_simulations": int(simulations),
        "joint_simulation_method": simulation_method,
        "simulation_interpretation": (
            "All goals share the same simulated market shocks on each household path. "
            "The household success probability is the fraction of paths on which every "
            "goal reaches its inflation-adjusted target. Goal probabilities are marginal "
            "probabilities and must not be added."
        ),
    }
