
import pytest

from engine.monte_carlo import run_monte_carlo


def test_monte_carlo_returns_expected_fields():
    result = run_monte_carlo(
        100000, 10000, 0.10, 0.15, 10, 2000000,
        simulations=1000,
        seed=42,
    )

    expected_fields = {
        "simulations",
        "years",
        "goal_amount",
        "goal_probability",
        "pessimistic_outcome",
        "median_outcome",
        "optimistic_outcome",
        "average_outcome",
    }

    assert expected_fields.issubset(result.keys())


def test_goal_probability_is_between_zero_and_one():
    result = run_monte_carlo(
        100000, 10000, 0.10, 0.15, 10, 2000000,
        seed=42,
    )

    assert 0 <= result["goal_probability"] <= 1


def test_simulation_results_are_reproducible():
    first = run_monte_carlo(
        100000, 10000, 0.10, 0.15, 10, 2000000,
        seed=42,
    )

    second = run_monte_carlo(
        100000, 10000, 0.10, 0.15, 10, 2000000,
        seed=42,
    )

    assert first == second


def test_invalid_negative_savings_raises_error():
    with pytest.raises(ValueError):
        run_monte_carlo(
            -100, 10000, 0.10, 0.15, 10, 2000000
        )


def test_invalid_zero_years_raises_error():
    with pytest.raises(ValueError):
        run_monte_carlo(
            100000, 10000, 0.10, 0.15, 0, 2000000
        )


def test_percentiles_are_ordered():
    result = run_monte_carlo(
        100000, 10000, 0.10, 0.15, 10, 2000000,
        seed=42,
    )

    assert (
        result["pessimistic_outcome"]
        <= result["median_outcome"]
        <= result["optimistic_outcome"]
    )
