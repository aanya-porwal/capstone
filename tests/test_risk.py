from engine.risk import calculate_risk_score, get_risk_profile


def test_risk_score():
    score = calculate_risk_score(
        age=25,
        income=100000,
        expenses=50000,
        debt=10000,
        dependents=0
    )

    assert score == 6


def test_risk_profile():
    score = calculate_risk_score(
        age=25,
        income=100000,
        expenses=50000,
        debt=10000,
        dependents=0
    )

    profile = get_risk_profile(score)

    assert profile == "Moderately High"