def calculate_risk_score(age, income, expenses, debt, dependents):
    score = 0

    if age < 30:
        score += 2
    elif age < 45:
        score += 1

    if income > expenses * 2:
        score += 2
    elif income > expenses:
        score += 1

    if debt < income * 0.3:
        score += 2
    elif debt < income:
        score += 1

    if dependents == 0:
        score += 1

    return score


def get_risk_profile(score):
    if score <= 2:
        return "Low"
    elif score <= 4:
        return "Moderate"
    elif score <= 6:
        return "Moderately High"
    else:
        return "High"
