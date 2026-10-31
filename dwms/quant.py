"""Quantitative engine: historical statistics, factor priors, shrinkage, constrained optimisation and bootstrap."""
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
ASSETS = pd.read_csv(ROOT/'data/asset_assumptions.csv')
# Transparent prior correlations; empirical correlation is used only for observed pairs.
CORR_PRIOR={('Indian equity','Indian equity'):.82,('Indian equity','Global equity'):.65,('Indian equity','Gold'):.05,('Indian equity','Fixed income'):-.05,('Indian equity','Cash/deposit'):0,('Global equity','Gold'):.05,('Global equity','Fixed income'):-.05,('Gold','Fixed income'):.10,('Gold','Cash/deposit'):0,('Fixed income','Cash/deposit'):.55,('Tax-advantaged equity','Indian equity'):.95,('Tax-advantaged equity','Global equity'):.60,('Tax-advantaged equity','Gold'):.05,('Tax-advantaged equity','Fixed income'):-.05,('Tax-advantaged equity','Cash/deposit'):0,('Tax-advantaged fixed income','Indian equity'):-.05,('Tax-advantaged fixed income','Fixed income'):.85,('Tax-advantaged fixed income','Cash/deposit'):.55,('Retirement / multi-asset','Indian equity'):.55,('Retirement / multi-asset','Fixed income'):.55,('Retirement / multi-asset','Gold'):.15,('Retirement / multi-asset','Cash/deposit'):.25}

def load_prices():
    files={'Nifty 50 ETF':ROOT/'data/nifty50_historical.csv','Gold ETF':ROOT/'data/goldbees_historical.csv'}
    series={}
    for name,path in files.items():
        if path.exists():
            d=pd.read_csv(path); d['Date']=pd.to_datetime(d['Date']); d['close']=pd.to_numeric(d['close'],errors='coerce')
            s=d.dropna(subset=['Date','close']).drop_duplicates('Date').set_index('Date')['close'].sort_index()
            series[name]=s.pct_change(fill_method=None).dropna()
    extra=ROOT/'data/prices'
    if extra.exists():
        # Load raw price files first and distribution-adjusted proxies last so a
        # proxy with the same canonical asset name takes precedence deterministically.
        for path in sorted(extra.glob('*.csv'), key=lambda p: ('total_return_proxy' in p.stem, p.name)):
            try:
                d=pd.read_csv(path); datecol='Date' if 'Date' in d else 'date'; pricecol='Close' if 'Close' in d else ('close' if 'close' in d else 'NAV')
                d[datecol]=pd.to_datetime(d[datecol]); s=pd.to_numeric(d[pricecol],errors='coerce'); s.index=d[datecol]
                aliases={'nifty_50_etf':'Nifty 50 ETF','nifty_next_50_etf':'Nifty Next 50 ETF','nifty_midcap_etf':'Nifty Midcap ETF','gold_etf':'Gold ETF','liquid_fund_proxy':'Liquid Fund','gilt_etf_proxy':'Government Bond','s_p_500_etf_proxy':'International Equity','nifty_500_etf_proxy':'Nifty 500 ETF proxy','nifty_bank_etf_proxy':'Nifty Bank ETF proxy','bharat_bond_etf_proxy':'Bharat Bond ETF proxy','nifty_100_index_proxy':'Nifty 100 Index Proxy','nifty_200_index_proxy':'Nifty 200 Index Proxy','nifty_500_index_proxy':'Nifty 500 Index Proxy','nifty_bank_index_proxy':'Nifty Bank Index Proxy','nifty_it_index_proxy':'Nifty IT Index Proxy','nifty_pharma_index_proxy':'Nifty Pharma Index Proxy','nifty_midcap_50_index_proxy':'Nifty Midcap 50 Index Proxy','sensex_index_proxy':'Sensex Index Proxy','gold_bees_etf_price':'Gold BeES ETF Price','embassy_reit_price':'Embassy REIT Price','mindspace_reit_price':'Mindspace REIT Price','brookfield_reit_price':'Brookfield India REIT Price','nexus_select_trust_price':'Nexus Select Trust Price','indigrid_invit_price':'IndiGrid InvIT Price','irb_invit_price':'IRB InvIT Price','powergrid_invit_price':'PowerGrid InvIT Price','gold_bees_etf_price':'Gold BeES ETF Price','embassy_reit_price':'Embassy REIT Price','embassy_reit_price_total_return_proxy':'Embassy REIT Price','mindspace_reit_price':'Mindspace REIT Price','mindspace_reit_price_total_return_proxy':'Mindspace REIT Price','brookfield_reit_price':'Brookfield India REIT Price','brookfield_reit_price_total_return_proxy':'Brookfield India REIT Price','nexus_select_trust_price':'Nexus Select Trust Price','nexus_select_trust_price_total_return_proxy':'Nexus Select Trust Price','indigrid_invit_price':'IndiGrid InvIT Price','indigrid_invit_price_total_return_proxy':'IndiGrid InvIT Price','irb_invit_price':'IRB InvIT Price','irb_invit_price_total_return_proxy':'IRB InvIT Price','powergrid_invit_price':'PowerGrid InvIT Price','powergrid_invit_price_total_return_proxy':'PowerGrid InvIT Price'}
                series[aliases.get(path.stem,path.stem)]=s.sort_index().pct_change(fill_method=None).dropna()
            except Exception: pass
    # Selected Direct Growth mutual-fund NAVs are expense-net NAV total-return proxies.
    mf_panel = ROOT/'data/mutual_fund_nav'/'selected_nav_panel.csv'
    if mf_panel.exists():
        try:
            mf = pd.read_csv(mf_panel, index_col=0, parse_dates=True)
            mf = mf.apply(pd.to_numeric, errors='coerce').sort_index()
            mf_returns = mf.pct_change(fill_method=None)
            for name in mf_returns.columns:
                s = mf_returns[name].replace([np.inf,-np.inf],np.nan).dropna()
                if len(s) >= 60:
                    series[str(name)] = s
        except (ValueError, OSError, pd.errors.ParserError):
            pass
    return pd.concat(series,axis=1,join='outer',sort=False).sort_index() if series else pd.DataFrame()

def market_features(returns):
    if returns.empty: return pd.DataFrame()
    # Daily data, with rolling features. Gold used only as a secondary market feature.
    eq=returns['Nifty 50 ETF'] if 'Nifty 50 ETF' in returns else returns.iloc[:,0]
    f=pd.DataFrame(index=eq.index)
    f['vol_21']=eq.rolling(21).std()*np.sqrt(252)
    f['vol_63']=eq.rolling(63).std()*np.sqrt(252)
    f['mom_63']=(1+eq).rolling(63).apply(np.prod,raw=True)-1
    f['mom_252']=(1+eq).rolling(252).apply(np.prod,raw=True)-1
    f['drawdown']=(1+eq).cumprod()/(1+eq).cumprod().cummax()-1
    f['gold_mom_63']=(1+returns['Gold ETF']).rolling(63).apply(np.prod,raw=True)-1 if 'Gold ETF' in returns else 0
    return f.replace([np.inf,-np.inf],np.nan).dropna()

def detect_regime(returns):
    f=market_features(returns)
    if len(f)<100: return {'label':'Insufficient history','clusters':0,'features':f,'latest':None,'model':None,'scaler':None}
    scaler=StandardScaler(); X=scaler.fit_transform(f)
    model=KMeans(n_clusters=3,random_state=42,n_init=20); labels=model.fit_predict(X)
    tmp=f.copy(); tmp['cluster']=labels
    summary=tmp.groupby('cluster').agg(vol=('vol_63','mean'),mom=('mom_63','mean'),drawdown=('drawdown','mean'))
    # Cluster labels assigned by a transparent composite of momentum and volatility.
    score=summary['mom']-0.35*summary['vol']+0.15*summary['drawdown']
    order=score.sort_values().index.tolist(); names={order[0]:'Stress / defensive',order[1]:'Neutral / transition',order[2]:'Risk-on / momentum'}
    current=int(labels[-1]); return {'label':names[current],'clusters':3,'features':f,'latest':f.iloc[-1].to_dict(),'model':model,'scaler':scaler,'cluster_summary':summary.assign(label=[names[i] for i in summary.index])}

def estimate_moments(returns, assets=None):
    assets=(ASSETS.copy() if assets is None else assets.copy()).reset_index(drop=True)
    # Add only screened Direct Growth mutual funds; their expected-return and
    # volatility priors are replaced/blended with observed NAV history below.
    if assets is ASSETS or assets.equals(ASSETS):
        mf_assumptions = ROOT/'data/mutual_fund_asset_assumptions.csv'
        if mf_assumptions.exists():
            try:
                mf_assets = pd.read_csv(mf_assumptions)
                required = {'asset','class','mu','vol','risk','liquidity','lockin','evidence'}
                if required.issubset(mf_assets.columns):
                    assets = pd.concat([assets, mf_assets[list(ASSETS.columns)]], ignore_index=True)
                    assets = assets.drop_duplicates('asset', keep='first').reset_index(drop=True)
            except (ValueError, OSError, pd.errors.ParserError):
                pass
    names=assets.asset.tolist(); mu=assets.mu.to_numpy(float).copy(); vol=assets.vol.to_numpy(float).copy()
    # Observed daily statistics replace prior values only for assets with enough data.
    empirical={}
    if not returns.empty:
        for name in names:
            if name in returns and returns[name].count()>=100:
                s=returns[name].dropna(); years=len(s)/252
                cagr=float(np.prod(1+s)**(1/years)-1) if years>0 and (1+s).gt(0).all() else float(s.mean()*252)
                empirical[name]={'cagr':cagr,'vol':float(s.std()*np.sqrt(252)),'n':len(s)}
                idx=assets.index[assets.asset==name][0]; mu[idx]=np.clip(.45*cagr+.55*mu[idx],-.02,.18); vol[idx]=np.clip(.6*empirical[name]['vol']+.4*vol[idx],.005,.40)
    n=len(names); corr=np.eye(n)
    for i in range(n):
        for j in range(i):
            ci,cj=assets.iloc[i]['class'],assets.iloc[j]['class']; key=(ci,cj) if (ci,cj) in CORR_PRIOR else (cj,ci)
            corr[i,j]=corr[j,i]=CORR_PRIOR.get(key,.10 if ci!=cj else .65)
    # Use observed correlation where both series are available, then blend with prior.
    if not returns.empty:
        for i,a in enumerate(names):
            for j,b in enumerate(names[:i]):
                if a in returns and b in returns:
                    pair=returns[[a,b]].dropna()
                    if len(pair)>=100:
                        corr[i,j]=corr[j,i]=.65*pair.corr().iloc[0,1]+.35*corr[i,j]
    cov=np.outer(vol,vol)*corr
    # Ledoit-Wolf shrinkage on the empirically observed block; prior covariance remains for unobserved assets.
    observed=[name for name in names if name in returns.columns and returns[name].count()>=100] if not returns.empty else []
    if len(observed)>=2:
        block=returns[observed].dropna()
        if len(block)>=100:
            shrunk=LedoitWolf().fit(block.to_numpy()).covariance_*252
            for i,a in enumerate(observed):
                for j,b in enumerate(observed):
                    ai=names.index(a); bj=names.index(b)
                    cov[ai,bj]=shrunk[i,j]
    # PSD repair before optimiser; eigenvalue floor prevents numerical failures.
    eig,Q=np.linalg.eigh((cov+cov.T)/2); cov=Q@np.diag(np.maximum(eig,1e-7))@Q.T
    return assets,mu,cov,empirical

def optimise(returns, risk_score=50, horizon=10, monthly_budget=10000, objective='balanced_utility', age=30, tax_regime='New', existing_80c=0):
    assets,mu,cov,emp=estimate_moments(returns); n=len(assets)
    # Risk score 0..100 controls equity exposure and overall risk budget.
    equity_cap=float(np.interp(risk_score,[0,30,60,100],[.20,.40,.70,.90]))
    risk_cap=float(np.interp(risk_score,[0,30,60,100],[.07,.10,.15,.22]))
    if horizon<=3: equity_cap=min(equity_cap,.20); risk_cap=min(risk_cap,.07)
    elif horizon<=5: equity_cap=min(equity_cap,.40); risk_cap=min(risk_cap,.10)
    bounds=[]
    asset_names=assets['asset'].astype(str).str.lower()
    # A mutual-fund scheme is a vehicle, not a separate source of diversification.
    # Cap each selected fund and constrain concentrated equity styles in aggregate.
    mf_mask=asset_names.str.contains(r'\b(direct plan|growth option|growth)\b',regex=True).to_numpy()
    smallcap_idx=asset_names.str.contains(r'small\s*cap|smallcap',regex=True).to_numpy()
    midcap_idx=asset_names.str.contains(r'mid\s*cap|midcap',regex=True).to_numpy()
    sector_idx=asset_names.str.contains(r'sector|thematic|pharma|banking|technology|infrastructure',regex=True).to_numpy()
    largecap_idx=asset_names.str.contains(r'large\s*cap|largecap',regex=True).to_numpy()
    for i,(_,a) in enumerate(assets.iterrows()):
        cap=.35 if 'equity' in a['class'].lower() else (.30 if a['asset']!='Gold ETF' else .20)
        if mf_mask[i]: cap=min(cap,.15)
        if a['asset']=='Fixed Deposit': cap=.50
        if a['asset']=='Liquid Fund': cap=.35
        if a['asset']=='International Equity': cap=.20
        if a['asset']=='ELSS': cap=.20
        if a['asset']=='PPF' and horizon<15: cap=0.0
        if a['asset']=='NPS Tier I' and age+horizon<60: cap=0.0
        bounds.append((0,cap))
    eq_idx=np.array(['equity' in x.lower() for x in assets['class']]); gold_idx=np.array(assets['class']=='Gold')
    tax_idx=np.array(assets['asset'].isin(['ELSS','PPF']))
    style_constraints=[
        {'type':'ineq','fun':lambda w: .15-w[smallcap_idx].sum()},
        {'type':'ineq','fun':lambda w: .20-w[midcap_idx].sum()},
        {'type':'ineq','fun':lambda w: .10-w[sector_idx].sum()},
    ]
    tax_headroom=max(0,150000-float(existing_80c)) if tax_regime=='Old' else 0.0
    tax_monthly_cap=min(1.0,tax_headroom/max(monthly_budget*12,1)) if tax_regime=='Old' else 0.0
    def stats(w): return float(w@mu),float(np.sqrt(max(w@cov@w,0)))
    def obj(w):
        ret,risk=stats(w)
        if objective=='min_variance': return risk**2
        if objective=='risk_parity':
            mrc=cov@w/max(risk,1e-9); rc=w*mrc
            return float(np.sum((rc-rc.mean())**2))
        # robust return-risk utility with downside-risk proxy
        return -(ret-.55*risk**2)
    cons=[{'type':'eq','fun':lambda w:w.sum()-1},{'type':'ineq','fun':lambda w:equity_cap-w[eq_idx].sum()},{'type':'ineq','fun':lambda w:risk_cap-stats(w)[1]}]+style_constraints
    if tax_regime=='Old': cons.append({'type':'ineq','fun':lambda w:tax_monthly_cap-w[tax_idx].sum()})
    x0=np.ones(n)/n
    res=minimize(obj,x0,method='SLSQP',bounds=bounds,constraints=cons,options={'maxiter':1200,'ftol':1e-10})
    solver_mode='requested_objective_with_risk_cap'
    fallback_used=False
    if not res.success:
        # The requested risk cap may be infeasible under the asset priors and bounds.
        # Re-solve a minimum-variance problem without that cap, then report the breach.
        fallback_used=True
        solver_mode='minimum_variance_fallback_without_risk_cap'
        fallback_cons=[{'type':'eq','fun':lambda w:w.sum()-1},
                       {'type':'ineq','fun':lambda w:equity_cap-w[eq_idx].sum()}]+style_constraints
        if tax_regime=='Old':
            fallback_cons.append({'type':'ineq','fun':lambda w:tax_monthly_cap-w[tax_idx].sum()})
        res=minimize(lambda w: w@cov@w,x0,method='SLSQP',bounds=bounds,
                     constraints=fallback_cons,options={'maxiter':1200,'ftol':1e-10})
    if not res.success: raise RuntimeError('Portfolio optimisation failed: '+res.message)
    w=np.maximum(res.x,0); w=w/w.sum(); ret,risk=stats(w)
    equity_weight=float(w[eq_idx].sum())
    tax_weight=float(w[tax_idx].sum())
    tolerance=1e-6
    risk_cap_satisfied=bool(risk<=risk_cap+tolerance)
    equity_cap_satisfied=bool(equity_weight<=equity_cap+tolerance)
    tax_cap_satisfied=bool(tax_regime!='Old' or tax_weight<=tax_monthly_cap+tolerance)
    contributions=w*(cov@w)/max(risk,1e-12)
    result=assets[['asset','class','evidence']].copy(); result['weight']=w; result['monthly_amount']=w*monthly_budget; result['risk_contribution']=contributions
    # Keep every positive portfolio position in the returned allocation. Filtering
    # small weights here makes the reported weights sum to less than one and causes
    # downstream goal plans to understate invested capital.
    result=result[result.weight>1e-10].sort_values('weight',ascending=False)
    return {'allocation':result,'expected_return':ret,'volatility':risk,
            'equity_weight':equity_weight,'tax_weight':tax_weight,
            'risk_cap':risk_cap,'risk_cap_satisfied':risk_cap_satisfied,
            'risk_constraint_relaxed':bool(not risk_cap_satisfied),
            'equity_cap':equity_cap,'equity_cap_satisfied':equity_cap_satisfied,
            'tax_regime':tax_regime,'tax_deduction_monthly_cap':tax_monthly_cap,
            'tax_cap_satisfied':tax_cap_satisfied,
            'solver_mode':solver_mode,'fallback_used':fallback_used,
            'constraint_tolerance':tolerance,
            'moments':{'mu':mu,'cov':cov,'assets':assets},'empirical':emp,
            'solver_success':bool(res.success),'objective':objective}

def bootstrap_goal(current, monthly, years, target, allocation, returns, simulations=5000, seed=42):
    months=max(1,int(years*12)); rng=np.random.default_rng(seed)
    assets,mu,cov=allocation['moments']; w=allocation['allocation'].set_index('asset')['weight']
    # Use actual joint historical observations when available, otherwise a documented factor-prior Gaussian proxy.
    materially_held=[x for x,v in w.items() if v>=.02]
    hist_cols=[x for x in materially_held if x in returns.columns]
    # Bootstrap only when every material portfolio holding has aligned observations.
    if len(hist_cols)>=2 and len(returns)>=80 and set(materially_held).issubset(set(hist_cols)):
        aligned=returns[hist_cols].dropna().to_numpy(); weights=np.array([w.get(x,0) for x in hist_cols]); weights=weights/weights.sum()
        port=aligned@weights; block=21; paths=np.empty((simulations,months))
        for s in range(simulations):
            vals=[]
            while len(vals)<months:
                start=rng.integers(0,max(1,len(port)-block+1)); vals.extend(port[start:start+block])
            paths[s]=np.asarray(vals[:months])
    else:
        m=allocation['expected_return']/12; v=allocation['volatility']/np.sqrt(12)
        paths=rng.normal(m,v,(simulations,months)); paths=np.maximum(paths,-.95)
    wealth=np.full(simulations,float(current))
    for m in range(months): wealth=wealth*(1+paths[:,m])+monthly
    return {'goal_probability':float(np.mean(wealth>=target)),'p10':float(np.percentile(wealth,10)),'median':float(np.percentile(wealth,50)),'p90':float(np.percentile(wealth,90)),'mean':float(wealth.mean()),'simulations':simulations,'method':'21-day moving-block bootstrap' if len(hist_cols)>=2 and len(returns)>=80 and set([x for x,v in w.items() if v>=.02]).issubset(set(hist_cols)) else 'Gaussian proxy using prior moments','final_values':wealth}
