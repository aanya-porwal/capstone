"""Instrument-aware capital-gains estimates for Indian resident individuals.

Rule configuration reflects the broad post-23 July 2024 framework and
Income-tax Act, 2025 / Finance Act, 2026 changes for Tax Year 2026-27.
This is an educational estimate, not a return-filing calculation. It does
not calculate surcharge, marginal relief, loss set-off, TDS or treaty effects.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import pandas as pd


@dataclass(frozen=True)
class TaxRule:
    holding_period_months: int
    ltcg_rate: float | None
    stcg_rate: str
    ltcg_exemption_group: str | None = None
    indexation: bool = False


RULES = {
    "listed_equity": TaxRule(12, 0.125, "special_20", "112A"),
    "equity_mutual_fund": TaxRule(12, 0.125, "special_20", "112A"),
    "business_trust_unit": TaxRule(12, 0.125, "special_20", "112A"),
    "gold_etf": TaxRule(12, 0.125, "slab"),
    "silver_etf": TaxRule(12, 0.125, "slab"),
    "listed_gsec": TaxRule(12, 0.125, "slab"),
    "physical_gold": TaxRule(24, 0.125, "slab"),
    "physical_silver": TaxRule(24, 0.125, "slab"),
    "debt_mutual_fund_50aa": TaxRule(9999, None, "slab"),
    "other_mutual_fund": TaxRule(24, 0.125, "slab"),
    "unlisted_bond": TaxRule(9999, None, "slab"),
    "sgb_secondary_sale": TaxRule(12, 0.125, "slab"),
}

LTCG_112A_EXEMPTION = 125000
CESS_RATE = 0.04


def estimate_capital_gains(asset_type: str, gain: float, holding_months: int,
                           marginal_slab_rate: float = 0.30,
                           other_112a_ltcg: float = 0.0,
                           stt_eligible: bool = True,
                           sgb_original_subscriber: bool = False,
                           sgb_held_continuously_to_maturity: bool = False,
                           sgb_redemption_at_maturity: bool = False,
                           acquisition_date=None) -> dict:
    """Estimate tax on a positive realised gain for supported asset categories."""
    key = str(asset_type).lower().strip()
    if key not in RULES:
        raise ValueError(f"Unsupported asset_type. Choose from: {sorted(RULES)}")
    if gain < 0 or holding_months < 0:
        raise ValueError("gain and holding_months must be non-negative")
    if not 0 <= marginal_slab_rate <= 1:
        raise ValueError("marginal_slab_rate must be between zero and one")

    if key == "sgb_secondary_sale" and sgb_redemption_at_maturity and sgb_original_subscriber and sgb_held_continuously_to_maturity:
        return {"asset_type": key, "gain": float(gain), "classification": "exempt redemption",
                "tax_before_cess": 0.0, "cess": 0.0, "estimated_tax": 0.0,
                "rule_basis": "Income-tax Act, 2025 section 70(1)(x), as amended w.e.f. 1-Apr-2026",
                "warning": "Coupon interest is separate and remains taxable; retain original subscription and holding evidence."}

    rule = RULES[key]
    if key == "debt_mutual_fund_50aa":
        if acquisition_date is None:
            raise ValueError("acquisition_date is required to determine whether section 50AA applies")
        acquired = pd.Timestamp(acquisition_date).date()
        if acquired < date(2023, 4, 1):
            long_term = holding_months >= 24
            rule = TaxRule(24, 0.125, "slab")
        else:
            long_term = False
    else:
        long_term = holding_months >= rule.holding_period_months
    if key == "unlisted_bond":
        long_term = False
    if not long_term:
        rate = 0.20 if rule.stcg_rate == "special_20" else marginal_slab_rate
        basis = "special STCG rate" if rule.stcg_rate == "special_20" else "user-supplied marginal slab rate"
        taxable = float(gain)
    elif rule.ltcg_exemption_group == "112A":
        if not stt_eligible:
            rate = marginal_slab_rate
            basis = "slab estimate; section 112A STT conditions not confirmed"
            taxable = float(gain)
        else:
            rate = float(rule.ltcg_rate)
            taxable = max(0.0, float(gain) + max(0.0, other_112a_ltcg) - LTCG_112A_EXEMPTION)
            basis = "section 112A; aggregate annual exemption applied using supplied other gains"
    else:
        rate = float(rule.ltcg_rate) if rule.ltcg_rate is not None else marginal_slab_rate
        taxable = float(gain)
        basis = "general LTCG estimate without indexation" if rule.ltcg_rate is not None else "slab estimate"
    tax = taxable * rate
    cess = tax * CESS_RATE
    return {
        "asset_type": key, "gain": float(gain),
        "classification": "LTCG" if long_term else "STCG",
        "holding_period_months": int(holding_months), "taxable_gain": taxable,
        "applied_rate": rate, "tax_before_cess": tax, "cess": cess,
        "estimated_tax": tax + cess, "rule_basis": basis,
        "warning": "Excludes surcharge, marginal relief, loss set-off, exemptions, expenses, TDS and individual-specific rules. Verify tax year and instrument classification.",
    }


def sgb_coupon_tax(coupon_income: float, marginal_slab_rate: float = 0.30) -> dict:
    """SGB interest/coupon is modelled separately as income taxable at slab rate."""
    if coupon_income < 0 or not 0 <= marginal_slab_rate <= 1:
        raise ValueError("Invalid coupon income or slab rate")
    tax = coupon_income * marginal_slab_rate
    return {"coupon_income": float(coupon_income), "tax_before_cess": tax,
            "cess": tax * CESS_RATE, "estimated_tax": tax * (1 + CESS_RATE),
            "rule_basis": "Interest income; marginal slab estimate",
            "warning": "SGB coupon is separate from capital-gains treatment of redemption or transfer."}
