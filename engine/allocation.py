def get_allocation(risk_profile):
    if risk_profile == "Low":
        return {
            "Debt": 0.60,
            "Equity": 0.20,
            "Gold": 0.10,
            "Tax Advantaged": 0.10
        }

    elif risk_profile == "Moderate":
        return {
            "Debt": 0.40,
            "Equity": 0.40,
            "Gold": 0.10,
            "Tax Advantaged": 0.10
        }

    elif risk_profile == "Moderately High":
        return {
            "Debt": 0.25,
            "Equity": 0.50,
            "Gold": 0.10,
            "Tax Advantaged": 0.15
        }

    else:
        return {
            "Debt": 0.15,
            "Equity": 0.60,
            "Gold": 0.10,
            "Tax Advantaged": 0.15
        }