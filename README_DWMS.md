# DWMS — Quantitative Wealth Management Research Prototype

A local-first Streamlit research prototype for Indian household financial planning, multi-goal portfolio construction, risk analysis and illustrative tax-aware modelling. It is an academic engineering system, not regulated investment advice or a production investment platform.

## Run on Windows 11

1. Install Python 3.10 or 3.11 (64-bit).
2. Open PowerShell in the project directory.
3. Create and activate an environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements-prototype.txt
   streamlit run streamlit_app.py
   ```

4. Optional: configure the separate research dataset path using `DWMS_RESEARCH_DATA_DIR`; see the research-data section below.
5. Run tests with `pytest -q`.

The Streamlit prototype stores profiles, goals and chat history in a local SQLite database. Passwords are PBKDF2-HMAC-SHA256 hashes with per-user salts. The database itself is not encrypted. Protect the device and database file.

## Current implementation inventory

### Application and planning
- Streamlit application with local registration/login, profile capture, conversational onboarding and profile review.
- Household cash-flow and career-income scenarios.
- Multiple goal records with pro-rata contributions constrained by a shared monthly budget.
- Goal-specific risk constraints and portfolio allocations.
- Correlated household Monte Carlo reporting marginal goal probabilities and the probability that all goals succeed on the same simulated household path.
- Tax intelligence, market intelligence, risk lab and goal-planning pages.

### Portfolio and quantitative engine
- SLSQP constrained portfolio optimisation with balanced-utility, minimum-variance and risk-parity objectives.
- Risk-score and horizon-dependent exposure constraints, asset bounds, old-regime 80C headroom constraints, and fallback when the requested risk cap is infeasible.
- Expected-return priors blended with observed history; class-level correlation priors for assets without sufficient common history.
- Ledoit-Wolf covariance shrinkage for the empirical observed block and positive-semidefinite covariance repair.
- Black-Litterman reverse optimisation, Bayesian posterior expected returns from explicit views and confidence levels, and long-only mean-variance allocation with optional turnover penalty.
- Student-t GARCH(1,1) maximum-likelihood estimation, volatility forecasts and parametric VaR/CVaR.
- K-Means descriptive regime clustering and Markov regime-switching Monte Carlo.
- Historical VaR/CVaR and walk-forward minimum-variance, equal-weight and benchmark comparison with configurable transaction-cost assumptions, turnover, CAGR, Sharpe, Sortino, drawdown and Calmar metrics.
- Financial-data quality diagnostics for invalid dates/values, non-positive prices, duplicate dates, ordering and availability timestamps; a conservative point-in-time filter excludes unknown or not-yet-published observations.
- Leakage-controlled walk-forward ML return forecasting using lagged/momentum/volatility features, Ridge and histogram gradient boosting, compared with a historical-mean baseline.

### Instruments and research data
- Prototype assumptions for equity, global equity, gold, fixed income, deposits, ELSS, PPF, NPS, index proxies, gold ETF, REITs and InvITs.
- External data loaders for indices, listed securities, commodity references, mutual-fund NAV/catalogue, SGBs, macro series and corporate actions.
- Mutual-fund shortlist pipeline for recent Direct Growth schemes.
- Separate REIT/InvIT distribution-adjusted proxy builder where parseable cash distribution events exist.
- SGB cash-flow summaries and approximate fixed-income duration/convexity sensitivity.
- Instrument-aware capital-gains estimates and separate SGB coupon tax estimate.

## Quantitative methodology

### Expected returns and covariance
For asset (i), observed CAGR and a prior expected return are blended:
[
\hat\mu_i = 0.45\,\mu_{i,observed}+0.55\,\mu_{i,prior}
]
with broad clipping. This is a stabilised planning estimate, not a forecast. The covariance matrix combines transparent class-level correlation priors and observed pairwise correlations. Ledoit-Wolf shrinkage is applied to the empirical block with adequate aligned history. The hybrid covariance is eigenvalue-repaired to be positive semidefinite.

### Portfolio optimisation
The current balanced-utility objective is approximately:
[
\max_w\quad w^T\mu-0.55\,w^T\Sigma w
]
subject to full investment, long-only positions, per-asset caps, equity exposure and volatility constraints. The minimum-variance and risk-parity objectives are also available. If a volatility constraint is infeasible, the current fallback relaxes that constraint while retaining the equity cap; the output must be inspected for the realised model volatility.

### Black–Litterman
The model reverse-optimises market equilibrium returns:
[
\Pi=\delta\Sigma w_{mkt}
]
and updates them using views (P\mu=Q), view uncertainty \(\Omega\), and prior uncertainty scale \(\tau\):
[
\mu_{BL}=\left[(\tau\Sigma)^{-1}+P^T\Omega^{-1}P\right]^{-1}
\left[(\tau\Sigma)^{-1}\Pi+P^T\Omega^{-1}Q\right]
]
Investor views must be supplied explicitly. The module does not fabricate views or yet derive them from ML forecasts.

### GARCH volatility
The current volatility model is Student-t GARCH(1,1):
[
\sigma_t^2=\omega+\alpha\epsilon_{t-1}^2+\beta\sigma_{t-1}^2
]
Parameters are estimated by maximum likelihood. Student-t innovations allow heavier tails than a Gaussian assumption. EGARCH and GJR-GARCH comparison remain future work.

### ML forecasting and validation
The current forecasting module builds features from lagged returns, momentum, realised volatility, downside volatility and drawdown. It predicts the compounded next-(h)-day return. Expanding-window validation uses a purge of (h) observations so training labels do not overlap the forecast origin. Models include Ridge and histogram gradient boosting; historical-mean prediction is the baseline. Metrics include MAE, RMSE, directional accuracy and out-of-sample (R^2).

This is a forecasting research module, not yet a production signal. It is not currently wired into the live portfolio optimiser or Streamlit UI. A low forecast error alone does not establish economic value. Forecasts must be tested for stability and portfolio improvement after turnover, fees, taxes and slippage.

## Important data limitations

- Bundled Nifty and GoldBeES daily series are finite historical price series, not 20-year universal asset histories. The Nifty series is not confirmed as TRI.
- External research clone: https://github.com/aswinv90/indian-market-historical-data. The source's licence metadata is restrictive/unclear; use for personal/educational research only unless written commercial permission is obtained.
- The external repository is expected in a sibling folder named `dwms_research_data`, or configured with `DWMS_RESEARCH_DATA_DIR`. Raw Parquet data should remain outside this repository.
- Index series must not be assumed to be TRI. Commodity spot prices are not investible ETF returns. Government bond yields are not bond total returns.
- REIT/InvIT price histories exclude distributions unless the separately generated distribution proxy has been reviewed. Event coverage is not guaranteed complete.
- Mutual-fund screening is not a recommendation process. Scheme mergers, survivorship, plan/option classification and benchmark consistency require further review.
- Many instruments still rely on assumed expected returns, volatility and correlations. The universe catalogue is broader than the empirically validated price panel.

### Build external research outputs

```powershell
$env:DWMS_RESEARCH_DATA_DIR = "C:\path\to\dwms_research_data"
python data\build_research_manifest.py
python data\build_research_price_panel.py
python data\build_mutual_fund_universe.py --min-records 500 --per-category 3 --export-navs
pytest -q
```

Generated research panels and manifests are local outputs and are ignored by Git. Inspect coverage and data-quality manifests before using any new instrument in optimisation.

## Tax and regulatory limitations

Tax modules are educational estimates, not a filing engine. Instrument classification, acquisition dates, STT conditions, holding periods, exemptions, losses, surcharge, marginal relief, exit loads, TDS and individual circumstances can change results. Verify all rates and rules against the applicable official Act, Rules and notifications before relying on an estimate. The system does not assess SEBI suitability, provide regulated advice, connect to a broker or execute trades.

## Research validation and application walkthrough

### Walk-forward strategy comparison

The Risk lab compares a trailing-window Ledoit-Wolf minimum-variance portfolio against an equal-weight portfolio of eligible assets and a buy-and-hold benchmark. It reports out-of-sample CAGR, annualised volatility, zero-risk-free Sharpe/Sortino, maximum drawdown, Calmar ratio and turnover. A user-configurable transaction-cost assumption is charged on one-way turnover at rebalance dates, including initial deployment. This is a research comparison, not a claim of alpha: the current prototype does not yet model taxes, bid-ask spread, market impact, exit loads, liquidity constraints or asset-specific trading calendars.

### Data quality and point-in-time controls

The Market intelligence page runs structural diagnostics on the bundled ETF price files. `engine.data_quality.audit_price_frame` can audit arbitrary price/NAV tables, and `point_in_time_filter` filters event/fundamental observations by their actual availability timestamp. Unknown availability timestamps are excluded. These utilities do not establish source accuracy, corporate-action completeness, survivorship-bias control or investibility. Add availability timestamps at ingestion for any future fundamental or macro event feature; do not infer them from period-end dates.

### Suggested end-to-end demo

1. Create a local account and complete My financial profile.
2. Open Portfolio strategy; compare balanced utility, minimum variance and risk parity and inspect evidence and solver diagnostics.
3. Open Goals & simulations; review the goal target and contribution assumptions.
4. Open Risk lab; select empirical assets and benchmark, set transaction costs, and compare the walk-forward optimiser, equal-weight portfolio and benchmark.
5. Open Market intelligence; inspect coverage, regime features, bundled data-quality diagnostics and limitations.
6. Open Tax intelligence; treat all estimates as illustrative and inspect the tax assumptions before interpreting outputs.

## Validation status and next work

Automated tests run on Python 3.10 and 3.11 through GitHub Actions. Passing tests establish software-level checks on synthetic and bundled test fixtures; they do not validate financial assumptions or prove predictive performance.

Current next priorities:
1. Compare GARCH, EGARCH and GJR-GARCH on identical rolling windows using likelihood, AIC/BIC, volatility forecast loss and VaR exceedance tests.
2. Add Hidden Markov Models with expanding-window state estimation and regime stability diagnostics.
3. Add ML model selection, feature ablations, benchmark forecasts, prediction calibration and economic backtests.
4. Connect validated forecasts to Black-Litterman views and portfolio construction only after out-of-sample evaluation.
5. Add transaction costs, bid-ask spread, taxes, turnover and liquidity constraints to walk-forward backtests.
6. Replace price proxies with verified TRI/NAV and complete cash-distribution histories.
7. Audit and modularise the legacy Flask and Streamlit paths; establish one canonical application and one canonical quantitative API.

