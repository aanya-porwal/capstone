
import pandas as pd
import numpy as np

from engine.market_data import (
    load_historical_prices,
    calculate_returns,
    calculate_annualized_volatility,
)


TRADING_DAYS_PER_YEAR = 252


def calculate_expected_return(portfolio):
    assets = pd.read_csv("data/assets.csv")
    expected_return = 0.0

    for asset, weight in portfolio.items():
        asset_data = assets[
            assets["asset_name"] == asset
        ]

        if not asset_data.empty:
            asset_return = float(
                asset_data.iloc[0]["expected_return"]
            )
            expected_return += weight * asset_return

    return float(expected_return)


def _load_historical_returns():
    historical_files = {
        "Nifty 50 ETF": "data/nifty50_historical.csv",
        "Gold ETF": "data/goldbees_historical.csv",
    }

    return_series = {}

    for asset_name, file_path in historical_files.items():
        try:
            prices = load_historical_prices(file_path)
            returns = calculate_returns(prices)

            if not returns.empty:
                dates = prices.loc[
                    returns.index, "Date"
                ].values

                returns_series = returns.copy()
                returns_series.index = dates
                return_series[asset_name] = returns_series

        except (FileNotFoundError, ValueError, KeyError):
            continue

    if not return_series:
        return pd.DataFrame()

    return pd.concat(
        return_series,
        axis=1,
        join="inner",
    ).dropna()


def _load_historical_volatilities():
    """Calculate annualized volatility for assets with historical data."""
    historical_files = {
        "Nifty 50 ETF": "data/nifty50_historical.csv",
        "Gold ETF": "data/goldbees_historical.csv",
    }

    volatilities = {}

    for asset_name, file_path in historical_files.items():
        try:
            prices = load_historical_prices(file_path)
            returns = calculate_returns(prices)

            if len(returns) >= 2:
                volatilities[asset_name] = (
                    calculate_annualized_volatility(returns)
                )

        except (FileNotFoundError, ValueError, KeyError):
            continue

    return volatilities


def calculate_portfolio_risk(portfolio):
    assets = pd.read_csv("data/assets.csv")
    asset_names = list(portfolio.keys())

    if not asset_names:
        raise ValueError(
            "Portfolio must contain at least one asset."
        )

    weights = np.array(
        [portfolio[asset] for asset in asset_names],
        dtype=float,
    )

    if not np.isfinite(weights).all():
        raise ValueError("Portfolio weights must be finite.")

    if (weights < 0).any():
        raise ValueError("Portfolio weights cannot be negative.")

    if not np.isclose(weights.sum(), 1.0, atol=1e-5):
        raise ValueError("Portfolio weights must sum to 1.")

    asset_rows = {}

    for asset in asset_names:
        matching = assets[assets["asset_name"] == asset]

        if matching.empty:
            raise ValueError(
                f"Asset '{asset}' was not found in data/assets.csv."
            )

        asset_rows[asset] = matching.iloc[0]

    # Use historical volatility where available.
    # Retain CSV assumptions for other assets.
    historical_volatilities = _load_historical_volatilities()

    volatilities = np.array([
        historical_volatilities.get(
            asset,
            float(asset_rows[asset]["volatility"]),
        )
        for asset in asset_names
    ])

    if (
        not np.isfinite(volatilities).all()
        or (volatilities < 0).any()
    ):
        raise ValueError(
            "Asset volatilities must be finite and non-negative."
        )

    # Default to zero correlation for pairs without historical data.
    correlation_matrix = np.eye(len(asset_names))
    historical_returns = _load_historical_returns()

    if not historical_returns.empty:
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

    portfolio_variance = (
        weights.T @ covariance_matrix @ weights
    )

    return float(np.sqrt(max(portfolio_variance, 0.0)))
