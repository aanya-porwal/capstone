from pathlib import Path
import sys, json, math
import numpy as np, pandas as pd
import streamlit as st
import plotly.express as px
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from dwms.database import init_db,register,authenticate,save_profile,load_profile,save_recommendation,load_latest_recommendation,save_chat,load_chat
from dwms.quant import load_prices,detect_regime,optimise,bootstrap_goal,ASSETS,estimate_moments
from dwms.tax import equity_gain_tax,tax_aware_sell_lots,compare_80c,RULES
from dwms.assistant import reply,ollama_available
from dwms.onboarding import STEPS,parse_step
from dwms.tax_compare import compare_regimes
from dwms.planning import salary_path, future_monthly_surplus, allocate_household_surplus, allocation_rationale
from engine.advanced_risk import historical_cvar, portfolio_return_series, regime_switching_monte_carlo, walk_forward_backtest
from engine.research_data import load_sgb, load_macro
from engine.sgb import sgb_instrument_table
from engine.fixed_income import yield_curve_scenarios
from dwms.capital_gains import estimate_capital_gains, sgb_coupon_tax

st.set_page_config(page_title='DWMS | Personal Wealth Intelligence',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
init_db()
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif} h1,h2,h3{font-family:'Manrope',sans-serif;letter-spacing:-.03em}
.block-container{padding-top:1.5rem;max-width:1440px}.stMetric{background:#18263a!important;padding:15px;border-radius:12px;border:1px solid #34445b!important}.stMetric label,.stMetric [data-testid='stMetricLabel'],.stMetric [data-testid='stMetricValue']{color:#f4f7fb!important}.stMetric [data-testid='stMetricDelta']{color:#c8d7e8!important}
[data-testid="stSidebar"]{background:#101a2b} [data-testid="stSidebar"] *{color:#eef3fb!important}
div[data-testid="stChatMessage"]{border:1px solid #e8edf3;border-radius:12px;padding:10px}
.small-muted{color:#778397;font-size:12px}.hero{background:linear-gradient(115deg,#13253f,#24466a);color:white;padding:25px 28px;border-radius:18px;margin-bottom:20px}
.hero h1{color:white;margin:0}.hero p{color:#d4e2f1;margin:6px 0 0}
</style>''',unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state.user=None
if 'page' not in st.session_state: st.session_state.page='Overview'

def login_screen():
    a,b=st.columns([1.15,1])
    with a:
        st.markdown("<div class='hero'><h1>Wealth management, made personal.</h1><p>Goal-led financial intelligence for India's next generation of investors.</p></div>",unsafe_allow_html=True)
        st.subheader('A more considered way to invest')
        st.write('DWMS connects your goals, financial capacity, risk profile, market context and tax position into one explainable planning experience.')
        st.caption('Local prototype • Your profile is stored in a SQLite database on this device.')
    with b:
        st.subheader('Welcome to DWMS')
        mode=st.radio('Account', ['Sign in','Create account'],horizontal=True)
        email=st.text_input('Email address'); password=st.text_input('Password',type='password')
        if mode=='Create account': st.caption('Use a password with at least 10 characters.')
        if st.button('Continue',type='primary',use_container_width=True):
            try:
                if mode=='Create account': uid=register(email,password); user={'id':uid,'email':email.lower()}
                else: user=authenticate(email,password)
                if not user: st.error('Email or password is incorrect.')
                else: st.session_state.user=user; st.rerun()
            except ValueError as e: st.error(str(e))

if not st.session_state.user:
    login_screen(); st.stop()
user=st.session_state.user; uid=user['id']; email=user['email']
profile=load_profile(uid) or {}
prices=load_prices(); regime=detect_regime(prices)

with st.sidebar:
    st.markdown('## ◈ DWMS')
    st.caption('PERSONAL WEALTH INTELLIGENCE')
    st.divider()
    pages=['Overview','Wealth conversation','My financial profile','Portfolio strategy','Goals & simulations','Risk lab','Tax intelligence','Market intelligence','Learn']
    page=st.radio('WORKSPACE',pages,index=pages.index(st.session_state.page) if st.session_state.page in pages else 0,label_visibility='collapsed')
    st.session_state.page=page
    st.divider(); st.caption('SIGNED IN AS'); st.write(email)
    st.caption('Local account • SQLite')
    if st.button('Sign out',use_container_width=True): st.session_state.user=None; st.rerun()

# Profile and recommendation computation
analysis=load_latest_recommendation(uid)
def make_analysis(p):
    risk=int(p.get('risk_score',50)); horizon=int(p.get('goal_years',10)); monthly=float(p.get('monthly_investment',0))
    opt=optimise(prices,risk_score=risk,horizon=horizon,monthly_budget=monthly,age=int(p.get('age',30)),tax_regime=p.get('tax_regime','New'),existing_80c=float(p.get('existing_80c',0)))
    goal=float(p.get('goal_amount',0)); current=float(p.get('current_savings',0)); inflation=float(p.get('goal_inflation',.06))
    future_goal=goal*((1+inflation)**horizon)
    sim=bootstrap_goal(current,monthly,horizon,future_goal,opt,prices,simulations=5000)
    return {'expected_return':opt['expected_return'],'volatility':opt['volatility'],'future_goal':future_goal,'goal_inflation':inflation,'equity_weight':opt['equity_weight'],'allocation':opt['allocation'].to_dict('records'),'goal_simulation':{k:v for k,v in sim.items() if k!='final_values'},'regime':regime['label'],'evidence':{r['asset']:r['evidence'] for _,r in ASSETS.iterrows()},'diagnostics':{'equity_cap':opt['equity_cap'],'risk_cap':opt['risk_cap'],'solver_success':opt['solver_success']}}
if all(k in profile for k in ['monthly_investment','risk_score','goal_years','goal_amount']):
    try:
        analysis=make_analysis(profile); save_recommendation(uid,analysis)
    except Exception as e: st.warning(f'Portfolio engine needs profile review: {e}')

if page=='Overview':
    st.markdown(f'<div class="hero"><h1>Good to see you.</h1><p>Your financial picture, goals and investment strategy in one place.</p></div>',unsafe_allow_html=True)
    if not profile:
        st.info('Start by building your financial profile. You can do this conversationally or enter the essentials in My financial profile.')
        if st.button('Build my financial profile',type='primary'): st.session_state.page='My financial profile'; st.rerun()
    else:
        a=analysis or {}
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Monthly investable amount',f"₹{profile.get('monthly_investment',0):,.0f}")
        c2.metric('Risk score',f"{profile.get('risk_score',0)}/100")
        c3.metric('Modelled return',f"{a.get('expected_return',0):.1%}")
        c4.metric('Modelled volatility',f"{a.get('volatility',0):.1%}")
        st.subheader('Your financial outlook')
        l,r=st.columns([1.25,1])
        with l:
            st.markdown('#### Goal trajectory')
            g=a.get('goal_simulation',{})
            st.metric('Simulated goal attainment',f"{g.get('goal_probability',0):.1%}",help='Scenario probability from historical block bootstrap where data permits, otherwise Gaussian proxy assumptions.')
            st.write(f"**Today's target:** ₹{profile.get('goal_amount',0):,.0f} · **Inflation-adjusted target:** ₹{a.get('future_goal',profile.get('goal_amount',0)):,.0f} · **Horizon:** {profile.get('goal_years',0)} years")
            st.write(f"**Median simulated corpus:** ₹{g.get('median',0):,.0f}")
            st.caption('Not a guaranteed forecast. Results depend on return, volatility, inflation and contribution assumptions.')
        with r:
            st.markdown('#### Current market regime')
            st.subheader(regime['label'])
            st.caption('Experimental K-Means classification based on rolling equity momentum, volatility and drawdown.')
            st.metric('Equity allocation',f"{a.get('equity_weight',0):.1%}")
        st.subheader('Your proposed allocation')
        alloc=pd.DataFrame(a.get('allocation',[]))
        if not alloc.empty:
            col1,col2=st.columns([1,1.2])
            with col1: st.plotly_chart(px.pie(alloc,names='asset',values='weight',hole=.55),use_container_width=True)
            with col2: st.dataframe(alloc[['asset','weight','monthly_amount','evidence']].style.format({'weight':'{:.1%}','monthly_amount':'₹{:,.0f}'}),hide_index=True,use_container_width=True)
    st.caption('Prototype notice: no brokerage connectivity, trade execution or regulated investment advice. Assumptions and proxy data are disclosed in Market intelligence.')

elif page=='My financial profile':
    st.title('Your financial profile'); st.write('Your financial plan should reflect your life, not just your age or salary.')
    with st.form('profile'):
        c1,c2,c3=st.columns(3)
        age=c1.number_input('Age',18,100,int(profile.get('age',28)))
        income=c2.number_input('Monthly take-home income (₹)',0,100000000,int(profile.get('income',90000)),step=5000)
        expenses=c3.number_input('Monthly essential + lifestyle expenses (₹)',0,100000000,int(profile.get('expenses',45000)),step=5000)
        c1,c2,c3=st.columns(3)
        debt=c1.number_input('Outstanding debt (₹)',0,100000000,int(profile.get('debt',0)),step=10000)
        savings=c2.number_input('Current financial investments (₹)',0,1000000000,int(profile.get('current_savings',300000)),step=10000)
        monthly=c3.number_input('Monthly investment capacity (₹)',0,10000000,int(profile.get('monthly_investment',20000)),step=1000)
        st.markdown('#### Career and income trajectory')
        c1,c2,c3=st.columns(3)
        profession=c1.selectbox('Employment / income type',['Salaried - private sector','Salaried - government','Self-employed / business','Freelancer / gig','Professional practice','Student / not currently earning','Retired'],index=['Salaried - private sector','Salaried - government','Self-employed / business','Freelancer / gig','Professional practice','Student / not currently earning','Retired'].index(profile.get('profession','Salaried - private sector')) if profile.get('profession') in ['Salaried - private sector','Salaried - government','Self-employed / business','Freelancer / gig','Professional practice','Student / not currently earning','Retired'] else 0)
        industry=c2.text_input('Industry / sector',profile.get('industry',''))
        experience=c3.number_input('Years of work experience',0,60,int(profile.get('experience',0)))
        c1,c2,c3=st.columns(3)
        income_growth=c1.slider('Expected annual income growth (%)',-5,25,int(profile.get('income_growth',6)),help='Use a conservative estimate, not your best-case promotion path.')/100
        expense_growth=c2.slider('Expected annual expense growth (%)',0,15,int(profile.get('expense_growth',5)))/100
        debt_payment=c3.number_input('Monthly EMI / debt payments (₹)',0,10000000,int(profile.get('debt_payment',0)),step=1000)
        st.caption('The model projects income and expenses as scenarios. It does not assume that salary growth is guaranteed; variable or business income should use a lower growth assumption and larger cash reserve.')
        st.markdown('#### Goals')
        c1,c2,c3=st.columns(3)
        goal_name=c1.selectbox('Primary goal',['Home purchase','Retirement','Education','Financial independence','Wealth creation','Other'],index=0)
        target=c2.number_input("Target amount in today's rupees (₹)",10000,1000000000,int(profile.get('goal_amount',2500000)),step=50000)
        years=c3.number_input('Years to goal',1,50,int(profile.get('goal_years',7)))
        st.caption('This legacy primary goal remains the default portfolio illustration. Add separate goals in Goals & simulations; each goal receives its own horizon, target and contribution budget, while all contributions share one household surplus.')
        st.markdown('#### Your relationship with risk')
        tolerance=st.slider('How would you react to a temporary 20% fall in your portfolio?',0,100,int(profile.get('risk_tolerance',50)),help='0 = would sell / cannot tolerate; 100 = can stay invested and tolerate volatility.')
        capacity=st.slider('How much financial loss could your circumstances absorb without disrupting essential goals?',0,100,int(profile.get('risk_capacity',50)),help='Consider income stability, emergency reserves, dependants, debt and near-term liabilities.')
        dependants=st.number_input('Financial dependants',0,15,int(profile.get('dependants',0)))
        regime_choice=st.selectbox('Income-tax regime', ['New','Old'],index=0 if profile.get('tax_regime','New')=='New' else 1)
        existing_80c=st.number_input('Existing eligible 80C contributions (₹)',0,1500000,int(profile.get('existing_80c',0)),step=5000)
        goal_inflation=st.slider('Assumed annual inflation for this goal',0.0,0.12,float(profile.get('goal_inflation',.06)),.005)
        submitted=st.form_submit_button('Save profile and calculate strategy',type='primary',use_container_width=True)
    if submitted:
        if monthly>max(0,income-expenses): st.error('Monthly investment capacity exceeds the surplus after expenses. Review the inputs.')
        else:
            # Risk capacity is independently adjusted for debt burden, liquidity and horizon.
            surplus=max(0,income-expenses); emergency_months=savings/max(expenses,1)
            capacity_adj=np.clip(capacity - min(25,debt/max(income*12,1)*20) + min(15,max(0,emergency_months-3)*2),0,100)
            score=int(round(.45*tolerance+.55*capacity_adj))
            p={'age':age,'income':income,'expenses':expenses,'debt':debt,'current_savings':savings,'monthly_investment':monthly,'goal_name':goal_name,'goal_amount':target,'goal_years':years,'risk_tolerance':tolerance,'risk_capacity':int(capacity_adj),'risk_score':score,'dependants':dependants,'tax_regime':regime_choice,'existing_80c':existing_80c,'goal_inflation':goal_inflation,'profession':profession,'industry':industry,'experience':experience,'income_growth':income_growth,'expense_growth':expense_growth,'debt_payment':debt_payment,'goals':profile.get('goals',[{'name':goal_name,'target_today':target,'years':years,'monthly_contribution':monthly,'current_corpus':savings,'inflation':goal_inflation}])}
            save_profile(uid,p); st.success(f'Profile saved. Combined risk score: {score}/100.'); st.rerun()
    if profile:
        st.info(f"Saved profile: {profile.get('goal_name')} · risk tolerance {profile.get('risk_tolerance')}/100 · risk capacity {profile.get('risk_capacity')}/100. These are separate dimensions, not a psychometric diagnosis. Career: {profile.get('profession','not supplied')} · income growth assumption: {profile.get('income_growth',0):.1%}/year.")

elif page=='Portfolio strategy':
    st.title('Portfolio strategy'); st.write('Constrained allocation built from historical evidence plus explicit priors.')
    if not profile: st.warning('Complete your financial profile first.')
    else:
        objective=st.selectbox('Optimisation objective',['balanced_utility','min_variance','risk_parity'],format_func=lambda x:{'balanced_utility':'Balanced return-risk utility','min_variance':'Minimum variance','risk_parity':'Risk parity'}[x])
        opt=optimise(prices,int(profile['risk_score']),int(profile['goal_years']),float(profile['monthly_investment']),objective,age=int(profile['age']),tax_regime=profile.get('tax_regime','New'),existing_80c=float(profile.get('existing_80c',0)))
        df=opt['allocation']; st.metric('Expected annual return (assumption blend)',f"{opt['expected_return']:.2%}"); st.metric('Annualised volatility estimate',f"{opt['volatility']:.2%}")
        st.plotly_chart(px.bar(df,x='asset',y='weight',color='class',hover_data=['evidence']),use_container_width=True)
        st.dataframe(df.style.format({'weight':'{:.1%}','monthly_amount':'₹{:,.0f}','risk_contribution':'{:.2%}'}),hide_index=True,use_container_width=True)
        st.markdown('#### Why these weights?')
        rationale=pd.DataFrame(allocation_rationale(df.to_dict('records'),int(profile['goal_years']),int(profile['risk_score'])))
        st.dataframe(rationale[['asset','weight','role','data_quality','suitability']].style.format({'weight':'{:.1%}'}),hide_index=True,use_container_width=True)
        st.caption('Weights are the result of the selected objective, expected-return priors, covariance estimates, asset caps and risk/equity constraints. The optimiser does not establish that the expected returns are achievable or that a specific fund/ETF is suitable.')
        st.markdown('#### Model diagnostics'); st.json({'equity_weight':opt['equity_weight'],'equity_cap':opt['equity_cap'],'risk_cap':opt['risk_cap'],'solver_success':opt['solver_success'],'empirical_statistics':opt['empirical']})
        st.warning('Several assets use prior expected returns, volatility and correlation assumptions. The covariance matrix is positive-semidefinite repaired. This is a prototype optimiser, not a verified investable portfolio.')

elif page=='Goals & simulations':
    st.title('Household goals & scenario analysis')
    st.write('Each goal has its own target, time horizon and notional portfolio. Contributions are constrained by one shared household surplus so the same rupee is not allocated twice.')
    if not profile: st.info('Complete your financial profile first.')
    else:
        goals=list(profile.get('goals') or [{'name':profile.get('goal_name','Primary goal'),'target_today':profile.get('goal_amount',0),'years':profile.get('goal_years',10),'monthly_contribution':profile.get('monthly_investment',0),'current_corpus':profile.get('current_savings',0),'inflation':profile.get('goal_inflation',.06)}])
        with st.form('add_goal'):
            st.markdown('#### Add a goal')
            c1,c2,c3=st.columns(3); gn=c1.text_input('Goal name'); gt=c2.number_input("Target in today's rupees (₹)",10000,1000000000,1000000,step=50000); gy=c3.number_input('Years until goal',1,50,10)
            c1,c2,c3=st.columns(3); gc=c1.number_input('Monthly contribution requested (₹)',0,10000000,5000,step=1000); corpus=c2.number_input('Existing corpus for this goal (₹)',0,1000000000,0,step=10000); infl=c3.slider('Goal inflation (%)',0,12,6)/100
            add=st.form_submit_button('Add goal')
        if add and gn.strip():
            goals.append({'name':gn.strip(),'target_today':gt,'years':gy,'monthly_contribution':gc,'current_corpus':corpus,'inflation':infl}); profile['goals']=goals; save_profile(uid,profile); st.rerun()
        st.markdown('#### Shared household cash flow')
        c1,c2,c3=st.columns(3); c1.metric('Current monthly surplus',f"₹{max(0,profile.get('income',0)-profile.get('expenses',0)-profile.get('debt_payment',0)):,.0f}"); c2.metric('Requested goal contributions',f"₹{sum(float(g.get('monthly_contribution',0)) for g in goals):,.0f}"); c3.metric('Current monthly investment budget',f"₹{profile.get('monthly_investment',0):,.0f}")
        surplus=max(0,profile.get('income',0)-profile.get('expenses',0)-profile.get('debt_payment',0)); funded=allocate_household_surplus(goals,min(surplus,profile.get('monthly_investment',surplus)))
        st.dataframe(pd.DataFrame(funded)[['name','target_today','years','monthly_contribution','funded_monthly','funding_ratio','current_corpus']].style.format({'target_today':'₹{:,.0f}','monthly_contribution':'₹{:,.0f}','funded_monthly':'₹{:,.0f}','funding_ratio':'{:.1%}','current_corpus':'₹{:,.0f}'}),hide_index=True,use_container_width=True)
        if sum(g['monthly_contribution'] for g in goals)>min(surplus,profile.get('monthly_investment',surplus)):
            st.warning('Requested contributions exceed the shared investment budget. Contributions are scaled pro-rata; increase the budget, reduce targets or extend goal dates.')
        st.markdown('#### Career-adjusted household cash-flow scenarios')
        years_view=st.slider('Projection horizon (years)',1,30,15)
        paths=[]
        for scen in ['conservative','base','optimistic']:
            vals=salary_path(profile.get('income',0),profile.get('income_growth',.06),years_view,scen)
            paths.append({'Scenario':scen.title(),'Year':list(range(years_view+1))[-1],'Monthly income at horizon':vals[-1]})
        st.dataframe(pd.DataFrame(paths).style.format({'Monthly income at horizon':'₹{:,.0f}'}),hide_index=True,use_container_width=True)
        st.line_chart(pd.DataFrame({'Conservative':salary_path(profile.get('income',0),profile.get('income_growth',.06),years_view,'conservative'),'Base':salary_path(profile.get('income',0),profile.get('income_growth',.06),years_view,'base'),'Optimistic':salary_path(profile.get('income',0),profile.get('income_growth',.06),years_view,'optimistic')}))
        if analysis:
            g=analysis['goal_simulation']; c1,c2,c3=st.columns(3); c1.metric('Primary-goal attainment',f"{g['goal_probability']:.1%}"); c2.metric('10th percentile corpus',f"₹{g['p10']:,.0f}"); c3.metric('90th percentile corpus',f"₹{g['p90']:,.0f}")
            st.caption(f"Primary goal only: {g['method']} across {g['simulations']:,} paths. Goal target is inflation-adjusted. The current bundled multi-asset history is insufficient for a fully empirical portfolio bootstrap; Gaussian proxy results are not forecasts.")
        st.caption('Separate per-goal portfolio optimisation is shown as a planning architecture; the current full Monte Carlo engine remains attached to the primary goal. Other goals share the household budget but do not yet each have independent path simulations.')


elif page=='Risk lab':
    st.title('Risk research lab')
    st.write('Explore historical tail risk, regime-conditioned scenarios and a walk-forward allocation baseline. Results depend on the selected historical sample and are not forecasts.')
    if prices.empty or len(prices.columns) < 2:
        st.warning('Build the external price panel and mutual-fund NAV panel to expand empirical coverage.')
    else:
        available=list(prices.columns)
        default=[x for x in ['Nifty 50 ETF','Gold ETF','Nifty 500 Index Proxy','Embassy REIT Price'] if x in available]
        selected=st.multiselect('Empirical assets',available,default=default or available[:min(3,len(available))])
        benchmarks=[x for x in available if x.startswith('Nifty') or x=='Sensex Index Proxy']
        if benchmarks:
            benchmark=st.selectbox('Benchmark series',benchmarks)
        else:
            benchmark=available[0]
        horizon=st.slider('Simulation horizon (months)',12,240,60,step=12)
        simulations=st.select_slider('Simulation paths',[500,1000,2500,5000,10000],value=2500)
        if len(selected)<1:
            st.info('Select at least one asset to calculate historical tail risk.')
        else:
            weights={x:1/len(selected) for x in selected}
            try:
                port=portfolio_return_series(prices,weights)
                cvar=historical_cvar(port,0.95)
                a,b,c1=st.columns(3)
                a.metric('Historical 95% VaR',f"{cvar['var']:.2%}")
                b.metric('Historical 95% CVaR',f"{cvar['cvar']:.2%}")
                c1.metric('Worst daily return',f"{cvar['worst_return']:.2%}")
                st.caption(f"Based on {cvar['observations']:,} aligned daily observations. Loss figures are daily historical estimates.")
            except ValueError as exc:
                st.warning(str(exc))
            if benchmark in prices.columns and benchmark not in selected:
                try:
                    result=regime_switching_monte_carlo(
                        prices,weights,benchmark=benchmark,horizon_months=horizon,
                        simulations=int(simulations)
                    )
                    st.subheader('Regime-switching Monte Carlo')
                    a,b,c1=st.columns(3)
                    a.metric('Current descriptive regime',result['current_regime'])
                    b.metric('Probability of terminal loss',f"{result['probability_of_loss']:.1%}")
                    c1.metric('Median terminal wealth',f"{result['median_terminal_wealth_multiple']:.2f}×")
                    st.write('Terminal wealth multiples: 5th percentile',f"{result['p05_terminal_wealth_multiple']:.2f}×",'| 95th percentile',f"{result['p95_terminal_wealth_multiple']:.2f}×")
                    st.dataframe(result['regime_summary'],use_container_width=True)
                    st.caption(result['method']+'. Regimes are descriptive historical clusters; the within-regime distribution is an approximation.')
                except ValueError as exc:
                    st.info(f'Regime simulation unavailable: {exc}')
            try:
                wf=walk_forward_backtest(prices,benchmark=benchmark,lookback=252,rebalance_every=21)
                rows=[]
                for label,key in [('Optimised portfolio','portfolio_metrics'),('Benchmark','benchmark_metrics')]:
                    m=wf[key]
                    rows.append({'Series':label,'CAGR':m['cagr'],'Volatility':m['volatility'],'Maximum drawdown':m['max_drawdown'],'Total return':m['total_return']})
                st.subheader('Walk-forward baseline')
                st.dataframe(pd.DataFrame(rows).style.format({k:'{:.2%}' for k in ['CAGR','Volatility','Maximum drawdown','Total return']}),hide_index=True,use_container_width=True)
                st.caption(f"Out-of-sample window: {wf['out_of_sample_start']} to {wf['out_of_sample_end']}. Walk-forward minimum-variance baseline; no taxes, exit loads or transaction costs.")
            except ValueError as exc:
                st.info(f'Walk-forward backtest unavailable: {exc}')

elif page=='Tax intelligence':
    st.title('Tax intelligence')
    st.write('Compare both tax regimes against your salary and eligible deductions before choosing. The calculation is a simplified salary-only estimate for Tax Year 2026-27.')
    st.warning('Not a tax return or CA opinion. It excludes surcharge, marginal relief, capital gains, special-rate income, HRA and several individual deductions. Verify eligibility and current law before acting.')
    gross=st.number_input('Annual gross salary (₹)',0,100000000,int(profile.get('income',0)*12),step=50000)
    deductions=st.number_input('Old-regime eligible deductions / exemptions aggregate (₹)',0,10000000, min(500000,int(profile.get('existing_80c',0)+0)),step=10000,help='Enter only amounts you have verified as eligible: e.g. 80C, 80D, eligible HRA and home-loan interest, subject to their separate limits and rules.')
    other=st.number_input('Other ordinary taxable income (₹)',0,100000000,0,step=10000)
    comp=compare_regimes(gross,deductions,other)
    c1,c2,c3=st.columns(3); c1.metric('Estimated new-regime tax',f"₹{comp['new']['tax_including_cess']:,.0f}"); c2.metric('Estimated old-regime tax',f"₹{comp['old']['tax_including_cess']:,.0f}"); c3.metric('Lower estimate',comp['recommended'],delta=f"₹{comp['difference']:,.0f} lower")
    st.success(f"On the inputs entered, the {comp['recommended']} regime has the lower estimated tax. Save this as a planning indication, not a final election.")
    st.dataframe(pd.DataFrame([{'Regime':'New','Taxable income':comp['new']['taxable_income'],'Tax before rebate':comp['new']['tax_before_rebate'],'Rebate assumed':comp['new']['rebate_assumed'],'Tax incl. 4% cess':comp['new']['tax_including_cess']},{'Regime':'Old','Taxable income':comp['old']['taxable_income'],'Tax before rebate':comp['old']['tax_before_rebate'],'Rebate assumed':comp['old']['rebate_assumed'],'Tax incl. 4% cess':comp['old']['tax_including_cess']}]).style.format({c:'₹{:,.0f}' for c in ['Taxable income','Tax before rebate','Rebate assumed','Tax incl. 4% cess']}),hide_index=True,use_container_width=True)
    with st.expander('What are the regimes? Benefits and trade-offs'):
        st.markdown('**New regime**\n- Lower, more graduated slab rates and simpler compliance.\n- Most common deductions/exemptions such as 80C and HRA are generally unavailable.\n- Often benefits people with modest deductions or who prefer flexibility.')
        st.markdown('**Old regime**\n- Higher slab rates but permits specified deductions/exemptions, subject to eligibility and limits (for example 80C, 80D, eligible HRA and home-loan interest).\n- May be better when eligible deductions are substantial.\n- Requires documentation and careful eligibility checks.')
    st.markdown('#### Calculation assumptions')
    for item in comp['assumptions']: st.caption('• '+item)
    st.markdown('#### Capital-gains estimator')
    gain=st.number_input('Realised listed-equity gain (₹)',0,100000000,100000,step=5000); holding=st.number_input('Holding period (months)',1,600,18)
    t=equity_gain_tax(gain,holding); c1,c2=st.columns(2); c1.metric('Estimated tax',f"₹{t['estimated_tax']:,.0f}"); c2.metric('After-tax gain',f"₹{gain-t['estimated_tax']:,.0f}")
    st.caption('Capital-gains module is separate from the salary-regime comparison and remains simplified. It does not model every asset type, loss set-off, surcharge, STT, exit load or individual tax circumstances.')

    st.divider()
    st.subheader('Instrument-specific capital-gains estimator')
    st.caption('A separate estimate from salary-regime comparison. Choose the closest instrument classification and verify it against the applicable tax year.')
    tax_asset=st.selectbox('Investment type',[
        'listed_equity','equity_mutual_fund','business_trust_unit','gold_etf',
        'silver_etf','listed_gsec','physical_gold','physical_silver',
        'debt_mutual_fund_50aa','other_mutual_fund','unlisted_bond','sgb_secondary_sale'
    ],format_func=lambda x:{
        'listed_equity':'Listed equity shares','equity_mutual_fund':'Equity-oriented mutual fund',
        'business_trust_unit':'Listed REIT / InvIT unit','gold_etf':'Gold ETF',
        'silver_etf':'Silver ETF','listed_gsec':'Listed government security',
        'physical_gold':'Physical gold','physical_silver':'Physical silver',
        'debt_mutual_fund_50aa':'Specified debt mutual fund (Section 50AA)',
        'other_mutual_fund':'Other mutual fund','unlisted_bond':'Unlisted bond',
        'sgb_secondary_sale':'Sovereign Gold Bond'
    }[x])
    gain=st.number_input('Realised capital gain (₹)',min_value=0.0,value=50000.0,step=5000.0)
    holding=st.number_input('Holding period (months)',min_value=0,max_value=600,value=18,step=1)
    slab=st.selectbox('Estimated marginal slab rate', [0.05,0.10,0.15,0.20,0.25,0.30],index=5,format_func=lambda x:f'{x:.0%}')
    stt=st.checkbox('Section 112A STT conditions satisfied',value=True)
    sgb_original=False
    sgb_continuous=False
    sgb_maturity=False
    if tax_asset=='sgb_secondary_sale':
        sgb_original=st.checkbox('Subscribed at original RBI issue',value=False)
        sgb_continuous=st.checkbox('Held continuously from original issue to maturity',value=False)
        sgb_maturity=st.checkbox('Redemption is at maturity (not secondary sale or premature exit)',value=False)
    if st.button('Estimate capital-gains tax'):
        try:
            estimate=estimate_capital_gains(
                tax_asset,gain,holding,slab,stt_eligible=stt,
                sgb_original_subscriber=sgb_original,
                sgb_held_continuously_to_maturity=sgb_continuous,
                sgb_redemption_at_maturity=sgb_maturity
            )
            a,b,c1=st.columns(3)
            a.metric('Classification',estimate['classification'])
            b.metric('Tax before cess',f"₹{estimate.get('tax_before_cess',0):,.0f}")
            c1.metric('Estimated tax incl. cess',f"₹{estimate['estimated_tax']:,.0f}")
            st.caption(estimate['rule_basis'])
            st.warning(estimate['warning'])
        except ValueError as exc:
            st.error(str(exc))
    st.subheader('SGB coupon interest')
    coupon=st.number_input('Annual SGB coupon income (₹)',min_value=0.0,value=0.0,step=500.0)
    if st.button('Estimate SGB coupon tax'):
        coupon_result=sgb_coupon_tax(coupon,slab)
        st.metric('Estimated coupon tax including cess',f"₹{coupon_result['estimated_tax']:,.0f}")
        st.caption(coupon_result['warning'])

elif page=='Market intelligence':
    st.title('Market intelligence'); st.write('Market regime detection and data provenance.')
    c1,c2,c3=st.columns(3); c1.metric('Market regime',regime['label']); c2.metric('Price series',len(prices.columns)); c3.metric('Aligned daily observations',len(prices))
    if not prices.empty:
        st.line_chart((1+prices).cumprod(),height=280)
        st.dataframe(pd.DataFrame([{'Series':c,'Observations':prices[c].count(),'Start':str(prices[c].dropna().index.min().date()),'End':str(prices[c].dropna().index.max().date()),'Evidence':'Historical ETF price series' if c in ['Nifty 50 ETF','Gold ETF'] else 'Downloaded proxy; see manifest'} for c in prices.columns]),hide_index=True,use_container_width=True)
    if regime.get('latest'): st.write('Latest regime features'); st.json(regime['latest'])
    st.markdown('#### Data limitations')
    st.write('- Bundled Nifty 50 ETF and Gold ETF data: 2020–2025, 1,486 observations each. These are ETF price histories, not a 20-year Nifty TRI dataset.')
    st.write('- Other assets use explicitly marked prior assumptions until actual time series are acquired.')
    st.write('- Run `python data/download_market_universe.py --years 10` to attempt free Yahoo Finance adjusted-close ETF proxies. Provider availability, survivorship and tracking differences must be documented.')
    st.write('- For research-grade long history, replace Nifty ETF prices with NSE Indices TRI; use AMFI NAV for mutual funds; RBI DBIE for G-Sec yields; official rate notifications for FD/PPF.')

    st.divider()
    st.subheader('Sovereign Gold Bonds')
    try:
        sgb_master=load_sgb('master')
        sgb_cashflows=load_sgb('cashflows')
        sgb_quotes=load_sgb('market_prices')
        sgb_table=sgb_instrument_table(sgb_master,sgb_cashflows,sgb_quotes)
        st.caption('Source catalogue and reported per-gram cash flows. Verify tranche ISIN, event completeness, current quote date and official redemption notices.')
        st.metric('Tranches in source catalogue',f"{len(sgb_table):,}")
        display_cols=[x for x in ['Tranche','Symbol','ISIN','Issue_Date','Maturity_Date','Issue_Price','Coupon_Rate_Pct','cashflow_events','coupon_cash_per_gram','redemption_cash_per_gram','Exchange','LTP','Premium_Discount_Pct','Status'] if x in sgb_table]
        st.dataframe(sgb_table[display_cols],hide_index=True,use_container_width=True)
    except (FileNotFoundError,ValueError,KeyError) as exc:
        st.info(f'SGB source data unavailable: {exc}')

    st.divider()
    st.subheader('Government bond yield sensitivity')
    try:
        gsec=load_macro('GSEC_10Y_YIELD')
        date_col=next((x for x in ['Date','date'] if x in gsec.columns),None)
        yield_col=next((x for x in ['Close','close','Yield','yield'] if x in gsec.columns),None)
        if date_col and yield_col:
            gsec[date_col]=pd.to_datetime(gsec[date_col],errors='coerce')
            gsec[yield_col]=pd.to_numeric(gsec[yield_col],errors='coerce')
            gsec=gsec.dropna(subset=[date_col,yield_col]).sort_values(date_col)
            duration=st.number_input('Illustrative modified duration (years)',min_value=0.0,max_value=30.0,value=5.0,step=0.5)
            scenarios=yield_curve_scenarios(gsec[yield_col],duration_years=duration)
            st.metric('Latest source 10-year yield',f"{gsec[yield_col].iloc[-1]:.2f}%")
            st.dataframe(scenarios,hide_index=True,use_container_width=True)
            st.caption('Duration/convexity sensitivity only. The RBI yield history is not a bond price or total-return series.')
        else:
            st.info('The source yield file does not expose recognised date/yield columns.')
    except (FileNotFoundError,ValueError,KeyError) as exc:
        st.info(f'Government yield data unavailable: {exc}')

elif page=='Learn':
    st.title('Learn investing'); st.write('A small reference library that explains the building blocks behind your strategy.')
    topics={'Asset allocation':'How investments are distributed across equity, debt, gold and cash. Allocation should reflect goals, horizon, liquidity and risk capacity.','Compounding':'Returns earned on prior returns. Compounding is powerful over long horizons, but actual returns are volatile and not guaranteed.','Volatility':'A statistical measure of return dispersion. It does not capture every kind of risk and does not guarantee the maximum possible loss.','Maximum drawdown':'The largest peak-to-trough decline in a historical portfolio value series.','Diversification':'Combining exposures whose returns are not perfectly correlated can reduce portfolio volatility. It cannot eliminate market risk.','Sharpe ratio':'Excess return per unit of total volatility. It is sensitive to the chosen risk-free rate and historical sample.','CVaR':'Conditional Value at Risk estimates the average loss in the tail beyond a selected VaR threshold.','SIP':'A systematic periodic investment. It structures contributions but does not guarantee profit or protect against loss.','ELSS':'An equity-linked savings scheme with a statutory three-year lock-in for each investment instalment. Tax benefit depends on tax regime and eligibility.','Rebalancing':'Restoring portfolio weights to target ranges. It may create taxes, transaction costs and exit loads.'}
    for title,body in topics.items():
        with st.expander(title): st.write(body)

elif page=='Wealth conversation':
    st.title('Your wealth conversation'); st.write('A guided conversation to understand your circumstances, then an assistant for your ongoing financial questions.')
    if 'onboarding_step' not in st.session_state: st.session_state.onboarding_step=0
    hist=load_chat(uid)
    for h in hist:
        with st.chat_message(h['role']): st.write(h['content'])
    if not profile:
        step=min(st.session_state.onboarding_step,len(STEPS)-1)
        st.info('I will ask one thing at a time. You can answer in your own words; you can review and correct everything in My financial profile.')
        st.markdown('**To start:** '+STEPS[step][1])
        prompt=st.chat_input('Type your answer…')
        if prompt:
            save_chat(uid,'user',prompt)
            with st.chat_message('user'): st.write(prompt)
            key=STEPS[step][0]
            new_profile,ok,error=parse_step(key,prompt,st.session_state.get('onboarding_profile',{}))
            if ok:
                st.session_state.onboarding_profile=new_profile
                st.session_state.onboarding_step=step+1
                if st.session_state.onboarding_step>=len(STEPS):
                    p=st.session_state.onboarding_profile
                    if p.get('monthly_investment',0)>max(0,p.get('income',0)-p.get('expenses',0)):
                        st.session_state.onboarding_step=4
                        answer='Your stated monthly investment is higher than your monthly surplus. Let us revisit the amount you can comfortably invest. '+STEPS[4][1]
                        with st.chat_message('assistant'): st.write(answer)
                        save_chat(uid,'assistant',answer); st.rerun()
                    # Derive a provisional risk score from the separate tolerance and capacity answers.
                    p['risk_score']=int(round(.45*p['risk_tolerance']+.55*p['risk_capacity']))
                    p.setdefault('debt',0); p.setdefault('dependants',0); p.setdefault('tax_regime','New'); p.setdefault('existing_80c',0); p.setdefault('goal_inflation',.06)
                    save_profile(uid,p); st.session_state.onboarding_step=0; st.session_state.onboarding_profile={}
                    answer='Thank you. I have assembled your initial financial profile. I will now calculate goal feasibility and a portfolio strategy. Please review the extracted figures in My financial profile before relying on the results.'
                else: answer='Thanks. '+STEPS[st.session_state.onboarding_step][1]
            else: answer=error
            with st.chat_message('assistant'): st.write(answer)
            save_chat(uid,'assistant',answer); st.rerun()
    else:
        prompt=st.chat_input('For example: Can I afford a house in seven years and still invest for retirement?')
        if prompt:
            save_chat(uid,'user',prompt)
            with st.chat_message('user'): st.write(prompt)
            with st.chat_message('assistant'):
                with st.spinner('Reviewing your financial context…'):
                    answer=reply(prompt,profile,analysis,hist)
                st.write(answer)
            save_chat(uid,'assistant',answer)
            if not ollama_available(): st.caption('Local LLM unavailable; deterministic conversational fallback is active. Install Ollama and pull qwen2.5:3b to enable local language-model responses.')
