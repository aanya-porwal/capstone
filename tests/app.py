from flask import Flask, render_template, request, jsonify
from engine.planner import create_financial_assessment


app = Flask(__name__)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/assess", methods=["POST"])
def assess():

    data = request.get_json()

    try:
        user = {
            "age": int(data["age"]),
            "income": float(data["income"]),
            "expenses": float(data["expenses"]),
            "debt": float(data["debt"]),
            "dependents": int(data["dependents"]),
            "current_savings": float(data["current_savings"]),
            "monthly_investment": float(data["monthly_investment"]),
            "goal_amount": float(data["goal_amount"]),
            "goal_years": int(data["goal_years"])
        }

        result = create_financial_assessment(user)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 400


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )