import pytest
from dwms.capital_gains import estimate_capital_gains, sgb_coupon_tax


def test_equity_112a_exemption_and_rate():
    out = estimate_capital_gains("listed_equity", 200000, 13, other_112a_ltcg=0)
    assert out["taxable_gain"] == 75000
    assert out["estimated_tax"] == pytest.approx(75000 * 0.125 * 1.04)


def test_gold_etf_long_term_and_short_term():
    short = estimate_capital_gains("gold_etf", 10000, 8, marginal_slab_rate=0.30)
    long = estimate_capital_gains("gold_etf", 10000, 13, marginal_slab_rate=0.30)
    assert short["classification"] == "STCG"
    assert short["applied_rate"] == 0.30
    assert long["classification"] == "LTCG"
    assert long["applied_rate"] == 0.125


def test_sgb_maturity_exemption_requires_all_conditions():
    exempt = estimate_capital_gains("sgb_secondary_sale", 100000, 96,
        sgb_original_subscriber=True, sgb_held_continuously_to_maturity=True,
        sgb_redemption_at_maturity=True)
    taxable = estimate_capital_gains("sgb_secondary_sale", 100000, 96,
        sgb_original_subscriber=False, sgb_held_continuously_to_maturity=True,
        sgb_redemption_at_maturity=True)
    assert exempt["estimated_tax"] == 0
    assert taxable["estimated_tax"] > 0


def test_sgb_coupon_separate_from_capital_gain():
    out = sgb_coupon_tax(1000, 0.30)
    assert out["estimated_tax"] == pytest.approx(312)


def test_section_50aa_depends_on_acquisition_date():
    with pytest.raises(ValueError):
        estimate_capital_gains("debt_mutual_fund_50aa", 10000, 36)
    post = estimate_capital_gains("debt_mutual_fund_50aa", 10000, 36, acquisition_date="2024-01-01")
    pre = estimate_capital_gains("debt_mutual_fund_50aa", 10000, 36, acquisition_date="2022-01-01")
    assert post["classification"] == "STCG"
    assert pre["classification"] == "LTCG"
    assert pre["applied_rate"] == 0.125
