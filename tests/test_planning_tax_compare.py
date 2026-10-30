from dwms.planning import salary_path, allocate_household_surplus
from dwms.tax_compare import compare_regimes

def test_salary_path_scenarios_ordered():
    c=salary_path(50000,.06,10,'conservative')[-1]
    b=salary_path(50000,.06,10,'base')[-1]
    o=salary_path(50000,.06,10,'optimistic')[-1]
    assert c < b < o

def test_goal_contributions_never_exceed_household_budget():
    goals=[{'name':'A','monthly_contribution':10000},{'name':'B','monthly_contribution':15000}]
    result=allocate_household_surplus(goals,20000)
    assert abs(sum(x['funded_monthly'] for x in result)-20000)<1e-8

def test_tax_comparison_returns_both_regimes_and_nonnegative_tax():
    r=compare_regimes(1800000,300000)
    assert r['recommended'] in ('New','Old')
    assert r['new']['tax_including_cess'] >= 0
    assert r['old']['tax_including_cess'] >= 0
