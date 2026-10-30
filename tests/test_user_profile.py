from engine.user_profile import create_user_profile


def test_user_profile_creation():
    user = create_user_profile(
        age=25,
        income=100000,
        expenses=50000,
        debt=10000,
        dependents=0,
        current_savings=500000,
        monthly_investment=30000,
        goal_amount=3000000,
        goal_years=10
    )

    assert isinstance(user, dict)
    assert user["age"] == 25
    assert user["income"] == 100000
    assert user["current_savings"] == 500000
    assert user["monthly_investment"] == 30000
    assert user["goal_amount"] == 3000000
    assert user["goal_years"] == 10