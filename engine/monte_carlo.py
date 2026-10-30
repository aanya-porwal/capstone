
import numpy as np


def run_monte_carlo(
    current_savings,
    monthly_investment,
    expected_return,
    volatility,
    years,
    goal_amount,
    simulations=1000,
    seed=None,
):
    if current_savings < 0 or monthly_investment < 0:
        raise ValueError("Savings and investment cannot be negative.")

    if not 0 <= expected_return:
        raise ValueError("Expected return cannot be negative.")

    if volatility < 0 or years <= 0 or goal_amount < 0:
        raise ValueError("Invalid volatility, years, or goal amount.")

    if simulations < 1:
        raise ValueError("Simulations must be at least 1.")

    rng = np.random.default_rng(seed)
    months = int(round(years * 12))
    monthly_return = (1 + expected_return) ** (1 / 12) - 1
    monthly_volatility = volatility / np.sqrt(12)

    monthly_returns = rng.normal(
        monthly_return, monthly_volatility, (simulations, months)
    )
    monthly_returns = np.maximum(monthly_returns, -0.95)

    wealth = np.full(simulations, float(current_savings))
    for month in range(months):
        wealth = wealth * (1 + monthly_returns[:, month]) + monthly_investment

    final_values = wealth

    return {
        "simulations": int(simulations),
        "years": int(years),
        "goal_amount": float(goal_amount),
        "goal_probability": float(
            np.mean(final_values >= goal_amount)
        ),
        "pessimistic_outcome": float(
            np.percentile(final_values, 10)
        ),
        "median_outcome": float(
            np.percentile(final_values, 50)
        ),
        "optimistic_outcome": float(
            np.percentile(final_values, 90)
        ),
        "average_outcome": float(np.mean(final_values)),
    }
