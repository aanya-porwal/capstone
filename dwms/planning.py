"""Household cash-flow and goal planning helpers."""
import math
def salary_path(monthly_income, annual_growth, years, growth_scenario='base'):
    factors={'conservative':0.5,'base':1.0,'optimistic':1.35}; g=max(-0.05,min(0.25,float(annual_growth)*factors[growth_scenario])); return [float(monthly_income)*(1+g)**y for y in range(int(years)+1)]
def future_monthly_surplus(income, expenses, income_growth, expense_growth, years, debt_payment=0):
    out=[]
    for y in range(int(years)+1):
        inc=float(income)*(1+float(income_growth))**y; exp=float(expenses)*(1+float(expense_growth))**y
        out.append({'year':y,'monthly_income':inc,'monthly_expenses':exp,'monthly_debt_payment':float(debt_payment),'monthly_surplus':max(0,inc-exp-float(debt_payment))})
    return out
def allocate_household_surplus(goals, monthly_surplus):
    """Allocate surplus pro-rata to requested goal contributions, capped at total surplus."""
    req=[max(0,float(g.get('monthly_contribution',0))) for g in goals]; total=sum(req); scale=min(1,float(monthly_surplus)/total) if total else 0
    result=[]
    for g,r in zip(goals,req): result.append({**g,'funded_monthly':r*scale,'funding_ratio':scale if r else 0})
    return result
def allocation_rationale(rows, horizon, risk_score):
    out=[]
    for r in rows:
        name=str(r.get('asset','')); cls=str(r.get('class','')); w=float(r.get('weight',0)); evidence=str(r.get('evidence',''))
        if 'equity' in cls.lower(): why='Long-horizon growth exposure; increases drawdown risk and should be reduced for near-term goals.'
        elif 'gold' in cls.lower() or name=='Gold ETF': why='Diversifier with different return drivers; can be volatile and produces no contractual income.'
        else: why='Stability / income / liquidity sleeve; reduces reliance on equity but carries rate, credit, reinvestment or inflation risk.'
        if evidence.lower().startswith('historical'): data='Estimated partly from observed return history; historical returns are not forecasts.'
        else: data='Expected return and/or risk uses a prior assumption, not a long verified investable history.'
        out.append({'asset':name,'weight':w,'role':why,'data_quality':data,'suitability':f'{horizon}-year horizon; risk input {risk_score}/100. Weight is an optimiser output under stated constraints, not a product recommendation.'})
    return out
