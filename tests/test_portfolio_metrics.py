
import numpy as np

from engine.allocation import get_allocation
from engine.portfolio import create_portfolio
from engine.portfolio_metrics import (
    calculate_expected_return,
    calculate_portfolio_risk,
    _load_historical_returns,
    _load_historical_volatilities,
)


def test_expected_return():
    allocation = get_allocation("Moderately High")
    portfolio = create_portfolio(allocation)

    expected_return = calculate_expected_return(portfolio)

    assert expected_return > 0
    assert expected_return < 1


def test_portfolio_risk():
    allocation = get_allocation("Moderately High")
    portfolio = create_portfolio(allocation)

    portfolio_risk = calculate_portfolio_risk(portfolio)

    assert portfolio_risk > 0
    assert portfolio_risk < 1


def test_historical_returns_load_both_assets():
    returns = _load_historical_returns()

    assert not returns.empty
    assert "Nifty 50 ETF" in returns.columns
    assert "Gold ETF" in returns.columns
    assert len(returns) > 100


def test_historical_volatilities_are_valid():
    volatilities = _load_historical_volatilities()

    assert "Nifty 50 ETF" in volatilities
    assert "Gold ETF" in volatilities

    for volatility in volatilities.values():
        assert np.isfinite(volatility)
        assert volatility > 0
        assert volatility < 1
