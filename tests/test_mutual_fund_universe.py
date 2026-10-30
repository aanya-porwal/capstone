import pandas as pd

from data import build_mutual_fund_universe as mf


def _catalogue():
    return pd.DataFrame(
        {
            "schemeCode": [101, 202],
            "schemeName": [
                "Example Large Cap Fund - Direct Plan - Growth",
                "Example Large Cap Fund - Direct Plan - Growth",
            ],
            "category": ["Equity Scheme - Large Cap Fund"] * 2,
            "schemeType": ["Open Ended"] * 2,
            "records": [1200, 900],
            "oldestDate": ["2020-01-01", "2021-01-01"],
            "latestDate": ["2026-10-29", "2026-10-29"],
        }
    )


def test_shortlist_uses_requested_output_directory_and_stable_scheme_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(mf, "load_mutual_fund_catalog", lambda root=None: _catalogue())

    meta, shortlist = mf.build_shortlist(output_dir=tmp_path)

    assert len(shortlist) == 2
    assert shortlist["scheme_identity"].nunique() == 2
    assert shortlist["scheme_name_duplicate"].all()
    assert shortlist["asset"].nunique() == 2
    assert (tmp_path / "mutual_fund_asset_assumptions.csv").exists()
    assert "provisional category placeholders" in shortlist.iloc[0]["evidence"]


def test_export_nav_panel_keeps_same_named_schemes_separate(monkeypatch, tmp_path):
    root = tmp_path / "research"
    (root / "data" / "MF").mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-01"]),
            "schemeCode": [101, 202],
            "nav": [10.0, 20.0],
        }
    )
    monkeypatch.setattr(mf, "get_research_root", lambda value=None: root)
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: frame.copy())

    shortlist = pd.DataFrame(
        {
            "scheme_code": [101, 202],
            "schemeName": ["Same Fund", "Same Fund"],
        }
    )
    nav, panel, returns = mf.export_selected_navs(shortlist, root=root, outdir=tmp_path / "out")

    assert panel.shape[1] == 2
    assert set(panel.columns) == {"101 | Same Fund", "202 | Same Fund"}
    assert set(nav["schemeCode"]) == {101, 202}
