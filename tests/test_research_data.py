from pathlib import Path

import pandas as pd
import pytest

from engine.research_data import (
    get_research_root,
    build_coverage_report,
    load_asset_return_series,
    load_commodity,
    load_index,
    load_listed_security,
    load_macro,
    load_mutual_fund_nav,
    load_sgb,
    normalise_market_frame,
)


def test_root_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DWMS_RESEARCH_DATA_DIR", str(tmp_path))
    assert get_research_root() == tmp_path.resolve()


def test_normalise_market_frame_supports_date_index():
    frame = pd.DataFrame({"Close": [100, 101]}, index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    out = normalise_market_frame(frame)
    assert list(out["close"]) == [100, 101]
    assert out["Date"].is_monotonic_increasing


def test_normalise_market_frame_deduplicates_and_drops_invalid():
    frame = pd.DataFrame({"Date": ["2024-01-01", "2024-01-01", "bad"], "Close": [100, 101, 90]})
    out = normalise_market_frame(frame)
    assert len(out) == 1
    assert out.iloc[0]["close"] == 101


def test_loaders_fail_with_actionable_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="Clone"):
        load_index("NIFTY_50", tmp_path)


def test_reject_invalid_symbols():
    with pytest.raises(ValueError):
        load_index("../NIFTY_50")
    with pytest.raises(ValueError):
        load_listed_security("RELIANCE", "NYSE")


def test_return_loader_rejects_yield_and_spot_series():
    with pytest.raises(ValueError, match="Use index"):
        load_asset_return_series("gold:spot")



def test_asset_price_panel_preserves_non_overlapping_history():
    from dwms.quant import load_prices

    # Existing bundled data should remain available even if optional research
    # series have different inception dates.
    returns = load_prices()
    assert not returns.empty
    assert "Nifty 50 ETF" in returns.columns
    assert "Gold ETF" in returns.columns
    assert returns.index.is_monotonic_increasing



def test_coverage_report_reads_datetime_index_dates(tmp_path):
    path = tmp_path / "data" / "INDICES"
    path.mkdir(parents=True)
    pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date"),
    ).to_parquet(path / "NIFTY_50.parquet")

    report = build_coverage_report(tmp_path)
    row = report.loc[report["dataset"].eq("NIFTY_50")].iloc[0]

    assert row["status"] == "present"
    assert row["start_date"] == "2024-01-02"
    assert row["end_date"] == "2024-01-03"
