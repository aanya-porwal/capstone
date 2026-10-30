from engine.allocation import get_allocation


def test_low_risk_allocation():
    allocation = get_allocation("Low")

    assert allocation["Debt"] == 0.60
    assert allocation["Equity"] == 0.20
    assert allocation["Gold"] == 0.10
    assert allocation["Tax Advantaged"] == 0.10


def test_moderate_risk_allocation():
    allocation = get_allocation("Moderate")

    assert allocation["Debt"] == 0.40
    assert allocation["Equity"] == 0.40
    assert allocation["Gold"] == 0.10
    assert allocation["Tax Advantaged"] == 0.10


def test_moderately_high_allocation():
    allocation = get_allocation("Moderately High")

    assert allocation["Debt"] == 0.25
    assert allocation["Equity"] == 0.50
    assert allocation["Gold"] == 0.10
    assert allocation["Tax Advantaged"] == 0.15


def test_high_risk_allocation():
    allocation = get_allocation("High")

    assert allocation["Debt"] == 0.15
    assert allocation["Equity"] == 0.60
    assert allocation["Gold"] == 0.10
    assert allocation["Tax Advantaged"] == 0.15