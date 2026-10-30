"""Cash-distribution-adjusted price returns for listed trusts and securities.

Only explicitly labelled dividend/distribution events with a numeric per-unit
amount are accepted. Splits, bonuses, rights and ambiguous corporate actions
are not interpreted as cash income.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd


def _cash_amount(value):
    if pd.isna(value):
        return np.nan
    text = str(value).replace(",", "")
    matches = re.findall(r"(?<![A-Za-z0-9])(?:₹|Rs\.?\s*)?(-?\d+(?:\.\d+)?)(?![A-Za-z0-9])", text, flags=re.I)
    if len(matches) != 1:
        return np.nan
    amount = float(matches[0])
    return amount if amount >= 0 else np.nan


def distribution_adjusted_returns(prices, corporate_actions, symbol,
                                  date_col="Date", price_col="close"):
    """Add numeric per-unit cash distributions to ex-date close-price returns."""
    if not {date_col, price_col}.issubset(prices.columns):
        raise ValueError(f"prices must contain {date_col} and {price_col}")
    required = {"Ex_Date", "Symbol", "Action_Type", "Ratio_or_Amount"}
    if not required.issubset(corporate_actions.columns):
        raise ValueError(f"corporate_actions must contain {sorted(required)}")

    p = prices[[date_col, price_col]].copy()
    p[date_col] = pd.to_datetime(p[date_col], errors="coerce")
    p[price_col] = pd.to_numeric(p[price_col], errors="coerce")
    p = p.dropna(subset=[date_col, price_col])
    p = p[p[price_col].gt(0)].sort_values(date_col).drop_duplicates(date_col, keep="last")
    if len(p) < 2:
        raise ValueError("At least two valid price observations are required")

    actions = corporate_actions[
        corporate_actions["Symbol"].astype(str).str.upper().eq(str(symbol).upper())
    ].copy()
    actions["Action_Type"] = actions["Action_Type"].astype(str)
    actions = actions[actions["Action_Type"].str.contains(
        r"dividend|distribution", case=False, regex=True, na=False
    )].copy()
    actions["Ex_Date"] = pd.to_datetime(actions["Ex_Date"], errors="coerce")
    actions["cash_per_unit"] = actions["Ratio_or_Amount"].map(_cash_amount)
    actions["included"] = actions["Ex_Date"].notna() & actions["cash_per_unit"].notna()
    diagnostics = actions[
        ["Ex_Date", "Symbol", "Action_Type", "Ratio_or_Amount", "cash_per_unit", "included"]
    ].copy()

    accepted = actions[actions["included"]].groupby("Ex_Date")["cash_per_unit"].sum()
    daily = p.set_index(date_col)[price_col].rename("close").to_frame()
    # Ex-dates may fall on exchange holidays or non-trading days. Attribute
    # cash to the first available trading session on or after the ex-date.
    cash_by_session = pd.Series(0.0, index=daily.index, name="cash_distribution")
    for ex_date, amount in accepted.items():
        session_pos = daily.index.searchsorted(ex_date, side="left")
        if session_pos < len(daily.index):
            session = daily.index[session_pos]
            cash_by_session.loc[session] += float(amount)
    daily["cash_distribution"] = cash_by_session
    daily["previous_close"] = daily["close"].shift(1)
    daily["total_return"] = (
        (daily["close"] + daily["cash_distribution"]) / daily["previous_close"] - 1
    )
    returns = daily["total_return"].replace([np.inf, -np.inf], np.nan).dropna()
    returns.name = f"{symbol}_total_return_proxy"
    diagnostics.attrs["accepted_events"] = int(actions["included"].sum())
    diagnostics.attrs["rejected_events"] = int((~actions["included"]).sum())
    diagnostics.attrs["unmatched_ex_dates"] = int(
        (~actions.loc[actions["included"], "Ex_Date"].isin(daily.index)).sum()
    )
    return returns, diagnostics
