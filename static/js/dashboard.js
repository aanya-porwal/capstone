(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const CATEGORY_COLOURS = {
        "Equity": "var(--c-equity)",
        "Debt": "var(--c-debt)",
        "Gold": "var(--c-gold)",
        "Tax Advantaged": "var(--c-tax)",
    };

    function esc(value) {
        const div = document.createElement("div");
        div.textContent = String(value);
        return div.innerHTML;
    }
    function inr(n) { return "₹" + Math.round(n).toLocaleString("en-IN"); }
    function inrShort(n) {
        const abs = Math.abs(n);
        if (abs >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " crore";
        if (abs >= 1e5) return "₹" + (n / 1e5).toFixed(1) + " lakh";
        return inr(n);
    }

    function addGoal(name, amount, years) {
        const row = document.createElement("div");
        row.className = "goal-row";
        row.innerHTML = `
            <div class="field"><label>What are you saving for?</label>
                <input type="text" class="g-name" maxlength="40" placeholder="e.g. House, Car, Emergency fund"></div>
            <div class="field"><label>How much do you need? (₹)</label>
                <input type="number" class="g-amount" min="1" step="10000"></div>
            <div class="field"><label>In how many years?</label>
                <input type="number" class="g-years" min="1" max="50" step="1"></div>
            <button type="button" class="remove" aria-label="Remove goal" title="Remove goal">×</button>`;
        row.querySelector(".g-name").value = name || "";
        row.querySelector(".g-amount").value = amount || "";
        row.querySelector(".g-years").value = years || "";
        row.querySelector(".remove").addEventListener("click", () => {
            if (document.querySelectorAll(".goal-row").length > 1) row.remove();
        });
        $("goalList").appendChild(row);
    }

    function readGoals() {
        return Array.from(document.querySelectorAll(".goal-row")).map((row) => ({
            name: row.querySelector(".g-name").value.trim(),
            amount: Number(row.querySelector(".g-amount").value),
            years: Number(row.querySelector(".g-years").value),
        }));
    }

    function currentMode() { return document.querySelector('input[name="mode"]:checked').value; }

    function syncMode() {
        $("budgetLabel").textContent = currentMode() === "budget"
            ? "How much can you invest every month?"
            : "How much can you comfortably invest every month? (optional)";
    }
    function syncRisk() { $("riskHelper").hidden = $("riskChoice").value !== "auto"; }
    function showError(message) {
        const box = $("formError");
        box.textContent = message || "";
        box.hidden = !message;
    }

    function renderSummary(plan) {
        const s = plan.summary;
        let big, sub, flag = "";

        if (plan.mode === "budget") {
            big = `Investing ${inr(s.monthly_allocated)} a month could grow to about ${inrShort(s.projected_value)}.`;
            sub = `You would put in ${inrShort(s.total_invested)} and could earn about ${inrShort(s.projected_profit)} in profit.`;
            if (!s.affordable) {
                flag = `To fully fund every goal you would need about ${inr(s.extra_needed_per_month)} more each month. Goals with the furthest deadlines are the ones affected.`;
            } else if (s.monthly_left_over > 0) {
                flag = `Good news: all goals are covered and you would still have ${inr(s.monthly_left_over)} a month left over.`;
            }
        } else {
            big = `To reach your goals, invest about ${inr(s.monthly_needed)} a month.`;
            sub = `You would put in ${inrShort(s.total_invested)} and could earn about ${inrShort(s.projected_profit)} in profit.`;
            if (s.monthly_budget > 0) {
                flag = s.affordable
                    ? `That fits within the ${inr(s.monthly_budget)} a month you said you can invest.`
                    : `That is ${inr(s.extra_needed_per_month)} more than the ${inr(s.monthly_budget)} a month you said you can invest. You could extend the deadlines or lower a target (see each goal below).`;
            }
        }

        $("summary").innerHTML = `
            <h2>Your plan at a glance</h2>
            <div class="big">${esc(big)}</div>
            <div class="sub">${esc(sub)}</div>
            <div class="stats">
                <div class="stat"><span>Monthly investment</span><b>${esc(inr(plan.mode === "budget" ? s.monthly_allocated : s.monthly_needed))}</b></div>
                <div class="stat"><span>Goals on track</span><b>${s.goals_on_track} of ${s.goals_total}</b></div>
                <div class="stat"><span>Risk style</span><b>${esc(plan.risk_label)}</b></div>
            </div>
            ${flag ? `<div class="flag">${esc(flag)}</div>` : ""}`;
    }

    function statusLabel(status) {
        return { on_track: "On track", almost: "Almost there", short: "Falls short" }[status];
    }

    function renderAsset(m) {
        const colour = CATEGORY_COLOURS[m.category] || "var(--muted)";
        const lock = m.lock_in_years > 0
            ? `<span class="lock">${m.lock_in_years}-year lock-in</span>` : "";
        return `
            <div class="asset">
                <div class="asset-top">
                    <div class="asset-name"><i class="dot" style="background:${colour}"></i>
                        <div>${esc(m.asset_name)}${lock}<small>${esc(m.what_it_is)}</small></div></div>
                    <div class="cell"><span>Put in (${m.percent}%)</span><b>${esc(inr(m.monthly_amount))}/month</b>${m.starting_amount > 0 ? `<span>+ ${esc(inr(m.starting_amount))} to start</span>` : ""}</div>
                    <div class="cell"><span>Could grow to</span><b>${esc(inrShort(m.projected_value))}</b></div>
                    <div class="cell profit"><span>Profit</span><b>${esc(inrShort(m.profit))}</b><span>at ${(m.assumed_annual_return * 100).toFixed(1)}% a year</span></div>
                </div>
                <p class="why"><em>Why this?</em> ${esc(m.why)}</p>
            </div>`;
    }

    function renderGoal(g) {
        const bar = g.mix.map((m) =>
            `<i style="width:${m.percent}%;background:${CATEGORY_COLOURS[m.category] || "var(--muted)"}" title="${esc(m.asset_name)} ${m.percent}%"></i>`
        ).join("");

        const sc = g.scenarios;
        const scen = (key, label, mid) => `
            <div class="scen${mid ? " mid" : ""}">
                <span>${label}</span><b>${esc(inrShort(sc[key].projected_value))}</b>
                <small>Profit ${esc(inrShort(sc[key].profit))}</small><br>
                <small class="${sc[key].reaches_goal ? "ok" : "no"}">${sc[key].reaches_goal ? "Reaches your goal" : "Misses your goal"}</small>
            </div>`;

        const advice = g.advice.map((a) => `<li>${esc(a)}</li>`).join("");
        const startNote = g.starting_amount > 0
            ? ` and ${esc(inr(g.starting_amount))} you already have` : "";

        return `
            <article class="card">
                <div class="goal-head">
                    <div><h3>${esc(g.name)}</h3>
                        <p>Target ${esc(inrShort(g.target_amount))} in ${g.years} year${g.years === 1 ? "" : "s"}</p></div>
                    <span class="pill ${g.status}">${statusLabel(g.status)}</span>
                </div>

                <div class="numbers">
                    <div class="num"><span>Invest every month</span><b>${esc(inr(g.monthly_amount))}</b></div>
                    <div class="num"><span>Total you put in</span><b>${esc(inrShort(g.total_invested))}</b></div>
                    <div class="num"><span>Could grow to</span><b>${esc(inrShort(g.projected_value))}</b></div>
                    <div class="num profit"><span>Profit you could earn</span><b>${esc(inrShort(g.profit))}</b></div>
                </div>

                <h4>Where to put your ${esc(inr(g.monthly_amount))} a month${startNote}</h4>
                <div class="bar" role="img" aria-label="Split of your money">${bar}</div>
                ${g.mix.map(renderAsset).join("")}

                <h4>What could happen by year ${g.years}?</h4>
                <div class="scenarios">
                    ${scen("conservative", "If markets do worse", false)}
                    ${scen("expected", "If markets do as assumed", true)}
                    ${scen("optimistic", "If markets do better", false)}
                </div>

                <h4>Chance of reaching your goal</h4>
                <div class="chance">
                    <div class="meter"><i style="width:${g.chance_of_reaching_goal}%"></i></div>
                    <b>${g.chance_of_reaching_goal}%</b>
                </div>
                <p class="hint">We simulated thousands of possible market paths. This many reached your target. It is an estimate, not a promise.</p>

                <h4>${g.status === "on_track" ? "What to do" : "How to close the gap"}</h4>
                <ul class="advice">${advice}</ul>
            </article>`;
    }

    function renderSources(sources) {
        if (!sources.length) return "";
        const rows = sources.map((s) => {
            const live = s.source.startsWith("live");
            const flag = s.source.includes("stale") || s.source.includes("unverified") || s.source.includes("older");
            const label = live ? "Live data" : s.source.startsWith("manual") ? "Official rate" : "Assumption";
            return `<li><strong>${esc(s.asset_name)}</strong>: ${(s.annual_return * 100).toFixed(1)}% a year, ${esc(label)}` +
                `${s.as_of ? ` (as of ${esc(s.as_of)})` : ""}${flag ? " - needs a refresh" : ""}. ${esc(s.note)}</li>`;
        }).join("");
        return `<p style="margin-top:12px"><strong>Where the return numbers come from</strong></p><ul>${rows}</ul>`;
    }

    function renderPlan(plan) {
        renderSummary(plan);
        $("goalCards").innerHTML = plan.goals.map(renderGoal).join("");
        $("assumptions").innerHTML =
            `<strong>How we worked this out</strong><ul><li>${esc(plan.method)}</li>` +
            plan.assumptions.map((a) => `<li>${esc(a)}</li>`).join("") + "</ul>" +
            renderSources(plan.data_sources || []);
        $("results").hidden = false;
        $("results").scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function submit() {
        showError("");
        const goals = readGoals();

        for (const g of goals) {
            if (!g.name) return showError("Give each goal a name.");
            if (!(g.amount > 0)) return showError(`Enter how much you need for "${g.name}".`);
            if (!(g.years >= 1 && g.years <= 50) || !Number.isInteger(g.years)) {
                return showError(`Enter a whole number of years (1 to 50) for "${g.name}".`);
            }
        }

        const mode = currentMode();
        const budget = Number($("monthlyBudget").value) || 0;
        if (mode === "budget" && budget <= 0) {
            return showError("Enter how much you can invest every month.");
        }

        const payload = {
            mode,
            goals,
            monthly_budget: budget,
            current_savings: Number($("currentSavings").value) || 0,
            risk_profile: $("riskChoice").value,
        };
        if (payload.risk_profile === "auto") {
            payload.age = Number($("age").value);
            payload.income = Number($("income").value);
            payload.expenses = Number($("expenses").value);
            payload.debt = Number($("debt").value);
            payload.dependents = Number($("dependents").value);
        }

        const btn = $("planBtn");
        btn.disabled = true;
        btn.textContent = "Working it out…";
        try {
            const res = await fetch("/api/plan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Something went wrong.");
            renderPlan(data);
        } catch (err) {
            showError(err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Show my plan";
        }
    }

    document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener("change", syncMode));
    $("riskChoice").addEventListener("change", syncRisk);
    $("addGoal").addEventListener("click", () => {
        if (document.querySelectorAll(".goal-row").length < 10) addGoal();
    });
    $("planBtn").addEventListener("click", submit);

    addGoal("House", 5000000, 10);
    syncMode();
    syncRisk();
})();