"""Shared planning engine for Wealth AI (budget-first and goal-first)."""

import numpy as np

from engine.goal_recommender import load_assets
from engine.goals import monthly_rate
from engine.live_data import describe_sources
from engine.monte_carlo import run_monte_carlo
from engine.risk import calculate_risk_score, get_risk_profile

RISK_PROFILES = ("Low", "Moderate", "Moderately High", "High")

RISK_LABELS = {
    "Low": "Play it safe",
    "Moderate": "Balanced",
    "Moderately High": "Growth-leaning",
    "High": "Aggressive",
}


# Max share of a goal's money in equity, by horizon. Short goals get none.
def _horizon_equity_cap(years):
    if years < 3:
        return 0.0
    if years < 5:
        return 0.20
    if years < 8:
        return 0.40
    if years < 12:
        return 0.60
    return 0.80


_RISK_SCALE = {"Low": 0.35, "Moderate": 0.65, "Moderately High": 0.85, "High": 1.0}

# Plans are sized with returns 2 points below assumed. Hitting a target
# exactly at the expected return is only a ~50% chance.
PLANNING_CUSHION = -0.02

SCENARIOS = {"conservative": -0.03, "expected": 0.0, "optimistic": 0.02}

ASSET_INFO = {
    "Nifty 50 ETF": {
        "plain": "A basket of India's 50 biggest listed companies you buy like a single share.",
        "why_role": "growth",
    },
    "Large Cap Mutual Fund": {
        "plain": "A fund manager invests your money in large, established companies.",
        "why_role": "growth",
    },
    "ELSS": {
        "plain": "A tax-saving equity mutual fund. Each instalment is locked for 3 years.",
        "why_role": "growth",
        "lock_per_instalment": True,
    },
    "Fixed Deposit": {
        "plain": "You lend money to a bank and get a fixed interest rate.",
        "why_role": "safety",
    },
    "Government Bond": {
        "plain": "You lend money to the government and earn interest.",
        "why_role": "safety",
    },
    "PPF": {
        "plain": "A government savings scheme with tax benefits. Money is locked for 15 years.",
        "why_role": "safety",
    },
    "Gold ETF": {
        "plain": "Gold you hold digitally. Its price can move up or down, but it often behaves differently from shares.",
        "why_role": "diversify",
    },
    "NPS": {
        "plain": "A government-backed retirement account. Rules limit when you can withdraw.",
        "why_role": "retirement",
    },
}


def _role(asset_name, row):
    info = ASSET_INFO.get(asset_name)
    if info:
        return info["why_role"]
    category = str(row["category"])
    if category == "Equity":
        return "growth"
    if category == "Gold":
        return "diversify"
    return "safety"


def _correlation(role_a, role_b, same_asset):
    if same_asset:
        return 1.0
    if role_a == role_b:
        return 0.85 if role_a == "growth" else 0.5
    pair = {role_a, role_b}
    if pair == {"growth", "diversify"}:
        return 0.05
    if "growth" in pair:
        return 0.15
    return 0.05


def _round_pct(weights, step=5):
    pct = {k: v * 100 for k, v in weights.items()}
    rounded = {k: int(round(v / step) * step) for k, v in pct.items()}
    diff = 100 - sum(rounded.values())
    if rounded:
        biggest = max(rounded, key=lambda k: pct[k])
        rounded[biggest] += diff
    return {k: v for k, v in rounded.items() if v > 0}


def build_mix(goal_name, years, risk_profile, assets):
    """Pick assets and weights for one goal.

    1. Only assets whose lock-in fits inside the goal horizon.
    2. Equity share = horizon cap x risk comfort (none under 3 years).
    3. Gold: 10% diversifier for goals of 5+ years (not for "Low").
    4. The rest goes to safe assets; PPF capped at 30%.
    5. NPS only for retirement goals of 10+ years.
    """
    name_lower = goal_name.lower()
    is_retirement = "retire" in name_lower or "pension" in name_lower

    rows = {}
    for _, row in assets.iterrows():
        asset = str(row["asset_name"])
        info = ASSET_INFO.get(asset, {})
        lock = float(row["lock_in"])
        needed = lock * 2 if info.get("lock_per_instalment") else lock
        if needed > years:
            continue
        if years < 3 and float(row["liquidity"]) < 0.7:
            continue
        role = _role(asset, row)
        if role == "retirement" and not (is_retirement and years >= 10):
            continue
        rows[asset] = (row, role)

    growth = [a for a, (_, r) in rows.items() if r == "growth"]
    safety = [a for a, (_, r) in rows.items() if r == "safety"]
    diversify = [a for a, (_, r) in rows.items() if r == "diversify"]
    retirement = [a for a, (_, r) in rows.items() if r == "retirement"]

    equity_share = _horizon_equity_cap(years) * _RISK_SCALE[risk_profile]
    if not growth:
        equity_share = 0.0
    gold_share = 0.10 if (years >= 5 and risk_profile != "Low" and diversify) else 0.0
    nps_share = 0.20 if retirement else 0.0
    safety_share = 1.0 - equity_share - gold_share - nps_share
    if not safety:
        equity_share += safety_share if growth else 0.0
        safety_share = 0.0

    weights = {}
    for group, share in (
        (growth, equity_share), (diversify, gold_share),
        (retirement, nps_share),
    ):
        for a in group:
            weights[a] = weights.get(a, 0.0) + share / len(group) if group else 0

    if safety:
        per = safety_share / len(safety)
        for a in safety:
            weights[a] = per
        ppf_cap = 0.30
        capped = {a: w for a, w in weights.items() if a == "PPF" and w > ppf_cap}
        for a in capped:
            excess = weights[a] - ppf_cap
            weights[a] = ppf_cap
            others = [x for x in safety if x != a]
            if others:
                for x in others:
                    weights[x] += excess / len(others)

    total = sum(weights.values())
    weights = {a: w / total for a, w in weights.items()} if total else {}
    pct = _round_pct(weights)
    return {a: p / 100 for a, p in pct.items()}, rows


def _blend_factors(weights, rows, months, delta=0.0):
    """Growth of 1 rupee lump sum and of 1 rupee/month (month-end), blended."""
    lump = 0.0
    stream = 0.0
    for asset, w in weights.items():
        annual = max(float(rows[asset][0]["expected_return"]) + delta, 0.0)
        m = monthly_rate(annual)
        growth = (1 + m) ** months
        lump += w * growth
        stream += w * (months if m == 0 else (growth - 1) / m)
    return lump, stream


def _portfolio_stats(weights, rows):
    names = list(weights)
    w = np.array([weights[a] for a in names])
    ret = float(sum(weights[a] * float(rows[a][0]["expected_return"]) for a in names))
    vols = np.array([float(rows[a][0]["volatility"]) for a in names])
    corr = np.eye(len(names))
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            corr[i, j] = _correlation(rows[a][1], rows[b][1], i == j)
    var = float(w @ (np.outer(vols, vols) * corr) @ w)
    return ret, float(np.sqrt(max(var, 0.0)))


def _years_needed(target, savings, monthly, weights, rows, limit_years=60):
    if monthly <= 0 and savings <= 0:
        return None
    for y in range(1, limit_years + 1):
        lump, stream = _blend_factors(weights, rows, y * 12, PLANNING_CUSHION)
        if savings * lump + monthly * stream >= target:
            return y
    return None


def _why_text(asset, role, years, risk_profile, weight_pct):
    label = RISK_LABELS[risk_profile].lower()
    if role == "growth":
        return (
            f"Over {years} years, shares have time to recover from bad patches, so "
            f"{weight_pct}% goes here for higher growth. Your '{label}' comfort level "
            "limits how much."
        )
    if role == "safety":
        if years < 3:
            return (
                f"You need this money in {years} year(s), so most of it goes to "
                "something steady that won't drop right before you need it."
            )
        return (
            "This is the steady part of your plan. It grows more slowly but its "
            "value does not swing much, which protects what you have built."
        )
    if role == "diversify":
        return (
            "A small slice that often moves differently from shares, which can "
            "soften the ups and downs of the whole plan."
        )
    return "Included because this is a long-term retirement goal."


def _status(projected, target):
    if projected >= target * 0.999:
        return "on_track"
    if projected >= target * 0.9:
        return "almost"
    return "short"


def resolve_risk_profile(data):
    """Use the user's chosen risk level, or work it out from their finances."""
    chosen = data.get("risk_profile")
    if chosen in RISK_PROFILES:
        return chosen
    score = calculate_risk_score(
        int(data["age"]), float(data["income"]), float(data["expenses"]),
        float(data["debt"]), int(data["dependents"]),
    )
    return get_risk_profile(score)


def build_plan(
    mode, goals, monthly_budget, current_savings, risk_profile,
    assets=None, simulations=2000, seed=None,
):
    if mode not in {"budget", "goal"}:
        raise ValueError("Mode must be 'budget' or 'goal'.")
    if risk_profile not in RISK_PROFILES:
        raise ValueError("Unknown risk profile.")
    if not isinstance(goals, list) or not goals:
        raise ValueError("Add at least one goal.")
    if len(goals) > 10:
        raise ValueError("A maximum of 10 goals is allowed.")
    if monthly_budget < 0 or current_savings < 0:
        raise ValueError("Budget and savings cannot be negative.")
    if mode == "budget" and monthly_budget <= 0:
        raise ValueError("Enter how much you can invest each month.")

    assets = load_assets() if assets is None else assets

    prepared = []
    for g in goals:
        name = str(g.get("name", "")).strip()
        amount = float(g.get("amount", 0))
        years = int(g.get("years", 0))
        if not name:
            raise ValueError("Every goal needs a name.")
        if amount <= 0:
            raise ValueError(f"'{name}': the target amount must be above zero.")
        if not 1 <= years <= 50:
            raise ValueError(f"'{name}': years must be between 1 and 50.")
        weights, rows = build_mix(name, years, risk_profile, assets)
        if not weights:
            raise ValueError(f"No supported investment fits the goal '{name}'.")
        ret, vol = _portfolio_stats(weights, rows)
        prepared.append({
            "name": name, "amount": amount, "years": years,
            "weights": weights, "rows": rows, "ret": ret, "vol": vol,
        })

    # Existing savings go to the nearest deadlines first.
    order = sorted(range(len(prepared)), key=lambda i: prepared[i]["years"])
    savings_left = float(current_savings)
    for i in order:
        g = prepared[i]
        lump, _ = _blend_factors(
            g["weights"], g["rows"], g["years"] * 12, PLANNING_CUSHION
        )
        need_today = g["amount"] / lump
        g["savings"] = min(savings_left, need_today)
        savings_left -= g["savings"]

    for g in prepared:
        months = g["years"] * 12
        lump, stream = _blend_factors(
            g["weights"], g["rows"], months, PLANNING_CUSHION
        )
        g["required"] = max(0.0, (g["amount"] - g["savings"] * lump) / stream)

    if mode == "goal":
        for g in prepared:
            g["monthly"] = g["required"]
    else:
        budget_left = float(monthly_budget)
        for i in order:
            g = prepared[i]
            g["monthly"] = min(g["required"], budget_left)
            budget_left -= g["monthly"]

    goal_results = []
    for g in prepared:
        months = g["years"] * 12
        mix_out = []
        total_projected = 0.0
        total_invested = g["savings"] + g["monthly"] * months
        for asset, w in sorted(g["weights"].items(), key=lambda kv: -kv[1]):
            row, role = g["rows"][asset]
            a_monthly = g["monthly"] * w
            a_savings = g["savings"] * w
            lump_a, stream_a = _blend_factors({asset: 1.0}, g["rows"], months)
            a_projected = a_savings * lump_a + a_monthly * stream_a
            a_invested = a_savings + a_monthly * months
            total_projected += a_projected
            pct = int(round(w * 100))
            info = ASSET_INFO.get(asset, {})
            mix_out.append({
                "asset_name": asset,
                "category": str(row["category"]),
                "what_it_is": info.get("plain", f"{row['category']} investment."),
                "percent": pct,
                "monthly_amount": round(a_monthly, 2),
                "starting_amount": round(a_savings, 2),
                "total_invested": round(a_invested, 2),
                "projected_value": round(a_projected, 2),
                "profit": round(a_projected - a_invested, 2),
                "assumed_annual_return": float(row["expected_return"]),
                "lock_in_years": int(row["lock_in"]),
                "why": _why_text(asset, role, g["years"], risk_profile, pct),
            })

        scenarios = {}
        for label, delta in SCENARIOS.items():
            lump_s, stream_s = _blend_factors(
                g["weights"], g["rows"], months, delta
            )
            value = g["savings"] * lump_s + g["monthly"] * stream_s
            scenarios[label] = {
                "projected_value": round(value, 2),
                "profit": round(value - total_invested, 2),
                "reaches_goal": bool(value >= g["amount"] * 0.999),
            }

        sim = run_monte_carlo(
            current_savings=g["savings"], monthly_investment=g["monthly"],
            expected_return=g["ret"], volatility=g["vol"], years=g["years"],
            goal_amount=g["amount"], simulations=simulations, seed=seed,
        )

        status = _status(total_projected, g["amount"])
        shortfall = max(0.0, g["amount"] - total_projected)
        gap = max(0.0, g["required"] - g["monthly"])
        years_needed = None
        if status != "on_track":
            years_needed = _years_needed(
                g["amount"], g["savings"], g["monthly"], g["weights"], g["rows"]
            )

        advice = []
        if status == "on_track":
            advice.append("You are on track. Keep investing the same amount every month.")
        else:
            if gap > 0:
                advice.append(
                    f"Invest about ₹{g['required']:,.0f} a month instead of "
                    f"₹{g['monthly']:,.0f} (₹{gap:,.0f} more) to reach this goal."
                )
            if years_needed and years_needed > g["years"]:
                advice.append(
                    f"Or keep the same monthly amount and give it about "
                    f"{years_needed} years instead of {g['years']}."
                )
            advice.append(
                f"Or lower the target. Your plan reaches about ₹{total_projected:,.0f}."
            )

        goal_results.append({
            "name": g["name"],
            "target_amount": g["amount"],
            "years": g["years"],
            "status": status,
            "starting_amount": round(g["savings"], 2),
            "monthly_amount": round(g["monthly"], 2),
            "required_monthly": round(g["required"], 2),
            "monthly_gap": round(gap, 2),
            "total_invested": round(total_invested, 2),
            "projected_value": round(total_projected, 2),
            "profit": round(total_projected - total_invested, 2),
            "shortfall": round(shortfall, 2),
            "chance_of_reaching_goal": round(sim["goal_probability"] * 100),
            "bad_case_value": round(sim["pessimistic_outcome"], 2),
            "good_case_value": round(sim["optimistic_outcome"], 2),
            "assumed_return": round(g["ret"], 4),
            "years_needed": years_needed,
            "scenarios": scenarios,
            "mix": mix_out,
            "advice": advice,
        })

    total_monthly = sum(r["monthly_amount"] for r in goal_results)
    total_required = sum(r["required_monthly"] for r in goal_results)
    total_invested = sum(r["total_invested"] for r in goal_results)
    total_projected = sum(r["projected_value"] for r in goal_results)
    on_track = sum(1 for r in goal_results if r["status"] == "on_track")

    summary = {
        "mode": mode,
        "monthly_budget": float(monthly_budget),
        "monthly_needed": round(total_required, 2),
        "monthly_allocated": round(total_monthly, 2),
        "monthly_left_over": round(max(0.0, monthly_budget - total_monthly), 2),
        "affordable": bool(monthly_budget <= 0 or total_required <= monthly_budget + 0.5),
        "extra_needed_per_month": round(max(0.0, total_required - monthly_budget), 2)
        if monthly_budget > 0 else 0.0,
        "total_invested": round(total_invested, 2),
        "projected_value": round(total_projected, 2),
        "projected_profit": round(total_projected - total_invested, 2),
        "goals_on_track": on_track,
        "goals_total": len(goal_results),
        "unused_savings": round(savings_left, 2),
    }

    method = (
        "Your monthly budget is shared across goals, earliest deadline first, "
        "so nearer goals are fully funded before longer ones."
        if mode == "budget" else
        "Each goal's monthly amount is what it needs to reach its target "
        "under the assumed returns."
    )

    used = sorted({m["asset_name"] for r in goal_results for m in r["mix"]})

    return {
        "mode": mode,
        "risk_profile": risk_profile,
        "risk_label": RISK_LABELS[risk_profile],
        "data_sources": describe_sources(assets, used),
        "summary": summary,
        "goals": goal_results,
        "method": method,
        "assumptions": [
            "Returns are assumptions from data/assets.csv, not forecasts or guarantees.",
            "Monthly amounts are sized using returns 2 points below the assumed ones, as a safety cushion.",
            "Scenarios shift every return: conservative -3 points, optimistic +2 points.",
            "Money is invested at the end of each month. Tax, fees and inflation are not included.",
            "'Chance of reaching goal' comes from a simulation. It is not a promise.",
        ],
    }