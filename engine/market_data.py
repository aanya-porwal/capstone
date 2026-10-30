
import pandas as pd
import numpy as np


TRADING_DAYS_PER_YEAR = 252


def load_historical_prices(file_path):
    data = pd.read_csv(file_path)

    required_columns = {"Date", "close"}

    if not required_columns.issubset(data.columns):
        raise ValueError(
            "Historical data must contain Date and close columns."
        )

    data["Date"] = pd.to_datetime(
        data["Date"],
        errors="coerce"
    )

    data["close"] = pd.to_numeric(
        data["close"],
        errors="coerce"
    )

    data = data.dropna(subset=["Date", "close"])

    data = data[data["close"] > 0]

    data = (
        data.sort_values("Date")
        .drop_duplicates(subset=["Date"], keep="last")
        .reset_index(drop=True)
    )

    if len(data) < 2:
        raise ValueError(
            "At least two valid historical prices are required."
        )

    return data


def calculate_returns(data):
    if "close" not in data.columns:
        raise ValueError(
            "Data must contain a close column."
        )

    prices = pd.to_numeric(
        data["close"],
        errors="coerce"
    )

    if (prices.dropna() <= 0).any():
        raise ValueError(
            "Closing prices must be positive."
        )

    returns = prices.pct_change().dropna()

    return returns


def calculate_annualized_return(returns):
    returns = pd.Series(returns).dropna()

    if returns.empty:
        raise ValueError(
            "At least one valid return is required."
        )

    if (returns <= -1).any():
        raise ValueError(
            "Returns cannot be -100% or lower."
        )

    # Geometric annualization based on compounded returns.
    annual_return = (
        np.prod(1 + returns) **
        (TRADING_DAYS_PER_YEAR / len(returns))
    ) - 1

    return float(annual_return)


def calculate_annualized_volatility(returns):
    returns = pd.Series(returns).dropna()

    if len(returns) < 2:
        raise ValueError(
            "At least two valid returns are required "
            "to calculate volatility."
        )

    annual_volatility = (
        returns.std(ddof=1) *
        np.sqrt(TRADING_DAYS_PER_YEAR)
    )

    return float(annual_volatility)


def calculate_max_drawdown(data):
    if "close" not in data.columns:
        raise ValueError(
            "Data must contain a close column."
        )

    prices = pd.to_numeric(
        data["close"],
        errors="coerce"
    ).dropna()

    if prices.empty or (prices <= 0).any():
        raise ValueError(
            "Valid positive closing prices are required."
        )

    running_peak = prices.cummax()

    drawdowns = prices / running_peak - 1

    return float(drawdowns.min())


def calculate_sharpe_ratio(
    returns,
    risk_free_rate=0.0
):
    returns = pd.Series(returns).dropna()

    if len(returns) < 2:
        raise ValueError(
            "At least two valid returns are required."
        )

    daily_risk_free_rate = (
        (1 + risk_free_rate) **
        (1 / TRADING_DAYS_PER_YEAR)
    ) - 1

    excess_returns = returns - daily_risk_free_rate

    daily_volatility = returns.std(ddof=1)

    if daily_volatility == 0:
        raise ValueError(
            "Sharpe ratio cannot be calculated "
            "when return volatility is zero."
        )

    return float(
        excess_returns.mean() /
        daily_volatility *
        np.sqrt(TRADING_DAYS_PER_YEAR)
    )

def generate_market_report(
    asset_name,
    file_path,
    risk_free_rate=0.0
):
    """
    Generate a historical performance report for one asset.

    Returns historical annualized return, annualized volatility,
    maximum drawdown, Sharpe ratio, and observation counts.
    """
    prices = load_historical_prices(file_path)
    returns = calculate_returns(prices)

    annualized_return = calculate_annualized_return(returns)
    annualized_volatility = calculate_annualized_volatility(returns)
    maximum_drawdown = calculate_max_drawdown(prices)
    sharpe_ratio = calculate_sharpe_ratio(
        returns,
        risk_free_rate=risk_free_rate
    )

    return {
        "asset_name": asset_name,
        "start_date": prices["Date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": prices["Date"].iloc[-1].strftime("%Y-%m-%d"),
        "price_observations": int(len(prices)),
        "return_observations": int(len(returns)),
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "maximum_drawdown": maximum_drawdown,
        "sharpe_ratio": sharpe_ratio,
    }

def calculate_investment_growth(file_path, initial_investment=10000):
    """
    Calculate the historical growth of an initial investment.

    The first valid closing price represents the initial investment.
    """
    if initial_investment <= 0:
        raise ValueError("Initial investment must be positive.")

    prices = load_historical_prices(file_path)

    growth = (
        prices["close"] / prices["close"].iloc[0]
    ) * initial_investment

    return pd.DataFrame({
        "Date": prices["Date"],
        "investment_value": growth
    })
