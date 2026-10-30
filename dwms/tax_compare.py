"""Transparent simplified Indian salary-tax comparison for Tax Year 2026-27.
Not a return-filing engine: surcharge, marginal relief, special-rate income, exemptions and detailed deductions are excluded.
"""
NEW_SLABS=[(400000,0.00),(800000,0.05),(1200000,0.10),(1600000,0.15),(2000000,0.20),(2400000,0.25),(float("inf"),0.30)]
OLD_SLABS=[(250000,0.00),(500000,0.05),(1000000,0.20),(float("inf"),0.30)]
def _slab_tax(income, slabs):
    lo=0.0; tax=0.0
    for hi,rate in slabs:
        taxable=max(0,min(income,hi)-lo); tax+=taxable*rate; lo=hi
        if income<=hi: break
    return tax
def compare_regimes(annual_gross_salary, old_deductions=0, other_taxable_income=0):
    gross=max(0,float(annual_gross_salary)); other=max(0,float(other_taxable_income))
    # Standard deduction assumed at Rs 75,000 (new) and Rs 50,000 (old).
    new_income=max(0,gross-75000+other); old_income=max(0,gross-50000-max(0,float(old_deductions))+other)
    new_base=_slab_tax(new_income,NEW_SLABS); old_base=_slab_tax(old_income,OLD_SLABS)
    # Section 87A rebate assumption for resident individuals only; model cannot infer residency.
    new_rebate=min(new_base,60000) if new_income<=1200000 else 0
    old_rebate=min(old_base,12500) if old_income<=500000 else 0
    new_tax=max(0,new_base-new_rebate)*1.04; old_tax=max(0,old_base-old_rebate)*1.04
    better='New' if new_tax<=old_tax else 'Old'
    return {'tax_year':'Tax Year 2026-27','new':{'taxable_income':new_income,'tax_before_rebate':new_base,'rebate_assumed':new_rebate,'tax_including_cess':new_tax},'old':{'taxable_income':old_income,'tax_before_rebate':old_base,'rebate_assumed':old_rebate,'tax_including_cess':old_tax},'recommended':better,'difference':abs(new_tax-old_tax),'assumptions':['Salary-only simplified computation; no surcharge or marginal relief.','New regime standard deduction assumed Rs 75,000; old regime Rs 50,000.','New-regime rebate assumes resident individual eligibility; old-regime rebate assumes eligible resident individual.','Old deductions are a single user-entered aggregate; eligibility and limits are not validated.','Special-rate income, HRA exemptions, employer NPS, home-loan interest, capital gains and other exceptions are excluded.']}
