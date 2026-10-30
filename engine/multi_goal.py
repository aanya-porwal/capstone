"""Independent goal-level planning and Monte Carlo evaluation.

Each goal receives a capped share of one household contribution budget. Goal
simulations are run separately and are not a joint household probability.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np

from engine.goals import future_value, required_monthly_investment
from engine.monte_carlo import run_monte_carlo


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
    """Evaluate goals independently while enforcing a shared monthly budget.

    Goal fields: name, target_today, years, monthly_contribution,
    current_corpus, inflation, and optional annual_return/volatility.
    Requested contributions are scaled pro-rata if they exceed monthly_budget.
    """
    goals = list(goals)
    if monthly_budget < 0:
        raise ValueError("Monthly budget cannot be negative.")
    if default_return < 0 or default_volatility < 0:
        raise ValueError("Return and volatility assumptions cannot be negative.")
    if simulations < 1:
        raise ValueError("Simulations must be at least one.")

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
        if target < 0 or years <= 0 or contribution < 0 or corpus < 0:
            raise ValueError(f"Invalid target, horizon, contribution or corpus for {name}.")
        if inflation < 0 or annual_return < 0 or volatility < 0:
            raise ValueError(f"Invalid inflation, return or volatility for {name}.")
        requests.append((goal, name, target, years, contribution, corpus,
                         inflation, annual_return, volatility))

    requested_total = sum(row[4] for row in requests)
    scale = min(1.0, monthly_budget / requested_total) if requested_total else 0.0
    results = []
    for index, (_, name, target, years, requested, corpus, inflation,
                 annual_return, volatility) in enumerate(requests):
        funded = requested * scale
        inflated_target = target * (1 + inflation) ** years
        projected = future_value(corpus, funded, annual_return, years)
        required = required_monthly_investment(
            inflated_target, corpus, annual_return, years
        )
        portfolio = None
        goal_return, goal_volatility = annual_return, volatility
        allocation_rows = []
        goal_risk = int(np.clip(household_risk_score + (-25 if years <= 3 else (-12 if years <= 5 else (0 if years <= 10 else 8))), 0, 100))
        if returns is not None and not getattr(returns, 'empty', True):
            from dwms.quant import optimise
            objective = 'min_variance' if years <= 3 else 'balanced_utility'
            portfolio = optimise(returns, risk_score=goal_risk, horizon=int(math.ceil(years)), monthly_budget=funded, objective=objective, age=age, tax_regime=tax_regime, existing_80c=existing_80c)
            goal_return = float(portfolio['expected_return'])
            goal_volatility = float(portfolio['volatility'])
            allocation_rows = portfolio['allocation'].to_dict('records')
            projected = future_value(corpus, funded, goal_return, years)
            required = required_monthly_investment(inflated_target, corpus, goal_return, years)
        mc = run_monte_carlo(
            current_savings=corpus,
            monthly_investment=funded,
            expected_return=goal_return,
            volatility=goal_volatility,
            years=years,
            goal_amount=inflated_target,
            simulations=simulations,
            seed=seed + index,
        )
        results.append({
            "name": name,
            "target_today": target,
            "inflation_adjusted_target": inflated_target,
            "years": years,
            "current_corpus": corpus,
            "requested_monthly": requested,
            "funded_monthly": funded,
            "funding_ratio": funded / requested if requested else 0.0,
            "annual_return_assumption": goal_return,
            "volatility_assumption": goal_volatility,
            "risk_score": goal_risk,
            "portfolio_allocation": allocation_rows,
            "projected_value": projected,
            "required_monthly_at_assumed_return": required,
            "deterministic_shortfall": max(0.0, inflated_target - projected),
            "goal_probability": mc["goal_probability"],
            "p10": mc["pessimistic_outcome"],
            "median": mc["median_outcome"],
            "p90": mc["optimistic_outcome"],
            "simulations": mc["simulations"],
            "status": "On track (deterministic)" if projected >= inflated_target else "Gap (deterministic)",
        })

    return {
        "goals": results,
        "monthly_budget": float(monthly_budget),
        "requested_total": float(requested_total),
        "funded_total": float(sum(row["funded_monthly"] for row in results)),
        "unallocated_budget": float(max(0.0, monthly_budget - sum(row["funded_monthly"] for row in results))),
        "contribution_scale": float(scale),
        "portfolio_method": "Goal-specific constrained optimisation" if returns is not None and not getattr(returns, "empty", True) else "Assumption-only simulation; no price panel supplied",
        "simulation_interpretation": (
            "Each goal is simulated independently with its own random paths. "
            "Goal probabilities must not be added or interpreted as the probability "
            "that all household goals succeed together."
        ),
    }
