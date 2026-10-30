from engine.allocation import get_allocation
from engine.portfolio import create_portfolio


def test_portfolio_creation():
    allocation = get_allocation("Moderately High")

    portfolio = create_portfolio(allocation)

    assert isinstance(portfolio, dict)
    assert len(portfolio) > 0


def test_portfolio_weights_sum_to_one():
    allocation = get_allocation("Moderately High")

    portfolio = create_portfolio(allocation)

    total_weight = sum(portfolio.values())

    assert abs(total_weight - 1.0) < 0.0001