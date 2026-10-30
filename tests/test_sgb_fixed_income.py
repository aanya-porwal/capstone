import numpy as np
import pandas as pd
import pytest

from engine.sgb import normalise_sgb_cashflows, sgb_cashflow_summary, sgb_instrument_table
from engine.fixed_income import bond_price_change_from_yield, yield_curve_scenarios


def test_sgb_cashflow_summary_separates_coupon_and_redemption():
    cf = pd.DataFrame({
        "ISIN": ["IN1", "IN1", "IN1"],
        "Payment_Date": ["2024-01-01", "2024-07-01", "2029-01-01"],
        "Payment_Type": ["Coupon", "Interest", "Redemption"],
        "Amount_Per_Gram": [25, 25, 6500],
    })
    out = sgb_cashflow_summary(cf).iloc[0]
    assert out["coupon_cash_per_gram"] == 50
    assert out["redemption_cash_per_gram"] == 6500
    assert out["total_cash_per_gram"] == 6550


def test_sgb_instrument_table_joins_master_by_isin():
    master = pd.DataFrame({
        "ISIN": ["IN1"], "Tranche": ["I"], "Issue_Date": ["2024-01-01"],
        "Issue_Price": [6200], "Maturity_Date": ["2032-01-01"], "Coupon_Rate_Pct": [2.5],
    })
    cf = pd.DataFrame({
        "ISIN": ["IN1"], "Payment_Date": ["2024-07-01"],
        "Payment_Type": ["Coupon"], "Amount_Per_Gram": [77.5],
    })
    out = sgb_instrument_table(master, cf)
    assert out.loc[0, "cashflow_events"] == 1


def test_fixed_income_duration_sensitivity():
    assert bond_price_change_from_yield(5, 100) == pytest.approx(-0.05)
    assert bond_price_change_from_yield(5, -100) == pytest.approx(0.05)


def test_yield_scenarios_do_not_claim_bond_return():
    out = yield_curve_scenarios(pd.Series([6.5, 6.7]), duration_years=4)
    assert out.loc[out.shock_bps.eq(100), "approx_price_change_pct"].iloc[0] == pytest.approx(-4.0)
    assert "not bond total return" in out.iloc[0]["warning"]


def test_sgb_xirr_uses_separate_investment_and_maturity_dates():
    from engine.sgb import sgb_xirr
    cf = pd.DataFrame({
        "ISIN": ["IN1"], "Payment_Date": ["2025-01-01"],
        "Payment_Type": ["Redemption"], "Amount_Per_Gram": [110.0],
    })
    rate = sgb_xirr(cf, 100.0, investment_date="2024-01-01",
                    valuation_date="2025-01-01")
    assert rate == pytest.approx(0.10, rel=1e-3)
