
def monthly_rate(annual_return):
    """Convert an effective annual return (0.08 = 8% a year) to a monthly rate.

    Using (1 + r) ** (1/12) - 1 means 12 months of growth add up to exactly
    the quoted annual return, which is how FD, PPF and fund returns are quoted.
    """
    return (1 + annual_return) ** (1 / 12) - 1

def monthly_rate(annual_return):
    """Effective annual return (0.08 = 8%) to a monthly rate."""
    return (1 + annual_return) ** (1 / 12) - 1
def future_value(current_savings, monthly_investment, annual_return, years):
    """Value after `years`: lump sum plus month-end contributions.

    `annual_return` is an effective annual rate.
    """
    monthly_return = monthly_rate(annual_return)
    months = int(round(years * 12))

    if monthly_return == 0:
        return current_savings + monthly_investment * months

    future_savings = current_savings * (1 + monthly_return) ** months
    future_investments = monthly_investment * (
        ((1 + monthly_return) ** months - 1) / monthly_return
    )

    return future_savings + future_investments


def check_goal(projected_value, goal_amount):
    if projected_value >= goal_amount:
        return "Goal achievable"
    return "Goal not achievable"


def required_monthly_investment(
    goal_amount, current_savings, annual_return, years
):
    """Estimate the monthly contribution needed to reach a future target."""
    if goal_amount < 0 or current_savings < 0:
        raise ValueError("Goal amount and savings cannot be negative.")
    if years <= 0 or annual_return < 0:
        raise ValueError("Years must be positive and return cannot be negative.")

    months = int(round(years * 12))
    monthly_return = monthly_rate(annual_return)

    # Grow existing savings to the goal date.
    future_savings = current_savings * (1 + monthly_return) ** months
    remaining_target = goal_amount - future_savings

    if remaining_target <= 0:
        return 0.0

    if monthly_return == 0:
        return remaining_target / months

    contribution_factor = (
        ((1 + monthly_return) ** months - 1) / monthly_return
    )
    return remaining_target / contribution_factor


def build_goal_recommendation(
    name,
    goal_amount,
    years,
    projected_value,
    required_monthly,
    available_monthly,
):
    """Create a clear, goal-specific explanation and next step."""
    shortfall = max(0.0, goal_amount - projected_value)
    surplus = max(0.0, projected_value - goal_amount)

    if projected_value >= goal_amount:
        status = "On track"
        recommendation = (
            f"Your current plan is projected to meet your {name} goal. "
            "Keep contributions consistent and review your progress regularly."
        )
    elif available_monthly >= required_monthly:
        status = "Needs adjustment"
        recommendation = (
            f"Your current plan is projected to fall short of your {name} "
            f"goal by approximately ₹{shortfall:,.0f}. An estimated "
            f"₹{required_monthly:,.0f} per month could reach the target "
            "under the assumed return. Check that this fits your overall budget."
        )
    else:
        status = "Timeline or target needs review"
        recommendation = (
            f"Your current plan is projected to fall short of your {name} "
            f"goal by approximately ₹{shortfall:,.0f}. Reaching it may require "
            f"more than your stated monthly investment. Consider extending "
            "the timeline, lowering the target, or prioritising this goal."
        )

    return {
        "status": status,
        "shortfall": float(shortfall),
        "surplus": float(surplus),
        "required_monthly_investment": float(required_monthly),
        "recommendation": recommendation,
    }


def evaluate_financial_goal(
    name,
    goal_amount,
    goal_years,
    current_savings,
    monthly_investment,
    annual_return,
    volatility,
    simulations=1000,
):
    from engine.monte_carlo import run_monte_carlo

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Each financial goal must have a name.")
    if goal_amount < 0 or goal_years <= 0:
        raise ValueError(
            "Goal amount must be non-negative and goal timeline must be positive."
        )
    if current_savings < 0 or monthly_investment < 0:
        raise ValueError("Savings and monthly investment cannot be negative.")
    if annual_return < 0 or volatility < 0:
        raise ValueError("Return and volatility cannot be negative.")

    name = name.strip()
    projected_value = future_value(
        current_savings,
        monthly_investment,
        annual_return,
        goal_years,
    )

    required_monthly = required_monthly_investment(
        goal_amount,
        current_savings,
        annual_return,
        goal_years,
    )

    monte_carlo = run_monte_carlo(
        current_savings=current_savings,
        monthly_investment=monthly_investment,
        expected_return=annual_return,
        volatility=volatility,
        years=goal_years,
        goal_amount=goal_amount,
        simulations=simulations,
    )

    recommendation = build_goal_recommendation(
        name=name,
        goal_amount=goal_amount,
        years=goal_years,
        projected_value=projected_value,
        required_monthly=required_monthly,
        available_monthly=monthly_investment,
    )

    return {
        "name": name,
        "goal_amount": float(goal_amount),
        "goal_years": int(goal_years),
        "projected_value": float(projected_value),
        "goal_status": check_goal(projected_value, goal_amount),
        **recommendation,
        "monte_carlo": monte_carlo,
    }
