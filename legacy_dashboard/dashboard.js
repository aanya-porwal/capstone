// ============================================================
// WEALTH AI - DASHBOARD JAVASCRIPT
// ============================================================


// ============================================================
// ELEMENTS
// ============================================================

const inputScreen = document.getElementById("inputScreen");
const dashboardScreen = document.getElementById("dashboardScreen");

const generatePlanButton = document.getElementById("generatePlan");
const backButton = document.getElementById("backButton");


// ============================================================
// INPUT FIELDS
// ============================================================

const fields = [
    "age",
    "income",
    "expenses",
    "debt",
    "dependents",
    "currentSavings",
    "monthlyInvestment",
    "goalAmount",
    "goalYears"
];


// ============================================================
// GET USER INPUT
// ============================================================



function getUserData() {
    const dependents = Number(
        document.getElementById("dependents").value
    );

    const dependentAgesInput =
        document.getElementById("dependentAges");

    const dependentAges = dependentAgesInput.value
        .split(",")
        .map(age => age.trim())
        .filter(age => age !== "")
        .map(Number);

    if (dependentAges.length !== dependents) {
        throw new Error(
            `Please enter the ages of all ${dependents} dependents.`
        );
    }

    if (
        dependentAges.some(
            age => !Number.isInteger(age) || age < 0 || age > 120
        )
    ) {
        throw new Error(
            "Dependent ages must be whole numbers between 0 and 120."
        );
    }

    const goalCards = [
        ...document.querySelectorAll("#goalsContainer [data-goal]")
    ];

    const goals = goalCards.map((card, index) => {
        const name = card.querySelector(".goal-name").value.trim();
        const amount = Number(
            card.querySelector(".goal-amount").value
        );
        const years = Number(
            card.querySelector(".goal-years").value
        );

        if (!name) {
            throw new Error(
                `Please enter a name for financial goal ${index + 1}.`
            );
        }

        if (!Number.isFinite(amount) || amount < 0) {
            throw new Error(
                `Enter a valid amount for ${name}.`
            );
        }

        if (!Number.isInteger(years) || years < 1 || years > 40) {
            throw new Error(
                `Enter a valid timeline for ${name}.`
            );
        }

        return {
            name: name,
            amount: amount,
            years: years
        };
    });

    if (goals.length === 0) {
        throw new Error("Please add at least one financial goal.");
    }

    const primaryGoal = goals[0];

    return {
        age: Number(document.getElementById("age").value),
        income: Number(document.getElementById("income").value),
        expenses: Number(document.getElementById("expenses").value),
        debt: Number(document.getElementById("debt").value),
        dependents: dependents,
        dependent_ages: dependentAges,
        current_savings: Number(
            document.getElementById("currentSavings").value
        ),
        monthly_investment: Number(
            document.getElementById("monthlyInvestment").value
        ),

        // Legacy fields retained for existing backend calculations.
        goal_amount: primaryGoal.amount,
        goal_years: primaryGoal.years,

        // New field for multiple financial goals.
        goals: goals
    };
}




// ============================================================
// FORMAT INR
// ============================================================

function formatINR(value) {
    if (
        value === null ||
        value === undefined ||
        !Number.isFinite(Number(value))
    ) {
        return "—";
    }

    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0
    }).format(value);
}


// ============================================================
// UPDATE SLIDER LABELS
// ============================================================


function updateSliderLabels() {
    const age = document.getElementById("age");
    const ageValue = document.getElementById("ageValue");

    if (age && ageValue) {
        ageValue.textContent = age.value;
    }

    const dependents = document.getElementById("dependents");
    const dependentsValue = document.getElementById("dependentsValue");

    if (dependents && dependentsValue) {
        dependentsValue.textContent = dependents.value;
    }

    document.querySelectorAll(".goal-years").forEach(slider => {
        const years = Number(slider.value);

        const label =
            slider.id === "goalYears"
                ? document.getElementById("goalYearsValue")
                : slider
                    .closest("[data-goal]")
                    ?.querySelector(".goal-years-value");

        if (label) {
            label.textContent =
                `${years} ${years === 1 ? "year" : "years"}`;
        }
    });

    const dependentAges = document.getElementById("dependentAges");
    const dependentAgesGroup =
        document.getElementById("dependentAgesGroup");

    if (dependents && dependentAges && dependentAgesGroup) {
        const count = Number(dependents.value);

        dependentAges.disabled = count === 0;
        dependentAges.required = count > 0;
        dependentAgesGroup.style.display =
            count === 0 ? "none" : "";
        
        if (count === 0) {
            dependentAges.value = "";
        }
    }
}



// ============================================================
// SHOW INPUT SCREEN
// ============================================================

function showInputScreen() {
    inputScreen.classList.remove("hidden");
    dashboardScreen.classList.add("hidden");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// ============================================================
// SHOW DASHBOARD SCREEN
// ============================================================

function showDashboardScreen() {
    inputScreen.classList.add("hidden");
    dashboardScreen.classList.remove("hidden");

    loadMarketReport();
    loadInvestmentGrowthChart();

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// ============================================================
// LOAD HISTORICAL MARKET REPORT
// ============================================================

async function loadMarketReport() {
    const status = document.getElementById("marketReportStatus");
    const cards = document.getElementById("marketReportCards");
    const period = document.getElementById("marketReportPeriod");

    if (!status || !cards || !period) {
        return;
    }

    status.textContent = "Loading historical market data...";
    cards.replaceChildren();
    period.textContent = "—";

    try {
        const response = await fetch("/api/market-report");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Unable to load market data."
            );
        }

        if (!Array.isArray(data.reports) || data.reports.length === 0) {
            throw new Error("No market reports are available.");
        }

        data.reports.forEach(report => {
            const card = document.createElement("div");
            card.className = "kpi-card";

            const heading = document.createElement("span");
            heading.textContent = report.asset_name;

            const metrics = document.createElement("div");
            metrics.className = "market-metrics";

            const items = [
                ["Annualized Return", report.annualized_return, true],
                ["Annualized Volatility", report.annualized_volatility, true],
                ["Maximum Drawdown", report.maximum_drawdown, true],
                ["Sharpe Ratio", report.sharpe_ratio, false]
            ];

            items.forEach(([label, value, percentage]) => {
                const line = document.createElement("p");

                const valid =
                    value !== null &&
                    value !== undefined &&
                    Number.isFinite(Number(value));

                line.textContent = valid
                    ? `${label}: ${
                        percentage
                            ? `${(Number(value) * 100).toFixed(2)}%`
                            : Number(value).toFixed(2)
                    }`
                    : `${label}: —`;

                metrics.appendChild(line);
            });

            card.appendChild(heading);
            card.appendChild(metrics);
            cards.appendChild(card);
        });

        const startDate = data.reports
            .map(report => report.start_date)
            .sort()[0];

        const endDate = data.reports
            .map(report => report.end_date)
            .sort()
            .slice(-1)[0];

        period.textContent = `${startDate} to ${endDate}`;

        status.textContent =
            "Historical market data loaded successfully.";

    } catch (error) {
        console.error("Market report error:", error);

        status.textContent =
            "Unable to load market data. Please try again.";
    }
}


// ============================================================
// INVESTMENT GROWTH COMPARISON CHART
// ============================================================

async function loadInvestmentGrowthChart() {
    const container = document.getElementById("investmentGrowthChart");
    const status = document.getElementById("investmentGrowthStatus");

    if (!container || !status) {
        return;
    }

    status.textContent = "Loading investment growth data...";

    container.innerHTML = `
        <div class="chart-placeholder">
            Loading investment growth comparison...
        </div>
    `;

    try {
        const response = await fetch("/api/investment-growth");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Unable to load investment growth."
            );
        }

        if (!Array.isArray(data.reports) || data.reports.length === 0) {
            throw new Error("No investment growth data is available.");
        }

        const reports = data.reports.filter(report =>
            Array.isArray(report.dates) &&
            Array.isArray(report.values) &&
            report.dates.length === report.values.length &&
            report.values.length > 1 &&
            report.values.every(value =>
                Number.isFinite(Number(value))
            )
        );

        if (reports.length === 0) {
            throw new Error(
                "The historical investment data is invalid."
            );
        }

        // Align the asset series using their common dates.
        const dateSets = reports.map(
            report => new Set(report.dates)
        );

        const commonDates = reports[0].dates.filter(date =>
            dateSets.every(dateSet => dateSet.has(date))
        );

        if (commonDates.length < 2) {
            throw new Error(
                "There are not enough matching dates to compare the assets."
            );
        }

        const alignedReports = reports.map(report => {
            const valueByDate = new Map(
                report.dates.map((date, index) => [
                    date,
                    Number(report.values[index])
                ])
            );

            return {
                asset_name: report.asset_name,
                dates: commonDates,
                values: commonDates.map(
                    date => valueByDate.get(date)
                )
            };
        });

        const width = 900;
        const height = 360;

        const padding = {
            top: 30,
            right: 30,
            bottom: 50,
            left: 85
        };

        const allValues = alignedReports.flatMap(
            report => report.values
        );

        const minValue = Math.min(...allValues);
        const maxValue = Math.max(...allValues);
        const valueRange = maxValue - minValue || 1;

        const plotWidth =
            width - padding.left - padding.right;

        const plotHeight =
            height - padding.top - padding.bottom;

        const x = index =>
            padding.left +
            (index / (commonDates.length - 1)) * plotWidth;

        const y = value =>
            padding.top +
            ((maxValue - value) / valueRange) * plotHeight;

        const colors = ["#2563eb", "#b8860b"];

        // Draw horizontal grid lines and rupee labels.
        const gridLines = Array.from(
            { length: 5 },
            (_, index) => {
                const value =
                    minValue + (valueRange * index / 4);

                const position = y(value);

                return `
                    <line
                        x1="${padding.left}"
                        y1="${position}"
                        x2="${width - padding.right}"
                        y2="${position}"
                        stroke="#e5e7eb"
                        stroke-dasharray="4 4"
                    ></line>

                    <text
                        x="${padding.left - 12}"
                        y="${position + 5}"
                        text-anchor="end"
                        class="chart-label"
                    >${Math.round(value / 1000)}k</text>
                `;
            }
        ).join("");

        // Draw one line for each asset.
        const lines = alignedReports.map((report, index) => {
            const points = report.values.map(
                (value, pointIndex) =>
                    `${x(pointIndex)},${y(value)}`
            ).join(" ");

            return `
                <polyline
                    points="${points}"
                    fill="none"
                    stroke="${colors[index % colors.length]}"
                    stroke-width="3"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                ></polyline>
            `;
        }).join("");

        // Create the chart legend.
        const legend = document.createElement("div");

        legend.style.display = "flex";
        legend.style.flexWrap = "wrap";
        legend.style.gap = "12px";
        legend.style.marginBottom = "16px";

        alignedReports.forEach((report, index) => {
            const item = document.createElement("span");

            item.style.display = "inline-flex";
            item.style.alignItems = "center";
            item.style.gap = "7px";

            const swatch = document.createElement("span");

            swatch.style.display = "inline-block";
            swatch.style.width = "18px";
            swatch.style.height = "4px";

            swatch.style.backgroundColor =
                colors[index % colors.length];

            const label = document.createElement("span");
            label.textContent = report.asset_name;

            item.appendChild(swatch);
            item.appendChild(label);
            legend.appendChild(item);
        });

        const svgMarkup = `
            <svg
                viewBox="0 0 ${width} ${height}"
                class="wealth-svg"
                role="img"
                aria-label="Historical growth of a ten thousand rupee investment in Nifty 50 ETF and Gold ETF"
            >
                ${gridLines}

                <line
                    x1="${padding.left}"
                    y1="${padding.top}"
                    x2="${padding.left}"
                    y2="${height - padding.bottom}"
                    stroke="#9ca3af"
                ></line>

                <line
                    x1="${padding.left}"
                    y1="${height - padding.bottom}"
                    x2="${width - padding.right}"
                    y2="${height - padding.bottom}"
                    stroke="#9ca3af"
                ></line>

                ${lines}

                <text
                    x="${padding.left}"
                    y="${height - 15}"
                    class="chart-label"
                >${commonDates[0]}</text>

                <text
                    x="${width - padding.right}"
                    y="${height - 15}"
                    text-anchor="end"
                    class="chart-label"
                >${commonDates[commonDates.length - 1]}</text>
            </svg>
        `;

        container.replaceChildren(legend);

        const chartWrapper = document.createElement("div");
        chartWrapper.innerHTML = svgMarkup;

        container.appendChild(chartWrapper);

        status.textContent =
            "Historical comparison loaded. Values represent a one-time ₹10,000 investment, excluding taxes, fees, and dividends.";

    } catch (error) {
        console.error(
            "Investment growth chart error:",
            error
        );

        container.innerHTML = `
            <div class="chart-placeholder">
                Unable to display the investment growth chart.
            </div>
        `;

        status.textContent =
            "Unable to load investment growth data. Please try again.";
    }
}


// ============================================================
// WEALTH PROJECTION CHART
// ============================================================

function renderWealthChart(result) {
    const chartContainer = document.getElementById("wealthChart");

    if (!chartContainer) {
        return;
    }

    const years = Number(
        document.getElementById("goalYears").value
    );

    const startingSavings = Number(
        document.getElementById("currentSavings").value
    );

    const monthlyInvestment = Number(
        document.getElementById("monthlyInvestment").value
    );

    const annualReturn = Number(result.expected_return);

    if (
        !years ||
        years <= 0 ||
        !Number.isFinite(annualReturn)
    ) {
        chartContainer.innerHTML = `
            <div class="chart-placeholder">
                Unable to calculate projection.
            </div>
        `;

        return;
    }

    const monthlyReturn = annualReturn / 12;
    const data = [];

    for (let year = 0; year <= years; year++) {
        let value;

        if (monthlyReturn === 0) {
            value =
                startingSavings +
                monthlyInvestment * 12 * year;
        } else {
            const months = year * 12;

            const savingsGrowth =
                startingSavings *
                Math.pow(1 + monthlyReturn, months);

            const investmentGrowth =
                monthlyInvestment *
                (
                    (
                        Math.pow(1 + monthlyReturn, months) - 1
                    ) / monthlyReturn
                );

            value = savingsGrowth + investmentGrowth;
        }

        data.push({
            year,
            value
        });
    }

    const width = 900;
    const height = 360;
    const padding = 50;

    const values = data.map(item => item.value);

    const maxValue = Math.max(...values);
    const minValue = Math.min(...values);

    const valueRange = maxValue - minValue || 1;

    const points = data.map((item, index) => {
        const x =
            padding +
            (index / Math.max(data.length - 1, 1)) *
            (width - padding * 2);

        const y =
            height - padding -
            ((item.value - minValue) / valueRange) *
            (height - padding * 2);

        return {
            x,
            y,
            value: item.value,
            year: item.year
        };
    });

    const linePoints = points
        .map(point => `${point.x},${point.y}`)
        .join(" ");

    const areaPoints =
        `${padding},${height - padding} ` +
        linePoints +
        ` ${width - padding},${height - padding}`;

    const finalPoint = points[points.length - 1];

    chartContainer.innerHTML = `
        <svg
            viewBox="0 0 ${width} ${height}"
            class="wealth-svg"
            preserveAspectRatio="none"
            role="img"
            aria-label="Projected wealth growth over ${years} years"
        >
            <polygon
                points="${areaPoints}"
                class="chart-area"
            ></polygon>

            <polyline
                points="${linePoints}"
                class="chart-line"
                fill="none"
            ></polyline>

            <circle
                cx="${finalPoint.x}"
                cy="${finalPoint.y}"
                r="6"
                class="chart-point"
            ></circle>

            <text
                x="${padding}"
                y="${height - 15}"
                class="chart-label"
            >Year 0</text>

            <text
                x="${width - padding}"
                y="${height - 15}"
                text-anchor="end"
                class="chart-label"
            >Year ${years}</text>

            <text
                x="${finalPoint.x}"
                y="${finalPoint.y - 15}"
                text-anchor="middle"
                class="chart-value"
            >${formatINR(finalPoint.value)}</text>
        </svg>
    `;
}


// ============================================================
// RENDER PORTFOLIO
// ============================================================

function renderPortfolio(portfolio) {
    const portfolioContainer =
        document.getElementById("portfolio");

    if (!portfolioContainer) {
        return;
    }

    if (
        !portfolio ||
        Object.keys(portfolio).length === 0
    ) {
        portfolioContainer.innerHTML = `
            <div class="chart-placeholder">
                No portfolio recommendation available.
            </div>
        `;

        return;
    }

    let html = "";

    Object.entries(portfolio).forEach(([asset, weight]) => {
        const percentage = Number(weight) * 100;

        html += `
            <div class="portfolio-item">
                <div class="portfolio-header">
                    <span>${asset}</span>
                    <strong>${percentage.toFixed(1)}%</strong>
                </div>

                <div class="portfolio-bar">
                    <div
                        class="portfolio-fill"
                        style="width: ${percentage}%"
                    ></div>
                </div>
            </div>
        `;
    });

    portfolioContainer.innerHTML = html;
}


// ============================================================
// PORTFOLIO HEALTH CHECK
// ============================================================

function renderPortfolioHealth(diagnostics) {
    const status =
        document.getElementById("portfolioHealthStatus");

    const cards =
        document.getElementById("portfolioHealthCards");

    if (!status || !cards) {
        return;
    }

    cards.replaceChildren();

    if (
        !diagnostics ||
        typeof diagnostics !== "object"
    ) {
        status.textContent =
            "Portfolio diagnostics are unavailable for this assessment.";

        return;
    }

    const checks = [
        {
            label: "Portfolio risk",

            value: Number.isFinite(
                Number(diagnostics.risk_limit)
            )
                ? `${(
                    Number(diagnostics.risk_limit) * 100
                ).toFixed(2)}% maximum`
                : "—",

            passed: diagnostics.risk_within_limit
        },

        {
            label: "Weighted liquidity",

            value: Number.isFinite(
                Number(diagnostics.weighted_liquidity)
            )
                ? `${(
                    Number(diagnostics.weighted_liquidity) * 100
                ).toFixed(1)}%`
                : "—",

            passed: diagnostics.liquidity_constraint_satisfied
        },

        {
            label: "Weighted lock-in",

            value: Number.isFinite(
                Number(diagnostics.weighted_lock_in_years)
            )
                ? `${Number(
                    diagnostics.weighted_lock_in_years
                ).toFixed(2)} years`
                : "—",

            passed: diagnostics.lock_in_constraint_satisfied
        },

        {
            label: "Largest asset allocation",

            value: Number.isFinite(
                Number(diagnostics.maximum_asset_allocation)
            )
                ? `${(
                    Number(diagnostics.maximum_asset_allocation) * 100
                ).toFixed(1)}%`
                : "—",

            passed: diagnostics.asset_cap_satisfied
        },

        {
            label: "High-risk allocation",

            value: Number.isFinite(
                Number(diagnostics.high_risk_allocation)
            )
                ? `${(
                    Number(diagnostics.high_risk_allocation) * 100
                ).toFixed(1)}%`
                : "—",

            passed: diagnostics.high_risk_constraint_satisfied
        }
    ];

    const hasFailedCheck = checks.some(
        check => check.passed === false
    );

    const hasUnknownCheck = checks.some(
        check => typeof check.passed !== "boolean"
    );

    if (hasFailedCheck) {
        status.textContent =
            "One or more portfolio constraints were not satisfied.";
    } else if (hasUnknownCheck) {
        status.textContent =
            "Portfolio diagnostics loaded, but some checks are unavailable.";
    } else {
        status.textContent =
            "All checked portfolio constraints are satisfied.";
    }

    checks.forEach(check => {
        const card = document.createElement("div");
        card.className = "kpi-card";

        const heading = document.createElement("span");
        heading.textContent = check.label;

        const value = document.createElement("strong");
        value.textContent = check.value;

        const result = document.createElement("p");

        result.textContent =
            check.passed === true
                ? "Constraint satisfied"
                : check.passed === false
                    ? "Constraint not satisfied"
                    : "Check unavailable";

        card.append(heading, value, result);
        cards.appendChild(card);
    });
}


// ============================================================
// MONTE CARLO SIMULATION RESULTS
// ============================================================


function renderMonteCarlo(data) {
    const goalProbability =
        document.getElementById("monteCarloProbability");

    const pessimisticOutcome =
        document.getElementById("monteCarloPessimistic");

    const medianOutcome =
        document.getElementById("monteCarloMedian");

    const optimisticOutcome =
        document.getElementById("monteCarloOptimistic");

    const averageOutcome =
        document.getElementById("averageOutcome");

    const status =
        document.getElementById("monteCarloStatus");

    if (!goalProbability || !status) {
        return;
    }

    if (!data || typeof data !== "object") {
        goalProbability.textContent = "—";

        if (pessimisticOutcome) pessimisticOutcome.textContent = "—";
        if (medianOutcome) medianOutcome.textContent = "—";
        if (optimisticOutcome) optimisticOutcome.textContent = "—";
        if (averageOutcome) averageOutcome.textContent = "—";

        status.textContent =
            "Monte Carlo results are unavailable.";

        return;
    }

    const probability = Number(data.goal_probability);

    goalProbability.textContent =
        Number.isFinite(probability) &&
        probability >= 0 &&
        probability <= 1
            ? `${(probability * 100).toFixed(1)}%`
            : "—";

    if (pessimisticOutcome) {
        pessimisticOutcome.textContent =
            formatINR(data.pessimistic_outcome);
    }

    if (medianOutcome) {
        medianOutcome.textContent =
            formatINR(data.median_outcome);
    }

    if (optimisticOutcome) {
        optimisticOutcome.textContent =
            formatINR(data.optimistic_outcome);
    }

    if (averageOutcome) {
        averageOutcome.textContent =
            formatINR(data.average_outcome);
    }

    const simulations = Number(data.simulations);
    const years = Number(data.years);

    status.textContent =
        `${Number.isFinite(simulations) ? simulations : "Multiple"} simulated scenarios over ${Number.isFinite(years) ? years : "the selected"} years. These are estimates, not guarantees.`;
}


// ============================================================
// UPDATE DASHBOARD
// ============================================================

function updateDashboard(result) {
    const riskScore = document.getElementById("riskScore");
    const riskProfile = document.getElementById("riskProfile");

    const expectedReturn =
        document.getElementById("expectedReturn");

    const portfolioRisk =
        document.getElementById("portfolioRisk");

    const projectedValue =
        document.getElementById("projectedValue");

    const goalStatus =
        document.getElementById("goalStatus");

    if (riskScore) {
        riskScore.textContent = result.risk_score;
    }

    if (riskProfile) {
        riskProfile.textContent = result.risk_profile;
    }

    if (expectedReturn) {
        expectedReturn.textContent =
            `${(
                Number(result.expected_return) * 100
            ).toFixed(2)}%`;
    }

    if (portfolioRisk) {
        portfolioRisk.textContent =
            `${(
                Number(result.portfolio_volatility) * 100
            ).toFixed(2)}%`;
    }

    if (projectedValue) {
        projectedValue.textContent =
            formatINR(result.projected_value);
    }

    if (goalStatus) {
        goalStatus.textContent = result.goal_status;
    }

    renderPortfolio(result.portfolio);
    renderWealthChart(result);
    renderPortfolioHealth(result.portfolio_diagnostics);
    renderMonteCarlo(result.monte_carlo);
    renderGoalRecommendations(result);
}


// ============================================================
// CALCULATE FINANCIAL ASSESSMENT
// ============================================================


async function calculateAssessment() {
    let userData;

    try {
        userData = getUserData();
    } catch (error) {
        alert(error.message);
        return false;
    }


    if (
        userData.income < 0 ||
        userData.expenses < 0 ||
        userData.debt < 0 ||
        userData.current_savings < 0 ||
        userData.monthly_investment < 0 ||
        userData.goal_amount < 0
    ) {
        alert("Please enter valid financial values.");
        return false;
    }

    generatePlanButton.disabled = true;

    generatePlanButton.textContent =
        "Generating Your Plan...";

    try {
        const response = await fetch("/api/assess", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(userData)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.error ||
                "Unable to generate financial plan."
            );
        }

        updateDashboard(result);
        showDashboardScreen();

        return true;

    } catch (error) {
        console.error("Assessment error:", error);

        alert(
            `Unable to generate your financial plan.\n\n${error.message}`
        );

        return false;

    } finally {
        generatePlanButton.disabled = false;

        generatePlanButton.textContent =
            "Generate My Financial Plan →";
    }
}


// ============================================================
// GENERATE BUTTON
// ============================================================

if (generatePlanButton) {
    generatePlanButton.addEventListener(
        "click",
        calculateAssessment
    );
}


// ============================================================
// BACK / EDIT INPUTS BUTTON
// ============================================================

if (backButton) {
    backButton.addEventListener(
        "click",
        showInputScreen
    );
}


// ============================================================
// SLIDER EVENTS
// ============================================================

const ageSlider = document.getElementById("age");

if (ageSlider) {
    ageSlider.addEventListener(
        "input",
        updateSliderLabels
    );
}

const dependentsSlider =
    document.getElementById("dependents");

if (dependentsSlider) {
    dependentsSlider.addEventListener(
        "input",
        updateSliderLabels
    );
}

const goalYearsSlider =
    document.getElementById("goalYears");

if (goalYearsSlider) {
    goalYearsSlider.addEventListener(
        "input",
        updateSliderLabels
    );
}


// ============================================================
// INITIALIZE
// ============================================================

// Do not calculate the financial assessment on page load.
// The assessment should only happen after the user clicks
// "Generate My Financial Plan".

updateSliderLabels();
showInputScreen();

document.addEventListener("input", function (event) {
    if (event.target.matches(".goal-years")) {
        updateSliderLabels();
    }
});

const goalsContainer = document.getElementById("goalsContainer");
const addGoalButton = document.getElementById("addGoalButton");

if (goalsContainer && addGoalButton) {
    addGoalButton.addEventListener("click", function () {
        const goalCount =
            goalsContainer.querySelectorAll("[data-goal]").length;

        if (goalCount >= 10) {
            alert("You can add a maximum of 10 financial goals.");
            return;
        }

        const goalCard = document.createElement("div");
        goalCard.className = "goal-input-card";
        goalCard.setAttribute("data-goal", "");

        goalCard.innerHTML = `
            <div class="input-group">
                <label>Goal Name</label>
                <input
                    type="text"
                    class="goal-name"
                    placeholder="e.g. Car, Education, Retirement"
                    required
                >
            </div>

            <div class="input-group">
                <label>Goal Amount (₹)</label>
                <input
                    type="number"
                    class="goal-amount"
                    value="1000000"
                    min="0"
                    step="1000"
                    required
                >
            </div>

            <div class="input-group">
                <label>Time Horizon <span class="goal-years-value">5 years</span></label>
                <input
                    type="range"
                    class="goal-years"
                    min="1"
                    max="40"
                    value="5"
                >
            </div>

            <button type="button" class="remove-goal-button">
                Remove Goal
            </button>
        `;

        goalsContainer.appendChild(goalCard);

        const yearsSlider = goalCard.querySelector(".goal-years");
        const yearsLabel = goalCard.querySelector(".goal-years-value");

        yearsSlider.addEventListener("input", function () {
            const years = Number(yearsSlider.value);
            yearsLabel.textContent =
                `${years} ${years === 1 ? "year" : "years"}`;
        });

        goalCard
            .querySelector(".remove-goal-button")
            .addEventListener("click", function () {
                goalCard.remove();
            });
    });
}

function renderGoalRecommendations(result) {
    const goalsContainer = document.getElementById("goalsResults");
    const allocationContainer = document.getElementById("goalAllocationSummary");

    if (!goalsContainer || !allocationContainer) return;

    const goals = Array.isArray(result.goals) ? result.goals : [];
    const allocation = result.goal_allocation || {};

    const formatMoney = value => formatINR(Number(value) || 0);

    allocationContainer.innerHTML = `
        <div class="allocation-summary-card">
            <span class="allocation-label">Monthly investment budget</span>
            <strong>${formatMoney(allocation.monthly_budget)}</strong>
        </div>
        <div class="allocation-summary-card">
            <span class="allocation-label">Allocated to goals</span>
            <strong>${formatMoney(allocation.total_allocated)}</strong>
        </div>
        <div class="allocation-summary-card">
            <span class="allocation-label">Remaining each month</span>
            <strong>${formatMoney(allocation.remaining_budget)}</strong>
        </div>
        <p class="allocation-explanation">
            Your monthly investment is shared across your goals.
            These projections use an assumed return and are not guaranteed.
        </p>
    `;

    if (goals.length === 0) {
        goalsContainer.innerHTML = `
            <p>No additional goals were provided. Add goals to receive
            individual projections and recommendations.</p>
        `;
        return;
    }

    goalsContainer.innerHTML = goals.map((goal, index) => {
        const probability = Number(goal.monte_carlo?.goal_probability);
        const probabilityText = Number.isFinite(probability)
            ? `${(probability * 100).toFixed(0)}%`
            : "Not available";

        const status = goal.status || "Needs review";
        const shortfall = Number(goal.shortfall) || 0;
        const contributionGap = Number(goal.monthly_contribution_gap) || 0;

        const investmentPlan = goal.investment_recommendation || {};
        const suggestedMix = Array.isArray(investmentPlan.suggested_mix)
            ? investmentPlan.suggested_mix
            : [];

        const investmentSection = suggestedMix.length
            ? `
                <div class="investment-plan">
                    <h5>Suggested investments to consider</h5>
                    <p class="investment-explanation">
                        ${escapeGoalText(investmentPlan.explanation || "These suggestions use your goal timeline and risk profile.")}
                    </p>

                    <div class="investment-list">
                        ${suggestedMix.map(asset => `
                            <div class="investment-item">
                                <div class="investment-item-heading">
                                    <strong>${escapeGoalText(asset.asset_name)}</strong>
                                    <span>${Number(asset.allocation_percent).toFixed(1)}%</span>
                                </div>
                                <p>${escapeGoalText(asset.category || "Investment asset")}</p>
                                <div class="investment-item-details">
                                    <span>Monthly amount</span>
                                    <strong>${formatMoney(asset.monthly_amount)}</strong>
                                </div>
                                <div class="investment-item-details">
                                    <span>Assumed annual return</span>
                                    <strong>${(Number(asset.assumed_annual_return) * 100).toFixed(1)}%</strong>
                                </div>
                            </div>
                        `).join("")}
                    </div>

                    ${Array.isArray(investmentPlan.warnings) && investmentPlan.warnings.length
                        ? `<ul class="investment-warnings">
                            ${investmentPlan.warnings.map(warning =>
                                `<li>${escapeGoalText(warning)}</li>`
                            ).join("")}
                        </ul>`
                        : ""}
                </div>
            `
            : `
                <div class="investment-plan">
                    <h5>Investment suggestions</h5>
                    <p>${escapeGoalText(
                        investmentPlan.explanation ||
                        "No suitable assets were found for this goal under the current rules. Review the goal timeline and risk profile."
                    )}</p>
                </div>
            `;


        return `
            <article class="individual-goal-card">
                <div class="goal-card-header">
                    <div>
                        <span class="goal-number">GOAL ${index + 1}</span>
                        <h4>${escapeGoalText(goal.name)}</h4>
                    </div>
                    <span class="goal-status">${escapeGoalText(status)}</span>
                </div>

                <div class="goal-target-row">
                    <div>
                        <span>Target amount</span>
                        <strong>${formatMoney(goal.goal_amount)}</strong>
                    </div>
                    <div>
                        <span>Time available</span>
                        <strong>${Number(goal.goal_years)} years</strong>
                    </div>
                </div>

                <div class="goal-projection">
                    <span>Estimated value at your current allocation</span>
                    <strong>${formatMoney(goal.projected_value)}</strong>
                    <p>
                        ${shortfall > 0
                            ? `Estimated shortfall: ${formatMoney(shortfall)}`
                            : `Estimated amount above target: ${formatMoney(goal.surplus)}`}
                    </p>
                </div>

                <div class="goal-contribution-grid">
                    <div>
                        <span>Monthly allocation</span>
                        <strong>${formatMoney(goal.allocated_monthly_investment)}</strong>
                    </div>
                    <div>
                        <span>Estimated amount needed monthly</span>
                        <strong>${formatMoney(goal.required_monthly_investment)}</strong>
                    </div>
                    <div>
                        <span>Monthly contribution gap</span>
                        <strong>${formatMoney(contributionGap)}</strong>
                    </div>
                </div>

                <div class="goal-recommendation">
                    <h5>What this means for you</h5>
                    <p>${escapeGoalText(goal.recommendation || "Review this goal's timeline and monthly contribution.")}</p>
                </div>
                ${investmentSection}
                
                

                <details class="goal-details">
                    <summary>Understand the estimate</summary>
                    <p>
                        The projected value is based on the assumed annual return.
                        Actual investment outcomes can be higher or lower.
                    </p>
                    <p>
                        Estimated chance of reaching the target in the simulation:
                        <strong>${probabilityText}</strong>.
                        This is a model-based estimate, not a guarantee.
                    </p>
                </details>
            </article>
        `;
    }).join("");
}

function escapeGoalText(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}
