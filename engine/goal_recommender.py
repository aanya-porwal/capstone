
import pandas as pd


ASSET_DATA_PATH = "data/assets.csv"


def load_assets(path=ASSET_DATA_PATH):
    """Load investment options and validate the required columns."""
    assets = pd.read_csv(path)

    required_columns = {
        "asset_name",
        "category",
        "expected_return",
        "volatility",
        "risk_level",
        "liquidity",
        "lock_in",
    }

    missing = required_columns - set(assets.columns)
    if missing:
        raise ValueError(
            f"Asset dataset is missing columns: {sorted(missing)}"
        )

    if assets.empty:
        raise ValueError("The asset dataset contains no investment options.")

    if (
        assets["expected_return"].isna().any()
        or assets["volatility"].isna().any()
        or assets["risk_level"].isna().any()
        or assets["liquidity"].isna().any()
        or assets["lock_in"].isna().any()
    ):
        raise ValueError("The asset dataset contains missing numeric values.")

    if (
        (assets["expected_return"] < 0).any()
        or (assets["volatility"] < 0).any()
        or (assets["risk_level"] < 1).any()
        or (assets["risk_level"] > 5).any()
        or (assets["liquidity"] < 0).any()
        or (assets["liquidity"] > 1).any()
        or (assets["lock_in"] < 0).any()
    ):
        raise ValueError("The asset dataset contains invalid values.")

    return assets


def recommend_goal_investments(
    goal_name,
    goal_amount,
    years,
    monthly_contribution,
    risk_profile,
    assets=None,
):
    """
    Produce a transparent, rule-based investment-category suggestion.

    This is an educational planning estimate, not a personalised,
    regulated investment recommendation.
    """
    if not isinstance(goal_name, str) or not goal_name.strip():
        raise ValueError("Goal name is required.")

    if goal_amount < 0 or years <= 0 or monthly_contribution < 0:
        raise ValueError("Invalid goal amount, timeline or contribution.")

    if risk_profile not in {
        "Low",
        "Moderate",
        "Moderately High",
        "High",
    }:
        raise ValueError("Unknown risk profile.")

    if assets is None:
        assets = load_assets()

    # Avoid options whose recorded lock-in exceeds the goal horizon.
    eligible = assets[assets["lock_in"] <= years].copy()

    if eligible.empty:
        return {
            "goal_name": goal_name.strip(),
            "suggested_mix": [],
            "explanation": (
                "No listed option passes the dataset's lock-in check for "
                "this timeline. Review the available assets and timeline."
            ),
            "warnings": [
                "A recorded lock-in of zero does not guarantee immediate access."
            ],
        }

    # Match the risk profile to a conservative maximum risk level.
    risk_caps = {
        "Low": 2,
        "Moderate": 3,
        "Moderately High": 4,
        "High": 5,
    }
    eligible = eligible[eligible["risk_level"] <= risk_caps[risk_profile]]

    # Short-term goals need more liquidity and lower volatility.
    if years <= 3:
        eligible = eligible[
            (eligible["liquidity"] >= 0.7)
            & (eligible["volatility"] <= 0.05)
        ]
        horizon_note = (
            "This is a short-term goal, so the initial screen prioritises "
            "lower volatility and higher recorded liquidity."
        )
    elif years <= 7:
        eligible = eligible[
            (eligible["liquidity"] >= 0.5)
            & (eligible["volatility"] <= 0.12)
        ]
        horizon_note = (
            "This is a medium-term goal, so the initial screen balances "
            "liquidity with a preference for moderate volatility."
        )
    else:
        horizon_note = (
            "This is a longer-term goal. A wider range of eligible assets "
            "may be considered, provided they fit the user's risk profile."
        )

    if eligible.empty:
        return {
            "goal_name": goal_name.strip(),
            "suggested_mix": [],
            "explanation": (
                f"{horizon_note} However, no listed asset passes all the "
                "current risk, liquidity and lock-in filters. Do not force "
                "an allocation; review the assumptions or the available assets."
            ),
            "warnings": [
                "The dataset is limited and its expected returns are assumptions."
            ],
        }

    # Start with an equal-weight mix rather than falsely claiming
    # an optimiser has found a uniquely optimal allocation.
    selected = eligible.sort_values(
        by=["volatility", "risk_level", "asset_name"],
        ascending=[True, True, True],
    ).head(3)

    weight = 100.0 / len(selected)
    suggested_mix = []

    for _, asset in selected.iterrows():
        suggested_mix.append({
            "asset_name": str(asset["asset_name"]),
            "category": str(asset["category"]),
            "allocation_percent": round(weight, 2),
            "monthly_amount": round(monthly_contribution * weight / 100, 2),
            "assumed_annual_return": float(asset["expected_return"]),
            "recorded_volatility": float(asset["volatility"]),
            "recorded_liquidity": float(asset["liquidity"]),
            "recorded_lock_in_years": int(asset["lock_in"]),
        })

    return {
        "goal_name": goal_name.strip(),
        "goal_amount": float(goal_amount),
        "years": int(years),
        "monthly_contribution": float(monthly_contribution),
        "risk_profile": risk_profile,
        "suggested_mix": suggested_mix,
        "explanation": horizon_note,
        "warnings": [
            "Expected returns are model assumptions, not guaranteed outcomes.",
            "Equal weighting is a transparent starting illustration, not an optimised portfolio.",
            "Tax treatment, exit costs, product terms and emergency savings are not fully modelled.",
        ],
    }
