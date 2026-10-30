
def create_user_profile(
    age,
    income,
    expenses,
    debt,
    dependents,
    current_savings,
    monthly_investment,
    goal_amount,
    goal_years,
    dependent_ages=None,
):
    if dependent_ages is None:
        dependent_ages = []

    if len(dependent_ages) != dependents:
        raise ValueError(
            "The number of dependent ages must match the dependents count."
        )

    if any(
        not isinstance(dependent_age, int)
        or isinstance(dependent_age, bool)
        or not 0 <= dependent_age <= 120
        for dependent_age in dependent_ages
    ):
        raise ValueError(
            "Dependent ages must be whole numbers between 0 and 120."
        )

    return {
        "age": age,
        "income": income,
        "expenses": expenses,
        "debt": debt,
        "dependents": dependents,
        "dependent_ages": dependent_ages,
        "current_savings": current_savings,
        "monthly_investment": monthly_investment,
        "goal_amount": goal_amount,
        "goal_years": goal_years,
    }
