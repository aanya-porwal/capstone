# DWMS — Local Personal Wealth Intelligence Prototype

A local-first Streamlit prototype for conversational onboarding, financial profiling, goal planning, quantitative portfolio construction, scenario analysis and illustrative Indian tax logic.

## Run on Windows 11

1. Install Python 3.10 or 3.11 (64-bit).
2. Extract the ZIP into a writable folder.
3. Open PowerShell in that folder.
4. Create and activate an environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements-prototype.txt
   ```

5. Start the application:

   ```powershell
   streamlit run streamlit_app.py
   ```

   Or double-click `run_dwms.bat` (it installs the small prototype requirements and launches Streamlit).

6. Create a local account. Passwords are stored as PBKDF2-HMAC-SHA256 hashes with per-user random salts. Profiles, goals, recommendation snapshots and conversation messages are stored in `data/dwms_users.db`.

## Optional local LLM

Read `OLLAMA_SETUP.md`. The suggested `qwen2.5:3b` model runs locally via Ollama. The app uses CPU inference and works without Ollama using a deterministic fallback. No paid API key is required.

## What is implemented

- Local multi-user registration and login; per-user profile, recommendations and chat history in SQLite.
- Conversational onboarding that asks one question at a time and extracts approximate answers, with a profile page for review/correction.
- Separate risk-tolerance and risk-capacity inputs; these are user-reported planning indicators, not validated psychometric measures.
- Career-aware profile fields (employment type, sector, experience, income growth, expense growth and EMI) with conservative/base/optimistic income trajectories.
- Multiple simultaneous goals stored in the user profile, with distinct target/horizon/corpus/contribution fields and pro-rata funding against a shared household surplus. The full Monte Carlo remains primary-goal-only in this revision; this limitation is disclosed in-app.
- Allocation explanation table describing each asset sleeve, its portfolio role, data quality and horizon suitability.
- Side-by-side simplified new/old regime tax estimate for Tax Year 2026-27, with slab assumptions, standard deduction, indicative rebate and 4% cess; includes clear exclusions and regime trade-offs.
- Goal target inflation adjustment; monthly contribution and goal horizon feed the simulation.
- 13-instrument prototype universe spanning Indian/global equity, gold, fixed income, deposits, ELSS, PPF and NPS.
- SLSQP constrained portfolio optimisation with risk-score/horizon-based equity and volatility caps; alternative minimum-variance and risk-parity objectives.
- Empirical statistics for the two bundled series, transparent correlation priors for unobserved assets, Ledoit-Wolf shrinkage for the observed covariance block, and positive-semidefinite covariance repair.
- Unsupervised K-Means market regime classification using rolling volatility, momentum and drawdown. This is descriptive regime clustering, not a validated market forecast.
- Goal simulation. Historical moving-block bootstrap is used only when all material holdings have aligned empirical data; otherwise a Gaussian proxy simulation is explicitly labelled.
- Tax module: old-regime 80C headroom constraint for ELSS/PPF allocation, equity STCG/LTCG estimator, tax-aware illustrative withdrawal-lot selection and drift-band rebalance suggestions.
- Data provenance and educational reference pages.

## Data inventory and limitations

Bundled files:

- `data/nifty50_historical.csv`: 1,486 daily observations, 2020-01-01 to 2025-12-31; closing price series labelled Nifty 50 ETF in the existing project.
- `data/goldbees_historical.csv`: 1,486 daily observations, 2020-01-01 to 2025-12-31; GoldBees ETF closing price.

These are not 20-year histories and the Nifty ETF price series is not the Nifty 50 Total Returns Index. Other asset classes do not have bundled observed price histories. Their return/volatility/correlation inputs are transparent priors/assumptions, not empirical estimates. The system must not be represented as if all 13 assets have 20-year observed data.

Optional downloader (expanded ETF proxy coverage; still not official TRI/NAV data):

```powershell
python data\download_market_universe.py --years 10
```

This attempts to download free Yahoo Finance adjusted-close ETF proxies into `data/prices/`. Provider coverage and ticker availability may change. These are ETF proxies, not official index TRI or mutual fund NAV. Check `data/prices/download_manifest.json` and inspect each series before using it in research. A failed download is not replaced with fabricated values.

Recommended authoritative sources for research-grade data:

- NSE Indices historical data: https://www.niftyindices.com/reports/historical-data (use Nifty 50 TRI rather than price return index).
- AMFI NAV download: https://www.amfiindia.com/net-asset-value/nav-download (mutual-fund scheme NAV; downloads may require date batching).
- RBI DBIE: https://dbie.rbihub.in/ (government security yields, gold prices and macro data).
- SBI deposit rates: https://sbi.bank.in/en/web/interest-rates/interest-rates/deposit-rates
- Department of Economic Affairs small savings notifications: https://dea.gov.in/
- NPS Trust: https://npstrust.org.in/

## Quantitative methodology and caveats

1. Historical observed asset return: daily price percentage changes. Historical annualised volatility uses daily sample standard deviation times square-root 252. Historical CAGR uses geometric compounding over observed trading days.
2. Expected return: observed asset CAGR is blended 45% with the prior return 55%, then clipped to a broad planning range. This is a stabilising assumption, not a predictive estimator.
3. Covariance: transparent class-level correlation priors are used where observations are absent. Ledoit-Wolf shrinkage is applied to the empirical block of assets with sufficient aligned history. The resulting matrix is eigenvalue-floored to ensure positive semidefiniteness. This hybrid matrix is partly model-assumed.
4. Optimisation: SLSQP minimises a return-risk utility, minimum variance or risk-contribution dispersion subject to full investment, non-negative weights, asset caps, equity exposure and a risk ceiling. If the risk ceiling is infeasible, the fallback relaxes the volatility ceiling while retaining the equity cap; check reported volatility before interpreting output.
5. Market regimes: K-Means with three clusters on rolling realised volatility, momentum, drawdown and gold momentum. Cluster labels are assigned by a transparent composite score. This is exploratory and in-sample; no forecasting or trading signal claim is made.
6. Goal simulations: contributions are added monthly after each simulated return. The future goal is inflated at the user-selected annual goal inflation. A historical block bootstrap is only used if every material portfolio holding has aligned observed return history. With current bundled data the app correctly falls back to a Gaussian proxy using the model's estimated mean and volatility.
7. Tax: the salary tax comparison is a simplified Tax Year 2026-27 illustration; it excludes surcharge, marginal relief, special-rate income, HRA and many personal eligibility checks. The capital-gains/lot modules remain narrow and illustrative. It models equity-oriented listed-security gain estimates, basic 80C headroom under old-regime assumptions, and a demonstration tax-aware lot ordering. It omits detailed slab tax, surcharge/marginal relief, all instrument-specific tax categories, STT, loss set-off, exit loads, dividend tax, actual lot-level FIFO rules, and legal transition complexities. Rebalancing is a drift-band suggestion only; it requires supplied holdings and tax lots and does not execute trades. Do not use it for filing or investment execution.

## Testing

Run:

```powershell
pytest -q
```

The original test suite is retained, with additional tests for covariance validity, optimisation, simulation fallback and tax calculations.

## Next engineering steps

1. Replace ETF proxies with official Nifty TRI, AMFI NAV and RBI data; store raw source files and download timestamps.
2. Add monthly aligned total-return series for every investable exposure; do not infer unavailable returns from an asset label.
3. Add walk-forward regime validation, out-of-sample optimisation, block bootstrap and backtesting with transaction costs.
4. Add a full Indian tax rules engine reviewed against the Income-tax Act, 2025 / Rules, 2026 and current official guidance; include slab tax, surcharge, cess, loss harvesting, FIFO lots and instrument-specific rules.
5. Extend per-goal independent portfolio optimisation and Monte Carlo; this revision supports multiple goal budgets but only simulates the legacy primary goal end-to-end.
6. Add a proper drift-band rebalancer, trade-cost model and tax-aware sell-lot selection before claiming full tax-aware rebalancing.
7. Add automated tests for profile parsing, user isolation, numerical edge cases and UI flows.

## Safety and intended use

This is an academic research and demonstration prototype. It does not provide regulated investment advice, verify suitability under SEBI requirements, connect to a broker, or execute trades. Outputs are estimates under disclosed assumptions and can be wrong. User data is stored locally in plaintext SQLite apart from password hashes; protect the device and database file.

## External research dataset integration

The DWMS research loaders can read the separately cloned dataset repository:

- Repository: https://github.com/aswinv90/indian-market-historical-data
- Local folder expected by default: `../dwms_research_data` (sibling of this project folder).
- Override with `DWMS_RESEARCH_DATA_DIR` if the clone is elsewhere.
- Source licence: non-commercial, personal and educational research only. Commercial use requires prior written permission from the dataset author. Review the source repository `LICENSE` before redistributing any data.

### Windows PowerShell

```powershell
$env:DWMS_RESEARCH_DATA_DIR = "C:\Users\aanya\Downloads\DWMS_local_prototype\dwms_research_data"
python data\build_research_manifest.py
```

### Available loaders

- `load_index("NIFTY_50")`, `load_index("NIFTY_500")` and other index files.
- `load_listed_security("GOLDBEES", "BSE")` and other listed securities.
- `load_gold_etf_prices()` for listed gold ETF price proxies available in the source tree.
- `load_reit_invit_prices()` for listed REIT/InvIT unit price histories available in the source tree.
- `load_commodity("GOLD")` and `load_commodity("SILVER")` for bullion reference prices.
- `load_mutual_fund_catalog()` and `load_mutual_fund_nav(scheme_code)` for scheme metadata and NAV history.
- `load_sgb("master" | "cashflows" | "market_prices")` for SGB reference data.
- `load_macro("CPI" | "FX" | "GSEC_10Y_YIELD" | "RBI_POLICY")` for macro and rates context.
- `load_corporate_actions()` for listed-equity corporate actions.

`data/build_research_manifest.py` writes a local coverage report to `data/research_coverage.csv` and metadata to `data/research_coverage.json`. These generated files are local outputs and should not be committed unless intentionally curated. The price-panel builder exports only selected derived CSV series into `data/prices/`; raw Parquet data stays in the external clone. The quantitative engine reads these files with sparse date alignment, so one asset’s shorter history does not truncate every other asset. New series remain price-return proxies until their TRI, corporate-action and distribution treatment is verified.

### Return-series safeguards

- Index files are not assumed to be total-return indices (TRI).
- Gold/silver bullion prices are not ETF returns.
- Listed REIT/InvIT unit prices exclude cash distributions until those events are explicitly incorporated.
- A 10-year government bond yield series is not a government-bond return series.
- Mutual-fund NAVs must be classified by scheme, plan (Direct/Regular), option (Growth/IDCW), merger history and inception date before portfolio use.
- The source repository is useful for research coverage but its own licence restricts commercial use; do not redistribute its raw files or use them in a commercial deployment without permission.

The integration loaders expose source observations and provenance. They do not silently turn proxies into investible total-return histories. Optimiser eligibility must be granted only after data-quality and return-methodology checks.

## Expanded empirical panel and advanced risk research

After the external research clone is available, run:

```powershell
$env:DWMS_RESEARCH_DATA_DIR = "C:\Users\aanya\Downloads\DWMS_local_prototype\dwms_research_data"
python data\build_research_manifest.py
python data\build_research_price_panel.py
pytest -q
```

The price-panel builder exports selected index, Gold BeES, REIT and InvIT price series into local ignored files under `data/prices/`. `dwms.quant.load_prices()` reads them using an outer date join so shorter histories do not truncate the entire panel. `estimate_moments()` uses observed data where sufficiently covered and retains labelled assumptions for unobserved instruments.

The advanced research module `engine/advanced_risk.py` provides:
- Historical empirical VaR and CVaR.
- Three-state Markov regime-switching Monte Carlo, with regimes clustered from trailing benchmark volatility, momentum and drawdown.
- Walk-forward, long-only minimum-variance backtesting with trailing-window estimation and buy-and-hold benchmark comparison.

The regime simulation uses a Gaussian within-regime monthly approximation and should be compared with block-bootstrap and stress scenarios. The walk-forward engine is a baseline, not yet a full tax-aware transaction-cost-aware implementation. Neither engine should be presented as validated until tests have been run on the local source data and sensitivity analysis is complete.


### Mutual-fund research universe

Build a shortlist from the source master directory:

```powershell
python data\build_mutual_fund_universe.py --min-records 500 --per-category 3 --export-navs
```

This exports a catalogue audit, a category-based shortlist of recent Direct Growth schemes, selected NAV histories, and an aligned NAV return panel. The shortlist is capped per category rather than treating all 37,896 schemes as separate optimiser candidates. Growth-plan NAVs reflect reinvested distributions and are net of fund expenses; they remain subject to scheme-merger, benchmark and survivorship checks. Observed NAV history is blended into the quantitative engine when available. This is a research screening set, not a recommendation list.


### Distribution-adjusted listed trust returns

The research price-panel builder also attempts a conservative REIT/InvIT distribution adjustment using explicitly labelled dividend/distribution events from the source corporate-actions table. It writes a separate synthetic return-index proxy and records accepted, rejected and unmatched events in the manifest. It does not interpret splits, bonuses or ambiguous action amounts as cash distributions. Review each trust's diagnostics before treating the result as total return; incomplete corporate-action coverage means the series remains a proxy.


### SGB and fixed-income research

- `engine/sgb.py` joins RBI SGB tranche metadata, reported per-gram cash flows and secondary-market quote fields by ISIN. It summarises coupon and redemption cash flows separately. The cash-flow table is not assumed complete; validate against official RBI redemption notices.
- `engine/fixed_income.py` converts a user-supplied modified duration and convexity into a local parallel-yield-shock price sensitivity. It does not treat the RBI 10-year yield series as a bond return series.
- The Market intelligence page exposes the SGB catalogue and yield-sensitivity table when the external dataset is available.

### Instrument-aware tax estimates

The Tax intelligence page includes a separate instrument-level estimator for listed equity, equity mutual funds, business-trust units, gold/silver ETFs, physical metals, specified debt mutual funds, other mutual funds, bonds and SGBs. SGB coupon income is estimated separately from capital gains.

For Tax Year 2026-27, the SGB maturity exemption is gated on all three conditions: original subscription by an individual, continuous holding from original issue, and redemption at maturity. Secondary-market acquisition and premature redemption do not satisfy this exemption. The estimator uses broad category assumptions and excludes surcharge, marginal relief, loss set-off, treaty effects, TDS and several instrument-specific distribution rules. Do not use it for filing.

Official reference points:
- Income-tax Department, Income-tax Act 2025 and Rules 2026: https://www.incometaxindia.gov.in/en/income-tax-act-202511
- CBDT / Income-tax Department, Budget 2026 SGB FAQ: https://incometaxindia.gov.in/Documents/Budget2026/FAQs-Budget-2026.pdf
- Income-tax Department capital-gains guidance: https://www.incometaxindia.gov.in/w/capital-gain
- AMFI mutual-fund tax guidance: https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TaxRegimeForMutualFunds

Tax rules change and depend on instrument structure, acquisition date, listing, STT and investor status. Verify the current Act, Rules and notifications before using any estimate.
