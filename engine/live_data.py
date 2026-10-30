"""Live market data for Wealth AI.

* ETFs: price history from Yahoo Finance (yfinance).
* Mutual funds: daily NAV history from MFapi.in (free, no key).
* PPF, FD, Government Bond: no reliable free API. Dated manual rates in
  data/live_config.json, flagged when stale.

The planning return is a blend of the trailing return and the long-run
assumption in assets.csv, limited to a band around the assumption.
Nothing here raises: on failure the CSV assumption is used.
"""

import json
import threading
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine.goal_recommender import load_assets

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_PATH = DATA_DIR / "live_config.json"
CACHE_PATH = DATA_DIR / "cache" / "live_assets.json"
MFAPI_BASE = "https://api.mfapi.in"

_refresh_lock = threading.Lock()
_refreshing = False


# ------------------------------------------------------------- fetchers
def fetch_yfinance_history(ticker, years=5):
    import yfinance as yf  # lazy import so the app runs without it

    data = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=True)
    close = data["Close"].dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.astype(float)


def _http_json(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": "wealth-ai/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_mfapi_nav(payload):
    rows = payload.get("data") or []
    dates = pd.to_datetime([r["date"] for r in rows], dayfirst=True, errors="coerce")
    navs = pd.to_numeric([r["nav"] for r in rows], errors="coerce")
    series = pd.Series(navs, index=dates).dropna()
    series = series[series > 0]
    return series[~series.index.isna()].sort_index()


def fetch_mfapi_history(scheme_code, years=5):
    payload = _http_json(f"{MFAPI_BASE}/mf/{int(scheme_code)}")
    series = parse_mfapi_nav(payload)
    cutoff = series.index.max() - pd.DateOffset(years=years)
    return series[series.index >= cutoff]


def search_mfapi(query):
    return _http_json(f"{MFAPI_BASE}/mf/search?q={urllib.parse.quote(query)}")


# ------------------------------------------------------------- maths
def compute_stats(prices, min_points=250, min_years=2.0):
    prices = pd.Series(prices).dropna()
    if len(prices) < min_points:
        return None
    span_years = (prices.index[-1] - prices.index[0]).days / 365.25
    if span_years < min_years:
        return None
    cagr = float((prices.iloc[-1] / prices.iloc[0]) ** (1 / span_years) - 1)
    daily = prices.pct_change().dropna()
    vol = float(daily.std() * np.sqrt(252))
    if not np.isfinite(cagr) or not np.isfinite(vol):
        return None
    return {
        "cagr": cagr,
        "volatility": vol,
        "as_of": prices.index[-1].date().isoformat(),
        "observations": int(len(prices)),
        "span_years": round(span_years, 1),
    }


def planning_assumptions(stats, assumed_return, assumed_vol, settings):
    w = settings["blend_with_assumption"]
    shift = settings["max_return_shift"]
    blended = w * assumed_return + (1 - w) * stats["cagr"]
    ret = min(max(blended, assumed_return - shift), assumed_return + shift)
    vol = min(max(stats["volatility"], 0.5 * assumed_vol), 2.0 * assumed_vol)
    return float(ret), float(vol)


# ------------------------------------------------------------- config/cache
def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _read_cache(path=CACHE_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _cache_age_hours(cache):
    try:
        fetched = datetime.fromisoformat(cache["fetched_at"])
        return (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        return None


def refresh_live_assets(
    base_assets=None, config=None, cache_path=CACHE_PATH,
    yf_fetch=fetch_yfinance_history, mf_fetch=fetch_mfapi_history,
):
    """Fetch every market asset and write the cache. Returns a status report."""
    base = load_assets() if base_assets is None else base_assets
    config = config or load_config()
    settings = config["settings"]
    assumed = {
        str(r["asset_name"]): (float(r["expected_return"]), float(r["volatility"]))
        for _, r in base.iterrows()
    }

    results, report = {}, {}
    for name, spec in config["market"].items():
        if name not in assumed:
            continue
        try:
            if spec["type"] == "yfinance":
                prices = yf_fetch(spec["ticker"], settings["history_years"])
            elif spec["type"] == "mfapi":
                if not spec.get("scheme_code"):
                    report[name] = "skipped: no scheme_code set in live_config.json"
                    continue
                prices = mf_fetch(spec["scheme_code"], settings["history_years"])
            else:
                report[name] = f"skipped: unknown source type {spec['type']!r}"
                continue

            stats = compute_stats(prices)
            if stats is None:
                report[name] = "failed: not enough price history returned"
                continue
            ret, vol = planning_assumptions(stats, *assumed[name], settings)
            results[name] = {
                "expected_return": ret, "volatility": vol,
                "trailing_return": stats["cagr"], "as_of": stats["as_of"],
                "span_years": stats["span_years"],
            }
            report[name] = f"ok: trailing {stats['cagr']:.1%}, planning {ret:.1%}"
        except Exception as error:
            report[name] = f"failed: {type(error).__name__}: {error}"

    if results:
        cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        previous = (_read_cache(cache_path) or {}).get("assets", {})
        merged = {**previous, **results}
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump({
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "assets": merged,
            }, handle, indent=2)
    return report


def _background_refresh():
    global _refreshing
    try:
        refresh_live_assets()
    finally:
        with _refresh_lock:
            _refreshing = False


def _maybe_start_refresh():
    global _refreshing
    with _refresh_lock:
        if _refreshing:
            return
        _refreshing = True
    threading.Thread(target=_background_refresh, daemon=True).start()


# ------------------------------------------------------------- public API
def get_live_assets(base_assets=None, config=None, cache_path=CACHE_PATH,
                    background=True):
    """Assets table with live/manual values applied and a source label per row.

    Never blocks on the network: serves cached values immediately and
    refreshes in the background when the cache is missing or stale.
    """
    base = (load_assets() if base_assets is None else base_assets).copy()
    try:
        config = config or load_config()
    except (OSError, ValueError):
        config = None

    base["data_source"] = "assumption"
    base["data_as_of"] = None
    base["data_note"] = "Long-run assumption from assets.csv"
    if config is None:
        return base

    today = date.today()
    index = {str(n): i for i, n in zip(base.index, base["asset_name"])}

    for name, spec in config.get("manual", {}).items():
        if name not in index:
            continue
        i = index[name]
        base.at[i, "expected_return"] = float(spec["annual_rate"])
        as_of = spec.get("as_of")
        base.at[i, "data_as_of"] = as_of
        if as_of is None:
            base.at[i, "data_source"] = "manual (unverified)"
            base.at[i, "data_note"] = f"{spec.get('source', 'manual rate')} - date not set"
        else:
            age = (today - date.fromisoformat(as_of)).days
            stale = age > int(spec.get("review_days", 90))
            base.at[i, "data_source"] = "manual (stale)" if stale else "manual"
            base.at[i, "data_note"] = (
                f"{spec.get('source', 'manual rate')}, set {age} days ago"
                + (" - please review" if stale else "")
            )

    cache = _read_cache(cache_path)
    max_age = config["settings"]["cache_hours"]
    if cache:
        age = _cache_age_hours(cache)
        fresh = age is not None and age <= max_age
        for name, entry in cache.get("assets", {}).items():
            if name not in index:
                continue
            i = index[name]
            base.at[i, "expected_return"] = float(entry["expected_return"])
            base.at[i, "volatility"] = float(entry["volatility"])
            base.at[i, "data_as_of"] = entry.get("as_of")
            base.at[i, "data_source"] = "live" if fresh else "live (cached, older)"
            base.at[i, "data_note"] = (
                f"Blend of {entry.get('span_years', '?')}-year trailing return "
                f"({entry['trailing_return']:.1%}) and long-run assumption"
            )
        stale_cache = not fresh
    else:
        stale_cache = True

    if stale_cache and background and config.get("market"):
        _maybe_start_refresh()
    return base


def describe_sources(assets, asset_names):
    out = []
    for name in asset_names:
        row = assets[assets["asset_name"] == name]
        if row.empty or "data_source" not in row.columns:
            continue
        r = row.iloc[0]
        out.append({
            "asset_name": name,
            "source": str(r["data_source"]),
            "as_of": None if pd.isna(r["data_as_of"]) else str(r["data_as_of"]),
            "note": str(r["data_note"]),
            "annual_return": float(r["expected_return"]),
        })
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wealth AI live data")
    parser.add_argument("--refresh", action="store_true", help="fetch and cache now")
    parser.add_argument("--search", metavar="NAME", help="find a mutual fund scheme code")
    args = parser.parse_args()

    if args.search:
        for scheme in search_mfapi(args.search)[:15]:
            print(scheme["schemeCode"], scheme["schemeName"])
    else:
        for asset, status in refresh_live_assets().items():
            print(f"{asset}: {status}")
        table = get_live_assets(background=False)
        print(table[["asset_name", "expected_return", "volatility", "data_source", "data_as_of"]]
              .to_string(index=False))