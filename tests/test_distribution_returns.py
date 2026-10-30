import pandas as pd
import pytest
from engine.distribution_returns import distribution_adjusted_returns


def test_distribution_is_added_to_ex_date_return():
    prices = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "close": [100.0, 98.0, 99.0],
    })
    actions = pd.DataFrame({
        "Ex_Date": ["2024-01-02"], "Symbol": ["EMBASSY"],
        "Action_Type": ["Distribution"], "Ratio_or_Amount": ["2.00"],
    })
    returns, diagnostics = distribution_adjusted_returns(prices, actions, "EMBASSY")
    assert returns.iloc[0] == pytest.approx(0.0)
    assert diagnostics.attrs["accepted_events"] == 1


def test_ambiguous_non_cash_actions_are_not_added():
    prices = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "close": [100.0, 101.0],
    })
    actions = pd.DataFrame({
        "Ex_Date": ["2024-01-02", "2024-01-02"],
        "Symbol": ["ABC", "ABC"],
        "Action_Type": ["Stock Split", "Dividend"],
        "Ratio_or_Amount": ["1:2", "Rs. 1.50 per share"],
    })
    returns, diagnostics = distribution_adjusted_returns(prices, actions, "ABC")
    assert returns.iloc[0] == pytest.approx(0.025)
    assert len(diagnostics) == 1
    assert diagnostics.attrs["accepted_events"] == 1


def test_requires_valid_price_columns():
    with pytest.raises(ValueError):
        distribution_adjusted_returns(pd.DataFrame(), pd.DataFrame(), "ABC")


def test_numeric_cash_amount_parser_rejects_ratios():
    from engine.distribution_returns import _cash_amount
    assert _cash_amount("Rs. 1.50 per share") == 1.50
    assert pd.isna(_cash_amount("1:2"))
