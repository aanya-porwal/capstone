
import pandas as pd
import numpy as np
from scipy.optimize import minimize

from engine.portfolio_metrics import (
    _load_historical_returns,
    _load_historical_volatilities,
)
from engine.market_data import calculate_annualized_return


def calculate_portfolio_risk(weights, covariance_matrix):
    portfolio_variance = weights.T @ covariance_matrix @ weights
    return float(np.sqrt(max(portfolio_variance, 0.0)))


def optimize_portfolio(risk_profile, risk_limit):
    assets = pd.read_csv("data/assets.csv")

    returns = assets["expected_return"].to_numpy(dtype=float, copy=True)
    volatilities = assets["volatility"].to_numpy(dtype=float, copy=True)
    risk_levels = assets["risk_level"].to_numpy(dtype=float)
    liquidity = assets["liquidity"].to_numpy(dtype=float)
    lock_in = assets["lock_in"].to_numpy(dtype=float)
    asset_names = assets["asset_name"].tolist()

    historical_returns = _load_historical_returns()
    historical_volatilities = _load_historical_volatilities()

    for i, asset_name in enumerate(asset_names):
        if asset_name in historical_returns.columns:
            asset_returns = historical_returns[asset_name].dropna()

            if len(asset_returns) >= 2:
                historical_return = calculate_annualized_return(
                    asset_returns
                )
                returns[i] = (
                    0.5 * returns[i]
                    + 0.5 * historical_return
                )

        if asset_name in historical_volatilities:
            volatilities[i] = historical_volatilities[asset_name]

    if (
        not np.isfinite(returns).all()
        or not np.isfinite(volatilities).all()
        or (volatilities < 0).any()
        or not np.isfinite(liquidity).all()
        or not np.isfinite(lock_in).all()
        or (liquidity < 0).any()
        or (liquidity > 1).any()
        or (lock_in < 0).any()
    ):
        raise ValueError("Asset data contains invalid values.")

    number_of_assets = len(assets)
    correlation_matrix = np.eye(number_of_assets)

    for i, asset_i in enumerate(asset_names):
        for j, asset_j in enumerate(asset_names):
            if (
                asset_i in historical_returns.columns
                and asset_j in historical_returns.columns
            ):
                paired = historical_returns[
                    [asset_i, asset_j]
                ].dropna()

                if len(paired) >= 2:
                    correlation = paired.corr().iloc[0, 1]

                    if np.isfinite(correlation):
                        correlation_matrix[i, j] = np.clip(
                            correlation, -1.0, 1.0
                        )

    correlation_matrix = (
        correlation_matrix + correlation_matrix.T
    ) / 2
    np.fill_diagonal(correlation_matrix, 1.0)

    covariance_matrix = (
        np.outer(volatilities, volatilities)
        * correlation_matrix
    )

    if risk_profile == "Low":
        max_high_risk = 0.30
        risk_aversion = 3.0
        min_weighted_liquidity = 0.65
        max_weighted_lock_in = 5.0
    elif risk_profile == "Moderate":
        max_high_risk = 0.50
        risk_aversion = 2.0
        min_weighted_liquidity = 0.60
        max_weighted_lock_in = 5.0
    elif risk_profile == "Moderately High":
        max_high_risk = 0.70
        risk_aversion = 1.0
        min_weighted_liquidity = 0.50
        max_weighted_lock_in = 6.0
    else:
        max_high_risk = 0.90
        risk_aversion = 0.5
        min_weighted_liquidity = 0.40
        max_weighted_lock_in = 8.0

    high_risk_assets = risk_levels >= 3

    def objective(weights):
        expected_return = np.dot(weights, returns)
        portfolio_risk = calculate_portfolio_risk(
            weights, covariance_matrix
        )
        return -expected_return + risk_aversion * portfolio_risk**2

    def risk_constraint(weights):
        return risk_limit - calculate_portfolio_risk(
            weights, covariance_matrix
        )

    def high_risk_constraint(weights):
        return max_high_risk - np.sum(
            weights[high_risk_assets]
        )

    def liquidity_constraint(weights):
        return np.dot(weights, liquidity) - min_weighted_liquidity

    def lock_in_constraint(weights):
        return max_weighted_lock_in - np.dot(weights, lock_in)

    constraints = [
        {
            "type": "eq",
            "fun": lambda weights: np.sum(weights) - 1,
        },
        {"type": "ineq", "fun": risk_constraint},
        {"type": "ineq", "fun": high_risk_constraint},
        {"type": "ineq", "fun": liquidity_constraint},
        {"type": "ineq", "fun": lock_in_constraint},
    ]

    bounds = [(0, 0.40) for _ in range(number_of_assets)]
    initial_weights = np.ones(number_of_assets) / number_of_assets

    result = minimize(
        objective,
        initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )

    if not result.success:
        return None

    weights = result.x
    portfolio_return = float(np.dot(weights, returns))
    portfolio_risk = calculate_portfolio_risk(
        weights, covariance_matrix
    )

    portfolio = {
        asset_names[i]: float(weights[i])
        for i in range(number_of_assets)
        if weights[i] > 0.001
    }

    weighted_liquidity = float(np.dot(weights, liquidity))
    weighted_lock_in = float(np.dot(weights, lock_in))
    max_asset_weight = float(np.max(weights))
    high_risk_allocation = float(np.sum(weights[high_risk_assets]))

    diagnostics = {
        "risk_limit": float(risk_limit),
        "risk_within_limit": bool(
            portfolio_risk <= risk_limit + 1e-6
        ),
        "weighted_liquidity": weighted_liquidity,
        "minimum_weighted_liquidity": float(
            min_weighted_liquidity
        ),
        "liquidity_constraint_satisfied": bool(
            weighted_liquidity >= min_weighted_liquidity - 1e-6
        ),
        "weighted_lock_in_years": weighted_lock_in,
        "maximum_weighted_lock_in_years": float(
            max_weighted_lock_in
        ),
        "lock_in_constraint_satisfied": bool(
            weighted_lock_in <= max_weighted_lock_in + 1e-6
        ),
        "maximum_asset_allocation": max_asset_weight,
        "asset_cap": 0.40,
        "asset_cap_satisfied": bool(
            max_asset_weight <= 0.40 + 1e-6
        ),
        "high_risk_allocation": high_risk_allocation,
        "maximum_high_risk_allocation": float(max_high_risk),
        "high_risk_constraint_satisfied": bool(
            high_risk_allocation <= max_high_risk + 1e-6
        ),
        "allocation_total": float(np.sum(weights)),
    }

    return {
        "portfolio": portfolio,
        "expected_return": portfolio_return,
        "risk": portfolio_risk,
        "diagnostics": diagnostics,
    }
