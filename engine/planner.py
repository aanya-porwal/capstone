from engine.goal_recommender import recommend_goal_investments
from engine.risk import calculate_risk_score, get_risk_profile
from engine.goals import (
    future_value,
    check_goal,
    evaluate_financial_goal,
    required_monthly_investment,
)
from engine.optimizer import optimize_portfolio
from engine.monte_carlo import run_monte_carlo


def create_financial_assessment(user):
    risk_score = calculate_risk_score(
        user["age"],
        user["income"],
        user["expenses"],
        user["debt"],
        user["dependents"],
    )

    risk_profile = get_risk_profile(risk_score)

    risk_limits = {
        "Low": 0.06,
        "Moderate": 0.08,
        "Moderately High": 0.10,
        "High": 0.15,
    }

    risk_limit = risk_limits.get(risk_profile, 0.15)

    optimized_result = optimize_portfolio(
        risk_profile,
        risk_limit,
    )

    if optimized_result is None:
        raise ValueError(
            "Unable to create a portfolio within the specified constraints."
        )

    portfolio = optimized_result["portfolio"]
    annual_return = optimized_result["expected_return"]
    portfolio_risk = optimized_result["risk"]
    diagnostics = optimized_result["diagnostics"]

    # Preserve the existing single-goal calculations.
    projected_value = future_value(
        user["current_savings"],
        user["monthly_investment"],
        annual_return,
        user["goal_years"],
    )

    goal_status = check_goal(
        projected_value,
        user["goal_amount"],
    )

    monte_carlo_result = run_monte_carlo(
        current_savings=user["current_savings"],
        monthly_investment=user["monthly_investment"],
        expected_return=annual_return,
        volatility=portfolio_risk,
        years=user["goal_years"],
        goal_amount=user["goal_amount"],
        simulations=1000,
    )

    # Evaluate additional financial goals when supplied.
    
    # Evaluate goals using one shared monthly investment budget.
    goals = user.get("goals", [])
    evaluated_goals = []

    if not isinstance(goals, list):
        raise ValueError("Goals must be provided as a list.")

    if len(goals) > 10:
        raise ValueError("A maximum of 10 financial goals is allowed.")

    if goals:
        prepared_goals = []

        for goal in goals:
            if not isinstance(goal, dict):
                raise ValueError("Each goal must be an object.")

            if not {"name", "amount", "years"}.issubset(goal):
                raise ValueError(
                    "Each goal must include name, amount, and years."
                )

            name = goal["name"]
            amount = float(goal["amount"])
            years = int(goal["years"])

            if not isinstance(name, str) or not name.strip():
                raise ValueError("Each goal must have a name.")

            if amount < 0 or years <= 0:
                raise ValueError(
                    "Goal amount must be non-negative and years must be positive."
                )

            if float(goal["years"]) != years:
                raise ValueError("Goal years must be a whole number.")

            prepared_goals.append({
                "name": name.strip(),
                "amount": amount,
                "years": years,
            })

        # Allocate existing savings proportionally to target amounts.
        total_target = sum(goal["amount"] for goal in prepared_goals)
        total_savings = float(user["current_savings"])

        for goal in prepared_goals:
            if total_target > 0:
                goal["allocated_savings"] = (
                    total_savings * goal["amount"] / total_target
                )
            else:
                goal["allocated_savings"] = 0.0

            goal["required_monthly"] = required_monthly_investment(
                goal_amount=goal["amount"],
                current_savings=goal["allocated_savings"],
                annual_return=annual_return,
                years=goal["years"],
            )

        # Never allocate more than the user's stated monthly budget.
        monthly_budget = float(user["monthly_investment"])
        total_required = sum(
            goal["required_monthly"] for goal in prepared_goals
        )

        if total_required <= monthly_budget:
            for goal in prepared_goals:
                goal["allocated_monthly"] = goal["required_monthly"]
        elif total_required > 0:
            for goal in prepared_goals:
                goal["allocated_monthly"] = (
                    monthly_budget
                    * goal["required_monthly"]
                    / total_required
                )
        else:
            for goal in prepared_goals:
                goal["allocated_monthly"] = 0.0

        # Generate separate projections and recommendations.
        for goal in prepared_goals:
            result = evaluate_financial_goal(
                name=goal["name"],
                goal_amount=goal["amount"],
                goal_years=goal["years"],
                current_savings=goal["allocated_savings"],
                monthly_investment=goal["allocated_monthly"],
                annual_return=annual_return,
                volatility=portfolio_risk,
                simulations=1000,
            )
            
            investment_recommendation = recommend_goal_investments(
                goal_name=goal["name"],
                goal_amount=goal["amount"],
                years=goal["years"],
                monthly_contribution=goal["allocated_monthly"],
                risk_profile=risk_profile,
            )

            result["investment_recommendation"] = investment_recommendation

            result["allocated_savings"] = float(goal["allocated_savings"])
            result["allocated_monthly_investment"] = float(
                goal["allocated_monthly"]
            )
            result["required_monthly_investment"] = float(
                goal["required_monthly"]
            )

            monthly_gap = max(
                0.0,
                goal["required_monthly"] - goal["allocated_monthly"],
            )
            result["monthly_contribution_gap"] = float(monthly_gap)

            if monthly_gap > 0:
                result["recommendation"] = (
                    f"Your {goal['name']} goal needs an estimated "
                    f"₹{goal['required_monthly']:,.0f} per month under "
                    f"the assumed return, but the current allocation is "
                    f"₹{goal['allocated_monthly']:,.0f}. The difference "
                    f"is ₹{monthly_gap:,.0f} per month. Consider changing "
                    "your goal timeline or target, or prioritising this "
                    "goal over another."
                )
                result["status"] = "Needs adjustment"
            elif result["projected_value"] >= goal["amount"]:
                result["recommendation"] = (
                    f"Your {goal['name']} goal is projected to reach its "
                    "target under the assumed return. Continue monitoring "
                    "your progress and review the plan regularly."
                )
                result["status"] = "On track"
            else:
                result["recommendation"] = (
                    f"Your {goal['name']} goal is not yet projected to "
                    "reach its target. Review the timeline, target amount "
                    "and contribution allocation."
                )
                result["status"] = "Needs review"

            evaluated_goals.append(result)


        # Explain the shared budget and allocation in the API response.
        allocated_total = sum(
            goal["allocated_monthly"] for goal in prepared_goals
        )

        goal_allocation = {
            "monthly_budget": monthly_budget,
            "total_allocated": allocated_total,
            "remaining_budget": max(0.0, monthly_budget - allocated_total),
            "method": "Proportional allocation based on estimated required contributions",
        }
    else:
        goal_allocation = {
            "monthly_budget": float(user["monthly_investment"]),
            "total_allocated": 0.0,
            "remaining_budget": float(user["monthly_investment"]),
            "method": "No additional goals supplied",
        }


    return {
        "risk_score": risk_score,
        "risk_profile": risk_profile,
        "portfolio": portfolio,
        "expected_return": annual_return,
        "portfolio_volatility": portfolio_risk,
        "projected_value": projected_value,
        "goal_status": goal_status,
        "portfolio_diagnostics": diagnostics,
        "monte_carlo": monte_carlo_result,
        "goals": evaluated_goals,
        "goal_allocation": goal_allocation,
    }
