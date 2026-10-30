"""Leakage-controlled ML forecasting for daily asset returns.

Features are known at forecast origin t. The target is the compounded return
over the next horizon trading days. Walk-forward training excludes any row
whose target window overlaps the test forecast origin.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error


def build_forecast_dataset(returns, horizon=21):
    """Build lagged/momentum/volatility features and forward compounded target."""
    x = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    if not isinstance(x.index, pd.DatetimeIndex):
        raise ValueError("Returns must have a DatetimeIndex.")
    if horizon < 1:
        raise ValueError("Forecast horizon must be positive.")
    frame = pd.DataFrame(index=x.index)
    for lag in (1, 2, 5, 10, 21):
        frame[f"return_lag_{lag}"] = x.shift(lag-1)
    for window in (5, 21, 63):
        frame[f"momentum_{window}"] = (1+x).rolling(window).apply(np.prod, raw=True)-1
        frame[f"volatility_{window}"] = x.rolling(window).std()
    frame["downside_volatility_21"] = x.clip(upper=0).rolling(21).std()
    frame["drawdown_63"] = (1+x).rolling(63).apply(np.prod, raw=True)
    wealth = (1+x).cumprod()
    frame["drawdown_63"] = wealth / wealth.rolling(63, min_periods=1).max() - 1
    forward = (1+x).shift(-1).rolling(horizon).apply(np.prod, raw=True).shift(-(horizon-1))-1
    frame["target"] = forward
    return frame.replace([np.inf, -np.inf], np.nan).dropna()


def _metrics(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    direction = np.sign(actual) == np.sign(predicted)
    denom = np.sum((actual-actual.mean())**2)
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "directional_accuracy": float(direction.mean()),
        "observations": int(len(actual)),
        "r2_oos": float(1-np.sum((actual-predicted)**2)/denom) if denom > 0 else None,
    }


def walk_forward_forecast(
    returns,
    *,
    horizon=21,
    min_train=504,
    step=21,
    models=("ridge", "hist_gradient_boosting"),
):
    """Expanding-window OOS forecasts; train only on fully matured target windows."""
    data = build_forecast_dataset(returns, horizon=horizon)
    if len(data) < min_train + step:
        raise ValueError(
            f"Insufficient history: need at least {min_train+step} feature rows; got {len(data)}."
        )
    feature_cols = [c for c in data.columns if c != "target"]
    X = data[feature_cols]
    y = data["target"]
    predictions = []
    for test_pos in range(min_train, len(data), step):
        origin = data.index[test_pos]
        # A training observation is admissible only if its forward target ends
        # strictly before the current forecast origin.
        train_end = test_pos - horizon
        if train_end < min_train:
            continue
        train_x, train_y = X.iloc[:train_end], y.iloc[:train_end]
        test_x = X.iloc[[test_pos]]
        if len(train_x) < min_train:
            continue
        baseline = float(train_y.mean())
        row = {"date": origin, "actual": float(y.iloc[test_pos]),
               "historical_mean": baseline}
        for model_name in models:
            if model_name == "ridge":
                model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
            elif model_name == "hist_gradient_boosting":
                model = HistGradientBoostingRegressor(
                    max_iter=100, learning_rate=.05, max_leaf_nodes=7,
                    l2_regularization=2.0, random_state=42,
                )
            else:
                raise ValueError(f"Unsupported forecasting model: {model_name}")
            model.fit(train_x, train_y)
            row[model_name] = float(model.predict(test_x)[0])
        predictions.append(row)
    pred = pd.DataFrame(predictions)
    if pred.empty:
        raise ValueError("No valid walk-forward forecasts were generated.")
    summary = {
        "historical_mean": _metrics(pred["actual"], pred["historical_mean"]),
        **{name: _metrics(pred["actual"], pred[name]) for name in models},
    }
    return {
        "predictions": pred,
        "metrics": summary,
        "horizon_days": int(horizon),
        "step_days": int(step),
        "min_train": int(min_train),
        "feature_columns": feature_cols,
        "validation": "expanding window; target-overlap purge; no random shuffle",
        "best_model_by_rmse": min(summary, key=lambda name: summary[name]["rmse"]),
    }
