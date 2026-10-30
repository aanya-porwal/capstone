"""Reusable financial-data quality and point-in-time validation utilities.

These checks report defects; they do not silently repair or certify financial data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def audit_price_frame(
    frame: pd.DataFrame,
    *,
    date_col: str = "Date",
    value_col: str = "close",
    availability_col: str | None = None,
) -> dict:
    """Return transparent quality diagnostics for a price/NAV observation table."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("frame must be a non-empty DataFrame")
    missing = {date_col, value_col} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    values = pd.to_numeric(frame[value_col], errors="coerce")
    valid_dates = dates.dropna()
    valid_values = values.dropna()
    duplicate_dates = int(dates[dates.notna()].duplicated(keep=False).sum())
    non_positive = int((values.notna() & values.le(0)).sum())
    invalid_numeric = int(values.isna().sum())
    invalid_dates = int(dates.isna().sum())
    ordered = dates.dropna()
    out_of_order = int((ordered.diff().dt.total_seconds().dropna() < 0).sum())
    availability_issues = None
    if availability_col:
        if availability_col not in frame.columns:
            raise ValueError(f"Missing availability column: {availability_col}")
        available = pd.to_datetime(frame[availability_col], errors="coerce")
        availability_issues = int((available.isna() | (available < dates)).sum())
    return {
        "rows": int(len(frame)),
        "valid_dates": int(dates.notna().sum()),
        "valid_values": int(values.notna().sum()),
        "invalid_dates": invalid_dates,
        "invalid_numeric_values": invalid_numeric,
        "non_positive_values": non_positive,
        "duplicate_date_rows": duplicate_dates,
        "out_of_order_steps": out_of_order,
        "start_date": str(valid_dates.min().date()) if not valid_dates.empty else None,
        "end_date": str(valid_dates.max().date()) if not valid_dates.empty else None,
        "availability_issues": availability_issues,
        "passes_basic_checks": bool(
            invalid_dates == 0 and invalid_numeric == 0 and non_positive == 0
            and duplicate_dates == 0 and out_of_order == 0
            and (availability_issues in (None, 0))
        ),
        "note": "Diagnostics only; passing checks do not establish source accuracy, total-return completeness or investibility.",
    }


def point_in_time_filter(
    frame: pd.DataFrame,
    as_of,
    *,
    available_at_col: str = "available_at",
) -> pd.DataFrame:
    """Keep only records known by the requested decision timestamp.

    The source availability timestamp, not the observation/economic period,
    controls eligibility. Unknown timestamps are excluded conservatively.
    """
    if available_at_col not in frame.columns:
        raise ValueError(f"Missing availability column: {available_at_col}")
    cutoff = pd.Timestamp(as_of)
    available = pd.to_datetime(frame[available_at_col], errors="coerce")
    mask = available.notna() & (available <= cutoff)
    return frame.loc[mask].copy()
