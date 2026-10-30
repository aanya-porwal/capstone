"""Load and audit the external Indian-market research repository.

The raw repository is deliberately kept outside the DWMS Git repository.
Set DWMS_RESEARCH_DATA_DIR to its clone root, or use the default sibling
folder ../dwms_research_data. All loaders return source data without silently
converting yields, spot bullion, or price indices into investible total returns.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd

REPOSITORY = "https://github.com/aswinv90/indian-market-historical-data"
DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "dwms_research_data"


def get_research_root(root: str | Path | None = None) -> Path:
    """Resolve the local clone root; environment variable takes precedence."""
    candidate = Path(root or os.getenv("DWMS_RESEARCH_DATA_DIR") or DEFAULT_ROOT).expanduser()
    return candidate.resolve()


def _path(root: str | Path | None, relative: str, required: bool = True) -> Path | None:
    p = get_research_root(root) / relative
    if not p.exists():
        if required:
            raise FileNotFoundError(
                f"Research dataset file not found: {p}. Clone {REPOSITORY} "
                "or set DWMS_RESEARCH_DATA_DIR to its local folder."
            )
        return None
    return p


def read_table(relative: str, root: str | Path | None = None,
               columns: list[str] | None = None) -> pd.DataFrame:
    """Read a CSV or Parquet file based on extension."""
    p = _path(root, relative)
    if p.suffix.lower() == ".parquet":
        return pd.read_parquet(p, columns=columns)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p, usecols=columns)
    raise ValueError(f"Unsupported research-data format: {p.suffix}")


def load_index(symbol: str = "NIFTY_50", root: str | Path | None = None) -> pd.DataFrame:
    """Load a benchmark/sector index. Index levels are not assumed to be TRI."""
    symbol = symbol.upper().strip()
    if not symbol.replace("_", "").isalnum():
        raise ValueError("Invalid index symbol")
    df = read_table(f"data/INDICES/{symbol}.parquet", root)
    return normalise_market_frame(df)


def load_listed_security(symbol: str, exchange: str = "NSE",
                         root: str | Path | None = None) -> pd.DataFrame:
    """Load a listed security by exchange symbol (NSE or BSE)."""
    symbol = symbol.upper().strip()
    exchange = exchange.upper().strip()
    if not symbol.replace("_", "").isalnum() or exchange not in {"NSE", "BSE"}:
        raise ValueError("Use an alphanumeric symbol and exchange NSE or BSE")
    suffix = "NS" if exchange == "NSE" else "BO"
    return normalise_market_frame(read_table(f"data/{exchange}/{symbol}_{suffix}.parquet", root))


def normalise_market_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise common OHLCV/index layouts without inventing missing fields."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    if "Date" not in out.columns:
        if isinstance(out.index, pd.DatetimeIndex):
            out = out.reset_index().rename(columns={out.index.name or "index": "Date"})
        elif "date" in out.columns:
            out = out.rename(columns={"date": "Date"})
    if "Date" not in out.columns:
        raise ValueError(f"Cannot identify date column. Available: {list(out.columns)}")
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    for col in ("Open", "High", "Low", "Close", "Adj Close", "Volume", "close", "Adj_Close"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    close_col = next((c for c in ("Adj Close", "Adj_Close", "Close", "close") if c in out), None)
    if close_col:
        out = out.rename(columns={close_col: "close"})
    out = out.dropna(subset=["Date"]).sort_values("Date")
    out = out.drop_duplicates("Date", keep="last").reset_index(drop=True)
    if "close" in out:
        out = out[out["close"].gt(0)]
    return out


def load_commodity(name: str, root: str | Path | None = None) -> pd.DataFrame:
    """Load GOLD or SILVER INR bullion observations; these are not ETF returns."""
    name = name.upper().strip()
    if name not in {"GOLD", "SILVER"}:
        raise ValueError("Commodity must be GOLD or SILVER")
    return read_table(f"data/COMMODITIES/{name}_INR.parquet", root)


def load_macro(name: str, root: str | Path | None = None) -> pd.DataFrame:
    """Load CPI, FX, 10-year yield, or RBI policy history as published."""
    files = {
        "CPI": "cpi_inflation.parquet",
        "FX": "forex_rates.parquet",
        "GSEC_10Y_YIELD": "in10y_bond_yield.parquet",
        "RBI_POLICY": "rbi_policy_rates.parquet",
    }
    key = name.upper().strip()
    if key not in files:
        raise ValueError(f"Macro name must be one of {sorted(files)}")
    return read_table(f"data/MACRO/{files[key]}", root)


def load_sgb(dataset: str = "master", root: str | Path | None = None) -> pd.DataFrame:
    files = {
        "master": "sgb_master_catalog.parquet",
        "cashflows": "sgb_cash_flows.parquet",
        "market_prices": "sgb_market_prices.parquet",
    }
    key = dataset.lower().strip()
    if key not in files:
        raise ValueError(f"SGB dataset must be one of {sorted(files)}")
    return read_table(f"data/SGB/{files[key]}", root)


def load_mutual_fund_catalog(root: str | Path | None = None) -> pd.DataFrame:
    return read_table("data/MF/mf_meta.parquet", root)


def load_mutual_fund_nav(scheme_code: int, root: str | Path | None = None) -> pd.DataFrame:
    """Load one scheme from its documented schemeCode modulo-10 NAV partition."""
    code = int(scheme_code)
    if code <= 0:
        raise ValueError("scheme_code must be a positive integer")
    part = code % 10
    p = _path(root, f"data/MF/nav_part_{part}.parquet")
    try:
        df = pd.read_parquet(p, columns=["date", "schemeCode", "nav"],
                             filters=[("schemeCode", "==", code)])
    except (ValueError, TypeError):
        df = pd.read_parquet(p, columns=["date", "schemeCode", "nav"])
        df = df.loc[df["schemeCode"].astype("int64").eq(code)]
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["nav"] = pd.to_numeric(out["nav"], errors="coerce")
    out = out.dropna(subset=["date", "nav"])
    out = out[out["nav"].gt(0)].sort_values("date").drop_duplicates("date", keep="last")
    return out.reset_index(drop=True)

def load_corporate_actions(root: str | Path | None = None) -> pd.DataFrame:
    return read_table("data/CORPORATE_ACTIONS/corporate_actions.parquet", root)


def load_gold_etf_prices(root: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Load listed gold ETF price proxies; these are not bullion spot prices."""
    candidates = {
        "Nippon India ETF Gold BeES": ("GOLDBEES", "BSE"),
        "BSL Gold ETF": ("BSLGOLDETF", "BSE"),
        "Quantum Gold Fund": ("QGOLDHALF", "BSE"),
        "Groww Gold ETF": ("GROWWGOLD", "BSE"),
    }
    result = {}
    for name, (symbol, exchange) in candidates.items():
        try:
            result[name] = load_listed_security(symbol, exchange, root)
        except FileNotFoundError:
            continue
    return result

def load_reit_invit_prices(root: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Load known listed REIT/InvIT symbols when present in the source clone.

    Returns price histories only. Total return requires adding trust distributions
    and applying the correct tax/withholding treatment; this function does not do so.
    """
    candidates = {
        "Embassy REIT": ("EMBASSY", "BSE"),
        "Mindspace REIT": ("MINDSPACE", "BSE"),
        "Brookfield India REIT": ("BIRET", "BSE"),
        "Nexus Select Trust": ("NEXUSSURGL", "BSE"),
        "IndiGrid InvIT": ("INDIGRID", "BSE"),
        "IRB InvIT": ("IRBINVIT", "BSE"),
        "PowerGrid InvIT": ("PGINVIT", "BSE"),
    }
    result = {}
    for name, (symbol, exchange) in candidates.items():
        try:
            result[name] = load_listed_security(symbol, exchange, root)
        except FileNotFoundError:
            continue
    return result


def build_coverage_report(root: str | Path | None = None) -> pd.DataFrame:
    """Inventory key datasets with presence, size, rows and date coverage."""
    base = get_research_root(root)
    definitions = [
        ("NIFTY_50", "data/INDICES/NIFTY_50.parquet", "benchmark price index"),
        ("NIFTY_500", "data/INDICES/NIFTY_500.parquet", "broad-market price index"),
        ("GOLD_INR", "data/COMMODITIES/GOLD_INR.parquet", "spot bullion reference"),
        ("SILVER_INR", "data/COMMODITIES/SILVER_INR.parquet", "spot bullion reference"),
        ("MF_CATALOG", "data/MF/mf_meta.parquet", "scheme metadata"),
        ("MF_NAV_PART_0", "data/MF/nav_part_0.parquet", "mutual-fund NAV partition"),
        ("SGB_MASTER", "data/SGB/sgb_master_catalog.parquet", "bond master"),
        ("SGB_CASHFLOWS", "data/SGB/sgb_cash_flows.parquet", "coupon/principal cashflows"),
        ("SGB_QUOTES", "data/SGB/sgb_market_prices.parquet", "secondary-market quotes"),
        ("CORPORATE_ACTIONS", "data/CORPORATE_ACTIONS/corporate_actions.parquet", "corporate actions"),
        ("CPI", "data/MACRO/cpi_inflation.parquet", "inflation index"),
        ("FX", "data/MACRO/forex_rates.parquet", "FX rates"),
        ("GSEC_10Y_YIELD", "data/MACRO/in10y_bond_yield.parquet", "yield series, not bond total return"),
        ("RBI_POLICY", "data/MACRO/rbi_policy_rates.parquet", "policy-rate events"),
    ]
    rows = []
    for name, rel, kind in definitions:
        p = base / rel
        row = {"dataset": name, "kind": kind, "path": rel, "exists": p.is_file(),
               "size_mb": round(p.stat().st_size / 1024**2, 3) if p.is_file() else None,
               "rows": None, "start_date": None, "end_date": None, "status": "missing"}
        if p.is_file():
            try:
                if p.suffix == ".parquet":
                    import pyarrow.parquet as pq
                    pf = pq.ParquetFile(p)
                    row["rows"] = pf.metadata.num_rows
                    row["status"] = "present"
                    names = set(pf.schema.names)
                    date_col = next((c for c in ("Date", "date") if c in names), None)
                    if date_col:
                        dates = pd.read_parquet(p, columns=[date_col])[date_col]
                        parsed = pd.to_datetime(dates, errors="coerce").dropna()
                        if not parsed.empty:
                            row["start_date"] = str(parsed.min().date())
                            row["end_date"] = str(parsed.max().date())
                else:
                    row["rows"] = max(sum(1 for _ in p.open(encoding="utf-8")) - 1, 0)
                    row["status"] = "present"
            except Exception as exc:
                row["status"] = f"read_error: {type(exc).__name__}: {exc}"
        rows.append(row)
    return pd.DataFrame(rows)


def load_asset_return_series(asset: str, root: str | Path | None = None,
                             scheme_code: int | None = None) -> pd.Series:
    """Return daily simple returns for supported empirical price/NAV series.

    Supported: index:<SYMBOL>, security:<EXCHANGE>:<SYMBOL>, mf:<scheme_code>.
    Spot gold/silver and bond yields are intentionally not exposed here as
    investible returns; use load_commodity/load_macro and define an explicit
    investible proxy/valuation methodology first.
    """
    parts = asset.split(":")
    if parts[0] == "index" and len(parts) == 2:
        frame = load_index(parts[1], root)
    elif parts[0] == "security" and len(parts) == 3:
        frame = load_listed_security(parts[2], parts[1], root)
    elif parts[0] == "mf" and len(parts) == 2:
        frame = load_mutual_fund_nav(int(parts[1]), root).rename(columns={"date": "Date", "nav": "close"})
    else:
        raise ValueError("Use index:<SYMBOL>, security:<NSE|BSE>:<SYMBOL>, or mf:<scheme_code>")
    if "close" not in frame or len(frame) < 2:
        raise ValueError("Series has insufficient valid price/NAV observations")
    returns = frame.set_index("Date")["close"].pct_change().dropna()
    returns.name = asset
    return returns
