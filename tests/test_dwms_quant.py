import numpy as np, pandas as pd
from dwms.quant import optimise, estimate_moments, detect_regime, bootstrap_goal
from dwms.tax import equity_gain_tax, compare_80c, tax_aware_sell_lots

def test_optimizer_weights_and_risk():
    r=pd.DataFrame({'Nifty 50 ETF':np.random.default_rng(1).normal(.0004,.01,500),'Gold ETF':np.random.default_rng(2).normal(.0002,.008,500)})
    out=optimise(r,55,10,20000)
    assert np.isclose(out['allocation'].weight.sum(),1)
    assert out['volatility']>=0
    assert out['solver_success']

def test_covariance_positive_semidefinite():
    r=pd.DataFrame({'Nifty 50 ETF':np.random.default_rng(3).normal(0,.01,500),'Gold ETF':np.random.default_rng(4).normal(0,.01,500)})
    _,_,cov,_=estimate_moments(r)
    assert np.linalg.eigvalsh(cov).min()>-1e-8

def test_bootstrap_falls_back_when_portfolio_not_fully_observed():
    r=pd.DataFrame({'Nifty 50 ETF':np.random.default_rng(1).normal(0,.01,500),'Gold ETF':np.random.default_rng(2).normal(0,.01,500)})
    out=optimise(r,50,10,10000); sim=bootstrap_goal(100000,10000,10,2000000,out,r,100,1)
    assert sim['method']=='Gaussian proxy using prior moments'
    assert 0<=sim['goal_probability']<=1

def test_tax_rules_and_80c():
    assert equity_gain_tax(100000,18)['estimated_tax']==0
    assert equity_gain_tax(200000,18)['estimated_tax']>0
    assert compare_80c('new',0,100000)['eligible_additional']==0
    assert compare_80c('old',50000,100000)['eligible_additional']==100000

def test_tax_aware_lot_sale():
    lots=[{'name':'short','units':100,'price':100,'gain_per_unit':30,'holding_months':8},{'name':'long','units':100,'price':100,'gain_per_unit':10,'holding_months':24}]
    out=tax_aware_sell_lots(lots,5000)
    assert out['raised']>=5000
    assert out['estimated_tax']>=0

def test_conversational_onboarding_parser():
    from dwms.onboarding import parse_step
    p,ok,_=parse_step('income','My take-home pay is about ₹90,000 per month',{})
    assert ok and p['income']==90000
    p,ok,_=parse_step('goal','Home down payment ₹25 lakh in 7 years',p)
    assert ok and p['goal_amount']==2500000 and p['goal_years']==7

def test_tax_aware_rebalance_drift_band():
    from dwms.tax import tax_aware_rebalance
    result=tax_aware_rebalance({'Equity':80000,'Debt':20000},{'Equity':.6,'Debt':.4},drift_threshold=.05)
    assert len(result['trades'])==2
    assert result['estimated_tax'] is None  # no tax-lot data: must not imply zero tax


def test_optimizer_reports_risk_constraint_feasibility():
    rng = np.random.default_rng(101)
    returns = pd.DataFrame({
        'Nifty 50 ETF': rng.normal(.0005, .012, 500),
        'Gold ETF': rng.normal(.0002, .009, 500),
    })
    out = optimise(returns, risk_score=20, horizon=2, monthly_budget=10000)
    assert 'risk_cap_satisfied' in out
    assert out['risk_constraint_relaxed'] is (not out['risk_cap_satisfied'])
    assert out['solver_mode'] in {
        'requested_objective_with_risk_cap',
        'minimum_variance_fallback_without_risk_cap',
    }
    assert out['equity_cap_satisfied']
    assert out['tax_cap_satisfied']
    assert out['solver_success']
