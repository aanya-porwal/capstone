"""Build a local daily price panel from the separately cloned research dataset.

Outputs are price histories, not automatically total-return histories. Raw
source files remain outside this repository. Run after setting
DWMS_RESEARCH_DATA_DIR.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

from engine.distribution_returns import distribution_adjusted_returns
from engine.research_data import (
    get_research_root, load_index, load_listed_security, load_corporate_actions,
)

INDEXES = {
    "Nifty 100 Index Proxy": ("NIFTY_100", "nifty_100_index_proxy"),
    "Nifty 200 Index Proxy": ("NIFTY_200", "nifty_200_index_proxy"),
    "Nifty 500 Index Proxy": ("NIFTY_500", "nifty_500_index_proxy"),
    "Nifty Bank Index Proxy": ("NIFTY_BANK", "nifty_bank_index_proxy"),
    "Nifty IT Index Proxy": ("NIFTY_IT", "nifty_it_index_proxy"),
    "Nifty Pharma Index Proxy": ("NIFTY_PHARMA", "nifty_pharma_index_proxy"),
    "Nifty Midcap 50 Index Proxy": ("NIFTY_MIDCAP_50", "nifty_midcap_50_index_proxy"),
    "Sensex Index Proxy": ("SENSEX", "sensex_index_proxy"),
}
SECURITIES = {
    "Gold BeES ETF Price": ("GOLDBEES", "BSE", "gold_bees_etf_price"),
    "Embassy REIT Price": ("EMBASSY", "BSE", "embassy_reit_price"),
    "Mindspace REIT Price": ("MINDSPACE", "BSE", "mindspace_reit_price"),
    "Brookfield India REIT Price": ("BIRET", "BSE", "brookfield_reit_price"),
    "Nexus Select Trust Price": ("NEXUSSURGL", "BSE", "nexus_select_trust_price"),
    "IndiGrid InvIT Price": ("INDIGRID", "BSE", "indigrid_invit_price"),
    "IRB InvIT Price": ("IRBINVIT", "BSE", "irb_invit_price"),
    "PowerGrid InvIT Price": ("PGINVIT", "BSE", "powergrid_invit_price"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/prices")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []

    def save(name, slug, frame, source_type, source_path):
        if "close" not in frame or frame.empty:
            raise ValueError("No usable close price")
        data = frame[["Date", "close"]].dropna().sort_values("Date")
        data = data.drop_duplicates("Date", keep="last")
        path = outdir / f"{slug}.csv"
        data.to_csv(path, index=False)
        rows.append({
            "asset": name, "file": str(path).replace("\\", "/"),
            "source": source_path, "source_type": source_type,
            "observations": int(len(data)),
            "start_date": str(data.Date.min().date()),
            "end_date": str(data.Date.max().date()),
            "return_status": "price return only; distributions/TRI not established",
        })

    for name, (symbol, slug) in INDEXES.items():
        try:
            save(name, slug, load_index(symbol, args.root),
                 "index level; TRI status unverified", f"data/INDICES/{symbol}.parquet")
        except (FileNotFoundError, ValueError) as exc:
            rows.append({"asset": name, "source": f"data/INDICES/{symbol}.parquet",
                         "status": f"not_loaded: {exc}"})

    actions = None
    try:
        actions = load_corporate_actions(args.root)
    except FileNotFoundError:
        pass

    trust_symbols = {"EMBASSY", "MINDSPACE", "BIRET", "NEXUSSURGL",
                     "INDIGRID", "IRBINVIT", "PGINVIT"}
    for name, (symbol, exchange, slug) in SECURITIES.items():
        try:
            frame = load_listed_security(symbol, exchange, args.root)
            save(name, slug, frame,
                 "listed security close; corporate-action/distribution adjustment unverified",
                 f"data/{exchange}/{symbol}_{'BO' if exchange == 'BSE' else 'NS'}.parquet")
            if symbol in trust_symbols and actions is not None:
                try:
                    daily_returns, diag = distribution_adjusted_returns(
                        frame, actions, symbol, date_col="Date", price_col="close"
                    )
                    tri = (1 + daily_returns).cumprod() * 100.0
                    tri_frame = tri.rename("close").rename_axis("Date").reset_index()
                    tri_frame.to_csv(outdir / f"{slug}_total_return_proxy.csv", index=False)
                    rows.append({
                        "asset": name, "file": str(outdir / f"{slug}_total_return_proxy.csv").replace("\\\\", "/"),
                        "source": "listed price + corporate_actions dividend/distribution events",
                        "source_type": "synthetic total-return proxy; only parseable cash distributions included",
                        "observations": int(len(tri_frame)),
                        "start_date": str(tri_frame.Date.min().date()),
                        "end_date": str(tri_frame.Date.max().date()),
                        "accepted_distribution_events": diag.attrs.get("accepted_events", 0),
                        "rejected_distribution_events": diag.attrs.get("rejected_events", 0),
                        "unmatched_ex_dates": diag.attrs.get("unmatched_ex_dates", 0),
                    })
                except (ValueError, KeyError) as exc:
                    rows.append({"asset": name, "source": "corporate_actions",
                                 "status": f"distribution_adjustment_not_applied: {exc}"})
        except (FileNotFoundError, ValueError) as exc:
            rows.append({"asset": name, "source": f"data/{exchange}/{symbol}",
                         "status": f"not_loaded: {exc}"})

    manifest = {
        "source_repository": "https://github.com/aswinv90/indian-market-historical-data",
        "source_root": str(get_research_root(args.root)),
        "method": "Daily close-level returns; for listed trusts, a separate distribution-adjusted proxy is emitted only when parseable dividend/distribution events are available. Index TRI status remains unverified.",
        "assets": rows,
    }
    (outdir / "research_price_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nSaved local price panel to {outdir}")


if __name__ == "__main__":
    main()
