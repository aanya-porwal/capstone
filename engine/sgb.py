"""Sovereign Gold Bond (SGB) cash-flow research utilities.

Inputs are source-reported per-gram cash flows and issue/master metadata.
No coupon, redemption value or market quote is fabricated. This module is
for scenario analysis; it does not replace issuer/RBI redemption notices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _date_col(frame, name):
    out = frame.copy()
    out[name] = pd.to_datetime(out[name], errors="coerce")
    return out


def normalise_sgb_cashflows(cashflows: pd.DataFrame) -> pd.DataFrame:
    required = {"ISIN", "Payment_Date", "Payment_Type", "Amount_Per_Gram"}
    missing = required - set(cashflows.columns)
    if missing:
        raise ValueError(f"SGB cashflows missing columns: {sorted(missing)}")
    out = _date_col(cashflows, "Payment_Date")
    out["Amount_Per_Gram"] = pd.to_numeric(out["Amount_Per_Gram"], errors="coerce")
    out["Payment_Type"] = out["Payment_Type"].astype(str).str.strip()
    out = out.dropna(subset=["ISIN", "Payment_Date", "Amount_Per_Gram"])
    out = out[out["Amount_Per_Gram"].ge(0)]
    out = out.sort_values(["ISIN", "Payment_Date", "Payment_Type"])
    return out.reset_index(drop=True)


def sgb_cashflow_summary(cashflows: pd.DataFrame) -> pd.DataFrame:
    """Aggregate coupon/redemption cash flows by ISIN without double counting."""
    cf = normalise_sgb_cashflows(cashflows)
    if cf.empty:
        return pd.DataFrame(columns=["ISIN", "cashflow_events", "total_cash_per_gram",
                                     "coupon_cash_per_gram", "redemption_cash_per_gram",
                                     "first_payment", "last_payment"])
    kind = cf["Payment_Type"].str.lower()
    cf["coupon_cash"] = np.where(kind.str.contains("coupon|interest"), cf["Amount_Per_Gram"], 0.0)
    cf["redemption_cash"] = np.where(kind.str.contains("redemption|principal|maturity"), cf["Amount_Per_Gram"], 0.0)
    summary = cf.groupby("ISIN").agg(
        cashflow_events=("Amount_Per_Gram", "size"),
        total_cash_per_gram=("Amount_Per_Gram", "sum"),
        coupon_cash_per_gram=("coupon_cash", "sum"),
        redemption_cash_per_gram=("redemption_cash", "sum"),
        first_payment=("Payment_Date", "min"),
        last_payment=("Payment_Date", "max"),
    ).reset_index()
    return summary


def sgb_instrument_table(master: pd.DataFrame, cashflows: pd.DataFrame,
                         market_prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """Join tranche-level source records and calculate observed cashflow coverage."""
    required = {"ISIN", "Tranche", "Issue_Date", "Issue_Price", "Maturity_Date", "Coupon_Rate_Pct"}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"SGB master missing columns: {sorted(missing)}")
    m = master.copy()
    for col in ("Issue_Date", "Maturity_Date"):
        m[col] = pd.to_datetime(m[col], errors="coerce")
    for col in ("Issue_Price", "Coupon_Rate_Pct", "Annual_Interest_Per_Gram",
                "Redemption_Price", "Secondary_Market_LTP", "Capital_Gains_Pct", "Total_CAGR_Pct"):
        if col in m:
            m[col] = pd.to_numeric(m[col], errors="coerce")
    summary = sgb_cashflow_summary(cashflows)
    out = m.merge(summary, on="ISIN", how="left", validate="many_to_one")
    out["cashflow_events"] = out["cashflow_events"].fillna(0).astype(int)
    if market_prices is not None and not market_prices.empty:
        q = market_prices.copy()
        if "ISIN" in q:
            for col in ("LTP", "Spot_Gold_Rate", "Premium_Discount_Pct"):
                if col in q:
                    q[col] = pd.to_numeric(q[col], errors="coerce")
            keep = [c for c in ("ISIN", "Exchange", "LTP", "Spot_Gold_Rate", "Premium_Discount_Pct")
                    if c in q]
            q = q[keep].drop_duplicates(["ISIN", "Exchange"] if "Exchange" in keep else ["ISIN"])
            out = out.merge(q, on="ISIN", how="left", suffixes=("", "_quote"))
    out["cashflow_coverage"] = np.where(out["cashflow_events"].gt(0), "cashflows present", "no cashflows found")
    out["source_warning"] = "Validate tranche ISIN, event completeness, quote date and official redemption notice before use."
    return out


def sgb_xirr(cashflows: pd.DataFrame, initial_investment_per_gram: float,
             valuation_date=None, terminal_value_per_gram: float = 0.0) -> float:
    """Annualised money-weighted return for dated per-gram cash flows.

    Initial investment is dated at the earliest payment date unless valuation_date
    is supplied. Terminal value is added at valuation_date. Returns NaN when no
    economically valid root is found.
    """
    from scipy.optimize import brentq
    cf = normalise_sgb_cashflows(cashflows)
    if cf.empty or initial_investment_per_gram <= 0:
        return float("nan")
    start = pd.Timestamp(valuation_date) if valuation_date is not None else cf["Payment_Date"].min()
    flows = [(start, -float(initial_investment_per_gram))]
    flows.extend(zip(cf["Payment_Date"], cf["Amount_Per_Gram"].astype(float)))
    if terminal_value_per_gram:
        end = pd.Timestamp(valuation_date) if valuation_date is not None else cf["Payment_Date"].max()
        flows.append((end, float(terminal_value_per_gram)))
    origin = min(d for d, _ in flows)
    years = np.array([(d - origin).days / 365.25 for d, _ in flows], dtype=float)
    amounts = np.array([v for _, v in flows], dtype=float)
    if not (amounts < 0).any() or not (amounts > 0).any():
        return float("nan")
    def npv(rate):
        return float(np.sum(amounts / np.power(1 + rate, years)))
    grid = np.concatenate([np.linspace(-0.95, 1.0, 200), np.linspace(1.1, 100.0, 100)])
    vals = [npv(x) for x in grid]
    for a, b, fa, fb in zip(grid[:-1], grid[1:], vals[:-1], vals[1:]):
        if np.isfinite(fa) and np.isfinite(fb) and fa * fb < 0:
            try:
                return float(brentq(npv, a, b))
            except ValueError:
                pass
    return float("nan")
