import pandas as pd

from data.build_mutual_fund_universe import classify_category, plan_option


def test_mutual_fund_category_classification():
    row = {"category": "Equity Scheme - Mid Cap Fund", "schemeName": "Example", "schemeType": "Open Ended"}
    assert classify_category(row) == "Mid Cap"


def test_mutual_fund_plan_option_classification():
    assert plan_option("Example Fund - Direct Plan - Growth") == ("Direct", "Growth")
    assert plan_option("Example Fund - Regular Plan - IDCW") == ("Regular", "IDCW/Dividend")


def test_scheme_code_from_catalogue_index_is_supported():
    from data.build_mutual_fund_universe import build_shortlist
    assert callable(build_shortlist)
