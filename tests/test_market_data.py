
import pandas as pd

from engine.market_data import (
    calculate_annualized_return,
    calculate_annualized_volatility,
    generate_market_report,
)


def test_annualized_return():
    returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.01])

    result = calculate_annualized_return(returns)

    assert result > 0


def test_annualized_volatility():
    returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.01])

    result = calculate_annualized_volatility(returns)

    assert result > 0


def test_generate_market_report():
    report = generate_market_report(
        "Nifty 50 ETF",
        "data/nifty50_historical.csv",
    )

    assert report["asset_name"] == "Nifty 50 ETF"
    assert report["price_observations"] > 100
    assert report["return_observations"] > 0

    assert report["start_date"] <= report["end_date"]

    assert -1 < report["annualized_return"]
    assert report["annualized_volatility"] > 0
    assert -1 <= report["maximum_drawdown"] <= 0
    assert pd.notna(report["sharpe_ratio"])
