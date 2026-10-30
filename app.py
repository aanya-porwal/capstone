
from flask import Flask, render_template, request, jsonify

from engine.market_data import (
    generate_market_report,
    calculate_investment_growth,
)
from engine.planner import create_financial_assessment
from engine.advisor import build_plan, resolve_risk_profile
from engine.live_data import get_live_assets, refresh_live_assets
from engine.advisor import build_plan, resolve_risk_profile


app = Flask(__name__)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/assess", methods=["POST"])
def assess():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON request is required."}), 400

    try:
        dependent_ages = data.get("dependent_ages", [])

        if not isinstance(dependent_ages, list):
            raise ValueError("Dependent ages must be provided as a list.")

        dependent_count = int(data["dependents"])

        if not 0 <= dependent_count <= 10:
            raise ValueError("Dependents must be between 0 and 10.")

        if len(dependent_ages) != dependent_count:
            raise ValueError(
                "The number of dependent ages must match the dependents count."
            )

        if any(
            isinstance(age, bool)
            or not isinstance(age, (int, float))
            or not float(age).is_integer()
            or not 0 <= age <= 120
            for age in dependent_ages
        ):
            raise ValueError(
                "Dependent ages must be whole numbers between 0 and 120."
            )

        user = {
            "age": int(data["age"]),
            "income": float(data["income"]),
            "expenses": float(data["expenses"]),
            "debt": float(data["debt"]),
            "dependents": dependent_count,
            "dependent_ages": dependent_ages,
            "current_savings": float(data["current_savings"]),
            "monthly_investment": float(data["monthly_investment"]),
            "goal_amount": float(data["goal_amount"]),
            "goal_years": int(data["goal_years"]),
            "goals": data.get("goals", []),
        }

        result = create_financial_assessment(user)

        return jsonify(result)

    except (TypeError, ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        app.logger.exception("Financial assessment failed")
        return jsonify({
            "error": "Unable to complete the financial assessment."
        }), 500


@app.route("/api/plan", methods=["POST"])
def plan():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON request is required."}), 400

    try:
        risk_profile = resolve_risk_profile(data)

        result = build_plan(
            mode=data.get("mode", "budget"),
            goals=data.get("goals", []),
            monthly_budget=float(data.get("monthly_budget") or 0),
            current_savings=float(data.get("current_savings") or 0),
            risk_profile=risk_profile,
        )
        return jsonify(result)

    except (TypeError, ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        app.logger.exception("Plan generation failed")
        return jsonify({"error": "Unable to build the plan."}), 500




@app.route("/api/refresh-data", methods=["POST"])
def refresh_data():
    try:
        return jsonify({"status": refresh_live_assets()})
    except Exception:
        app.logger.exception("Data refresh failed")
        return jsonify({"error": "Unable to refresh market data."}), 500
@app.route("/api/market-report", methods=["GET"])
def market_report():
    instruments = {
        "Nifty 50 ETF": "data/nifty50_historical.csv",
        "Gold ETF": "data/goldbees_historical.csv",
    }

    try:
        reports = [
            generate_market_report(name, path)
            for name, path in instruments.items()
        ]

        return jsonify({"reports": reports})

    except (FileNotFoundError, ValueError, KeyError) as error:
        app.logger.exception("Market report generation failed")
        return jsonify({
            "error": "Unable to generate the market report.",
            "details": str(error),
        }), 500

    except Exception:
        app.logger.exception("Unexpected market report failure")
        return jsonify({
            "error": (
                "An unexpected error occurred while generating "
                "the market report."
            )
        }), 500


@app.route("/api/investment-growth", methods=["GET"])
def investment_growth():
    instruments = {
        "Nifty 50 ETF": "data/nifty50_historical.csv",
        "Gold ETF": "data/goldbees_historical.csv",
    }

    try:
        reports = []

        for asset_name, file_path in instruments.items():
            growth = calculate_investment_growth(file_path)

            reports.append({
                "asset_name": asset_name,
                "dates": growth["Date"].dt.strftime(
                    "%Y-%m-%d"
                ).tolist(),
                "values": [
                    round(float(value), 2)
                    for value in growth["investment_value"]
                ],
            })

        return jsonify({"reports": reports})

    except (FileNotFoundError, ValueError, KeyError):
        app.logger.exception("Investment growth calculation failed")
        return jsonify({
            "error": "Unable to calculate historical investment growth."
        }), 500

    except Exception:
        app.logger.exception("Unexpected investment growth failure")
        return jsonify({
            "error": "An unexpected error occurred while calculating investment growth."
        }), 500


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )
