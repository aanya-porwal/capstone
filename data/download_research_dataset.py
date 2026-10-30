#!/usr/bin/env python3
"""Download reproducible Indian-market research data for DWMS.

Primary source: NSE Indices public (undocumented) TRI endpoint.
Gold ETF proxy: Yahoo Finance chart endpoint via yfinance (optional).
All downloads are saved under data/market_data; raw responses are retained.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "market_data"
RAW = OUT / "raw"
PROCESSED = OUT / "processed"
MANIFEST = OUT / "download_manifest.json"
BASE = "https://www.niftyindices.com"
TRI_URL = BASE + "/Backpage.aspx/getTotalReturnIndexString"
REFERER = BASE + "/reports/historical-data"
HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": REFERER,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

# Exact display names used by the Nifty Indices historical-data selector.
# The endpoint can return an empty list for an unavailable or misspelled series;
# failures are recorded rather than silently substituted.
NIFTY_SERIES = [
    ("NIFTY 50", "equity_broad_market"),
    ("NIFTY NEXT 50", "equity_broad_market"),
    ("NIFTY MIDCAP 150", "equity_broad_market"),
    ("NIFTY SMALLCAP 250", "equity_broad_market"),
    ("NIFTY 500", "equity_broad_market"),
    ("NIFTY 10 YR BENCHMARK G-SEC", "fixed_income_government"),
    ("NIFTY 5 YR BENCHMARK G-SEC", "fixed_income_government"),
    ("NIFTY AAA CORPORATE BOND", "fixed_income_corporate"),
    ("NIFTY BANKING & PSU DEBT", "fixed_income_corporate"),
]
GOLD_TICKERS = ["GOLDBEES.NS"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
LOG = logging.getLogger("dwms-data")


def chunks(start: date, end: date, days: int = 360):
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=days - 1), end)
        yield cursor, stop
        cursor = stop + timedelta(days=1)


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_tri_response(response: requests.Response) -> list[dict[str, Any]]:
    response.raise_for_status()
    payload = response.json()
    inner = payload.get("d")
    if isinstance(inner, str):
        rows = json.loads(inner)
    elif isinstance(inner, list):
        rows = inner
    else:
        raise ValueError(f"Unexpected TRI response shape: {str(payload)[:300]}")
    if not isinstance(rows, list):
        raise ValueError("TRI response 'd' was not a list")
    return rows


def fetch_tri(session: requests.Session, index_name: str, start: date, end: date, delay: float) -> pd.DataFrame:
    collected: list[dict[str, Any]] = []
    for first, last in chunks(start, end):
        # Nifty's ASP.NET method expects cinfo to be a single-quoted string.
        cinfo = "{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (
            index_name, first.strftime("%d-%b-%Y"), last.strftime("%d-%b-%Y"), index_name
        )
        body = json.dumps({"cinfo": cinfo})
        last_error = None
        for attempt in range(4):
            try:
                response = session.post(TRI_URL, data=body, headers=HEADERS, timeout=(10, 75))
                rows = parse_tri_response(response)
                collected.extend(rows)
                break
            except Exception as exc:  # retries are bounded and recorded
                last_error = exc
                if attempt == 3:
                    raise RuntimeError(f"{index_name} {first}–{last}: {exc}") from exc
                wait = min(2 ** attempt, 8)
                LOG.warning("Retry %s (%s), waiting %ss", index_name, type(exc).__name__, wait)
                time.sleep(wait)
        time.sleep(delay)

    if not collected:
        return pd.DataFrame(columns=["date", "tri", "ntr", "index_name"])

    frame = pd.DataFrame(collected)
    date_col = next((c for c in ["Date", "HistoricalDate", "date"] if c in frame.columns), None)
    tri_col = next((c for c in ["TotalReturnsIndex", "Total Return Index", "TRI", "tri"] if c in frame.columns), None)
    ntr_col = next((c for c in ["NTR_Value", "NTR Value", "NTR", "ntr"] if c in frame.columns), None)
    if not date_col or not tri_col:
        raise ValueError(f"Could not identify date/TRI fields for {index_name}. Returned columns: {list(frame.columns)}")
    out = pd.DataFrame({
        "date": pd.to_datetime(frame[date_col], errors="coerce", dayfirst=True),
        "tri": pd.to_numeric(frame[tri_col].astype(str).str.replace(",", "", regex=False), errors="coerce"),
        "ntr": pd.to_numeric(frame[ntr_col].astype(str).str.replace(",", "", regex=False), errors="coerce") if ntr_col else pd.NA,
        "index_name": index_name,
    })
    out = out.dropna(subset=["date", "tri"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    out = out[(out.date.dt.date >= start) & (out.date.dt.date <= end)]
    return out


def fetch_gold_yfinance(ticker: str, start: date, end: date) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is not installed; run pip install yfinance") from exc
    # yfinance end is exclusive. auto_adjust=True adjusts for distributions/splits.
    data = yf.download(ticker, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                       auto_adjust=True, progress=False, threads=False)
    if data.empty:
        raise RuntimeError(f"No Yahoo Finance observations returned for {ticker}")
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    out = pd.DataFrame({"date": pd.to_datetime(close.index).tz_localize(None), "adjusted_close": close.to_numpy()})
    out["ticker"] = ticker
    return out.dropna().sort_values("date").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Nifty TRI and Gold ETF research series for DWMS")
    parser.add_argument("--start-date", default="1999-01-01", help="YYYY-MM-DD; defaults to 1999-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat(), help="YYYY-MM-DD; defaults to today")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between Nifty requests")
    parser.add_argument("--skip-gold", action="store_true", help="Skip Yahoo Finance Gold ETF download")
    parser.add_argument("--indices", nargs="*", default=None, help="Optional exact Nifty index names to fetch")
    args = parser.parse_args()
    try:
        start, end = date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)
    except ValueError as exc:
        parser.error(str(exc))
    if start > end:
        parser.error("--start-date must be on or before --end-date")

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "created_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "sources": [], "failures": [],
        "methodology": {
            "nifty": "NSE Indices public TRI endpoint; TotalReturnsIndex is used (dividends reinvested). NTR retained separately.",
            "gold": "Yahoo Finance adjusted-close proxy for GOLDBEES.NS; not an official benchmark TRI or guaranteed complete NAV history.",
            "returns": "Compute simple/log returns from the level series; do not concatenate unrelated proxy histories without documenting the splice.",
            "limitations": "Undocumented public endpoint and third-party market-data proxy; verify coverage and source terms before publication or production use. No synthetic backfill is created.",
        },
    }
    session = requests.Session()
    # Best-effort site bootstrap; endpoint request itself remains the authoritative test.
    try:
        session.get(REFERER, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=(5, 8))
    except requests.RequestException:
        LOG.info("Nifty page bootstrap unavailable; trying data endpoint directly")

    selected = set(args.indices or [name for name, _ in NIFTY_SERIES])
    for name, category in NIFTY_SERIES:
        if name not in selected:
            continue
        LOG.info("Downloading Nifty TRI: %s", name)
        try:
            df = fetch_tri(session, name, start, end, args.delay)
            if df.empty:
                raise RuntimeError("Endpoint returned no observations; verify canonical index name/availability")
            slug = safe_name(name)
            raw_path = RAW / f"{slug}_tri_raw.json"
            # Preserve normalised rows from endpoint, not just transformed returns.
            df.to_json(raw_path, orient="records", date_format="iso", indent=2)
            csv_path = PROCESSED / f"{slug}_tri.csv"
            df.to_csv(csv_path, index=False)
            manifest["sources"].append({
                "series": name, "category": category, "source": TRI_URL,
                "data_type": "Total Return Index (TRI)", "file": str(csv_path.relative_to(ROOT)),
                "raw_file": str(raw_path.relative_to(ROOT)), "observations": int(len(df)),
                "first_date": df.date.min().date().isoformat(), "last_date": df.date.max().date().isoformat(),
                "fields": list(df.columns), "status": "downloaded",
            })
            LOG.info("  %s rows: %s to %s", len(df), df.date.min().date(), df.date.max().date())
        except Exception as exc:
            LOG.error("  FAILED: %s", exc)
            manifest["failures"].append({"series": name, "source": TRI_URL, "error": str(exc)})

    if not args.skip_gold:
        for ticker in GOLD_TICKERS:
            LOG.info("Downloading gold ETF adjusted-close proxy: %s", ticker)
            try:
                df = fetch_gold_yfinance(ticker, start, end)
                slug = safe_name(ticker)
                path = PROCESSED / f"{slug}_adjusted_close.csv"
                df.to_csv(path, index=False)
                manifest["sources"].append({
                    "series": ticker, "category": "gold_etf_proxy", "source": "Yahoo Finance chart data via yfinance",
                    "data_type": "ETF adjusted close proxy", "file": str(path.relative_to(ROOT)),
                    "observations": int(len(df)), "first_date": df.date.min().date().isoformat(),
                    "last_date": df.date.max().date().isoformat(), "status": "downloaded",
                    "limitations": "Not an official Gold TRI; vendor adjustments and historical coverage should be independently checked.",
                })
                LOG.info("  %s rows: %s to %s", len(df), df.date.min().date(), df.date.max().date())
            except Exception as exc:
                LOG.error("  FAILED: %s", exc)
                manifest["failures"].append({"series": ticker, "source": "Yahoo Finance", "error": str(exc)})

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = len(manifest["sources"])
    failed = len(manifest["failures"])
    LOG.info("Finished: %d series downloaded, %d failed. Manifest: %s", ok, failed, MANIFEST)
    LOG.info("No failed series were replaced with assumptions or synthetic data.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
