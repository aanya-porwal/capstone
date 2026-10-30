"""Screen the source mutual-fund catalogue and optionally export NAV histories.

The source has tens of thousands of schemes. This script does not treat every
scheme as a distinct investible product: it flags plan/option/category and
history metadata, then creates a small review shortlist per category.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from engine.research_data import get_research_root, load_mutual_fund_catalog


def classify_category(row) -> str:
    text = " ".join(str(row.get(k, "")) for k in ("category", "schemeName", "schemeType")).lower()
    rules = [
        ("Overnight/Liquid", ("overnight", "liquid")),
        ("Money Market/Ultra Short", ("money market", "ultra short", "low duration", "short duration")),
        ("Debt/Gilt", ("gilt", "government bond", "corporate bond", "credit risk", "dynamic bond", "banking and psu")),
        ("Hybrid/Allocation", ("hybrid", "balanced advantage", "multi asset", "equity savings", "arbitrage")),
        ("Index/ETF", ("index fund", "etf", "nifty", "sensex")),
        ("ELSS/Tax Saver", ("elss", "tax saver")),
        ("Large Cap", ("large cap", "largecap")),
        ("Large & Mid Cap", ("large & mid", "large and mid")),
        ("Flexi/Multi Cap", ("flexi cap", "multicap", "multi cap")),
        ("Mid Cap", ("mid cap", "midcap")),
        ("Small Cap", ("small cap", "smallcap")),
        ("Focused", ("focused", "focus fund")),
        ("Sector/Thematic", ("sectoral", "thematic", "pharma", "bank", "technology", "infrastructure", "consumption", "energy")),
        ("International", ("international", "overseas", "global", "nasdaq", "s&p 500", "hang seng")),
        ("Retirement/Solution", ("retirement", "children", "solution oriented")),
    ]
    for label, needles in rules:
        if any(n in text for n in needles):
            return label
    return "Other/Unclassified"


def plan_option(name: str) -> tuple[str, str]:
    s = str(name).lower()
    plan = "Direct" if re.search(r"\bdirect\b", s) else ("Regular" if re.search(r"\bregular\b", s) else "Unclear")
    if "growth" in s:
        option = "Growth"
    elif any(x in s for x in ("idcw", "dividend", "payout", "reinvestment")):
        option = "IDCW/Dividend"
    else:
        option = "Unclear"
    return plan, option


def build_shortlist(root=None, min_records=500, per_category=3, output_dir="data", min_history_years=3):
    meta = load_mutual_fund_catalog(root).copy()
    required = {"schemeName", "category", "schemeType", "records", "oldestDate", "latestDate"}
    missing = required - set(meta.columns)
    if missing:
        raise ValueError(f"MF catalogue missing expected columns: {sorted(missing)}")
    meta["records"] = pd.to_numeric(meta["records"], errors="coerce").fillna(0).astype(int)
    meta["latestDate"] = pd.to_datetime(meta["latestDate"], errors="coerce")
    meta["oldestDate"] = pd.to_datetime(meta["oldestDate"], errors="coerce")
    # The source README documents schemeCode as the Parquet index; tolerate
    # either an explicit column or that documented index representation.
    if "schemeCode" in meta.columns:
        codes = meta["schemeCode"]
    elif "scheme_code" in meta.columns:
        codes = meta["scheme_code"]
    else:
        codes = pd.Series(meta.index, index=meta.index)
    meta["scheme_code"] = pd.to_numeric(codes, errors="coerce").astype("Int64")
    if meta["scheme_code"].isna().all():
        raise ValueError("Could not resolve schemeCode from catalogue column or index.")
    meta["research_category"] = meta.apply(classify_category, axis=1)
    # Scheme codes, not display names, are the stable identity of NAV series.
    meta["scheme_name_duplicate"] = meta["schemeName"].astype(str).duplicated(keep=False)
    meta["scheme_identity"] = meta["scheme_code"].astype(str) + " | " + meta["schemeName"].astype(str)
    plan_opts = meta["schemeName"].map(plan_option)
    meta["plan"] = [x[0] for x in plan_opts]
    meta["option"] = [x[1] for x in plan_opts]
    meta["age_years"] = ((meta["latestDate"] - meta["oldestDate"]).dt.days / 365.25).round(2)
    latest = meta["latestDate"].max()
    meta["is_recent"] = meta["latestDate"].ge(latest - pd.Timedelta(days=120))
    # Keep all rows for audit; shortlist only mature, current, Direct Growth candidates.
    eligible = meta[
        meta["records"].ge(min_records)
        & meta["age_years"].ge(min_history_years)
        & meta["is_recent"]
        & meta["plan"].eq("Direct")
        & meta["option"].eq("Growth")
        & meta["scheme_code"].notna()
    ].copy()
    eligible = eligible.sort_values(
        ["research_category", "records", "latestDate"], ascending=[True, False, False]
    )
    shortlist = eligible.groupby("research_category", group_keys=False).head(per_category).copy()
    # Map shortlisted Direct Growth NAV series into optimiser-compatible rows.
    category_classes = {
        "Large Cap": "Indian equity", "Large & Mid Cap": "Indian equity",
        "Flexi/Multi Cap": "Indian equity", "Mid Cap": "Indian equity",
        "Small Cap": "Indian equity", "Focused": "Indian equity",
        "Sector/Thematic": "Indian equity", "Index/ETF": "Indian equity",
        "International": "Global equity", "ELSS/Tax Saver": "Tax-advantaged equity",
        "Debt/Gilt": "Fixed income", "Money Market/Ultra Short": "Fixed income",
        "Overnight/Liquid": "Cash/deposit", "Hybrid/Allocation": "Retirement / multi-asset",
        "Retirement/Solution": "Retirement / multi-asset",
    }
    shortlist["asset_class"] = shortlist["research_category"].map(category_classes).fillna("Indian equity")
    shortlist["asset"] = shortlist["scheme_identity"].astype(str).str.strip()
    shortlist["mu"] = 0.09
    shortlist["vol"] = 0.18
    shortlist["risk"] = shortlist["asset_class"].map({
        "Indian equity": 4, "Global equity": 4, "Tax-advantaged equity": 4,
        "Fixed income": 2, "Cash/deposit": 1, "Retirement / multi-asset": 3,
    }).fillna(3)
    shortlist["liquidity"] = 0.75
    shortlist["lockin"] = 0
    shortlist["evidence"] = "Observed Direct Growth NAV history; forward return/volatility are provisional category placeholders, not fund estimates"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    shortlist["asset_assumption_class"] = shortlist["asset_class"]
    shortlist[["asset", "asset_assumption_class", "mu", "vol", "risk", "liquidity", "lockin", "evidence"]].rename(
        columns={"asset_assumption_class": "class"}
    ).to_csv(Path(output_dir) / "mutual_fund_asset_assumptions.csv", index=False)
    shortlist["shortlist_reason"] = (
        f"Direct Growth; at least {min_records} NAV records and {min_history_years} years of history; recent latest NAV; "
        f"top {per_category} by record count within category"
    )
    return meta, shortlist


def export_selected_navs(shortlist: pd.DataFrame, root=None, outdir="data/mutual_fund_nav"):
    """Read selected schemes across partitions with predicate pushdown."""
    base = get_research_root(root)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    codes = sorted(shortlist["scheme_code"].dropna().astype(int).unique().tolist())
    collected = []
    for part in range(10):
        path = base / f"data/MF/nav_part_{part}.parquet"
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(
                path, columns=["date", "schemeCode", "nav"],
                filters=[("schemeCode", "in", codes)],
            )
        except (ValueError, TypeError):
            frame = pd.read_parquet(path, columns=["date", "schemeCode", "nav"])
            frame = frame[frame["schemeCode"].isin(codes)]
        if not frame.empty:
            collected.append(frame)
    if not collected:
        raise ValueError("No NAV observations found for selected schemes; verify schemeCode mapping.")
    nav = pd.concat(collected, ignore_index=True)
    nav["date"] = pd.to_datetime(nav["date"], errors="coerce")
    nav["nav"] = pd.to_numeric(nav["nav"], errors="coerce")
    nav = nav.dropna(subset=["date", "nav"])
    nav = nav[nav["nav"].gt(0)].drop_duplicates(["schemeCode", "date"]).sort_values(["date", "schemeCode"])
    nav.to_parquet(out / "selected_nav_long.parquet", index=False)
    names = shortlist.set_index(shortlist["scheme_code"].astype(int))["schemeName"].to_dict()
    nav["series_name"] = nav["schemeCode"].map(names)
    nav["series_name"] = nav["schemeCode"].astype(str) + " | " + nav["series_name"].astype(str)
    panel = nav.pivot(index="date", columns="series_name", values="nav").sort_index()
    panel.to_csv(out / "selected_nav_panel.csv")
    returns = panel.pct_change(fill_method=None)
    returns.to_csv(out / "selected_nav_returns.csv")
    return nav, panel, returns


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=None)
    p.add_argument("--output-dir", default="data")
    p.add_argument("--min-records", type=int, default=500)
    p.add_argument("--per-category", type=int, default=3)
    p.add_argument("--min-history-years", type=float, default=3)
    p.add_argument("--export-navs", action="store_true")
    args = p.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta, shortlist = build_shortlist(args.root, args.min_records, args.per_category, output_dir=out, min_history_years=args.min_history_years)
    meta.to_csv(out / "mutual_fund_catalog_audit.csv", index=False)
    shortlist.to_csv(out / "mutual_fund_shortlist.csv", index=False)
    print(f"Catalogue rows: {len(meta):,}")
    print(f"Shortlisted schemes: {len(shortlist):,}")
    print(shortlist[["scheme_code", "schemeName", "research_category", "records", "age_years"]].to_string(index=False))
    if args.export_navs:
        nav, panel, returns = export_selected_navs(shortlist, args.root, out / "mutual_fund_nav")
        print(f"Exported {len(nav):,} NAV rows across {panel.shape[1]} schemes.")


if __name__ == "__main__":
    main()
