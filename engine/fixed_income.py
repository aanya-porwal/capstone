"""Fixed-income scenario tools; yields are not treated as realised bond returns."""
from __future__ import annotations
import numpy as np
import pandas as pd


def bond_price_change_from_yield(duration_years: float, yield_change_bps: float,
                                 convexity: float = 0.0) -> float:
    """Approximate percentage price change using duration/convexity.

    Modified duration and convexity must be supplied for the specific bond or
    portfolio. The result is a local sensitivity approximation, not a return
    history or a substitute for full cash-flow repricing.
    """
    if duration_years < 0 or convexity < 0:
        raise ValueError("Duration and convexity must be non-negative")
    dy = float(yield_change_bps) / 10000.0
    return float(-duration_years * dy + 0.5 * convexity * dy * dy)


def yield_curve_scenarios(yield_series: pd.Series, shocks_bps=(-100, -50, 0, 50, 100),
                          duration_years=5.0, convexity=0.0) -> pd.DataFrame:
    """Apply parallel yield shocks to the latest observed yield."""
    s = pd.to_numeric(pd.Series(yield_series), errors="coerce").dropna()
    if s.empty:
        raise ValueError("No valid government bond yield observations")
    latest = float(s.iloc[-1])
    return pd.DataFrame([{
        "latest_yield_pct": latest,
        "shock_bps": int(shock),
        "approx_price_change_pct": 100 * bond_price_change_from_yield(
            duration_years, shock, convexity
        ),
        "duration_years_assumed": float(duration_years),
        "convexity_assumed": float(convexity),
        "warning": "Illustrative parallel-shift sensitivity; yield series is not bond total return.",
    } for shock in shocks_bps])
