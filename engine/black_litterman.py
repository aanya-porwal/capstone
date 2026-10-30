"""Black-Litterman Bayesian expected-return estimation and portfolio construction.

All returns and covariance inputs are annualised arithmetic quantities. The
module accepts explicit investor views; it never invents views from forecasts.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize


def _validate_covariance(covariance):
    sigma = np.asarray(covariance, dtype=float)
    if sigma.ndim != 2 or sigma.shape[0] != sigma.shape[1]:
        raise ValueError("Covariance matrix must be square.")
    if not np.isfinite(sigma).all():
        raise ValueError("Covariance matrix must contain finite values.")
    sigma = (sigma + sigma.T) / 2
    eig, vec = np.linalg.eigh(sigma)
    if eig.min() < -1e-8:
        raise ValueError("Covariance matrix must be positive semidefinite.")
    return vec @ np.diag(np.maximum(eig, 1e-10)) @ vec.T


def market_implied_returns(covariance, market_weights, risk_aversion=2.5):
    """Reverse-optimise equilibrium returns: pi = delta * Sigma * w_market."""
    sigma = _validate_covariance(covariance)
    weights = np.asarray(market_weights, dtype=float).reshape(-1)
    if len(weights) != sigma.shape[0]:
        raise ValueError("Market weights and covariance dimensions do not match.")
    if not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Market weights must be finite, non-negative and non-zero.")
    if risk_aversion <= 0 or not np.isfinite(risk_aversion):
        raise ValueError("Risk aversion must be positive and finite.")
    return risk_aversion * sigma @ (weights / weights.sum())


def black_litterman_posterior(covariance, market_weights, P, Q, *,
                              risk_aversion=2.5, tau=0.05, omega=None,
                              view_confidences=None):
    """Posterior expected returns from equilibrium prior and views P mu = Q."""
    sigma = _validate_covariance(covariance)
    pi = market_implied_returns(sigma, market_weights, risk_aversion)
    p = np.asarray(P, dtype=float)
    q = np.asarray(Q, dtype=float).reshape(-1)
    if p.ndim == 1:
        p = p.reshape(1, -1)
    if p.ndim != 2 or p.shape[1] != len(pi) or p.shape[0] != len(q):
        raise ValueError("P and Q dimensions do not match the asset universe.")
    if not np.isfinite(p).all() or not np.isfinite(q).all():
        raise ValueError("Views must contain finite values.")
    if tau <= 0 or not np.isfinite(tau):
        raise ValueError("tau must be positive and finite.")
    tau_sigma = tau * sigma
    view_cov = p @ tau_sigma @ p.T
    if omega is None:
        confidence = (np.full(len(q), 0.50) if view_confidences is None
                      else np.asarray(view_confidences, dtype=float).reshape(-1))
        if len(confidence) != len(q) or not np.isfinite(confidence).all():
            raise ValueError("One finite confidence value is required per view.")
        if ((confidence <= 0) | (confidence >= 1)).any():
            raise ValueError("View confidences must lie strictly between 0 and 1.")
        omega = np.diag(np.maximum(np.diag(view_cov), 1e-12) * (1-confidence) / confidence)
    else:
        omega = np.asarray(omega, dtype=float)
        if omega.shape != (len(q), len(q)) or not np.isfinite(omega).all():
            raise ValueError("Omega has invalid dimensions or non-finite values.")
        omega = (omega + omega.T) / 2
        if np.linalg.eigvalsh(omega).min() <= 0:
            raise ValueError("Omega must be positive definite.")
    middle = p @ tau_sigma @ p.T + omega
    gain = np.linalg.solve(middle, p @ tau_sigma)
    posterior_mu = pi + gain.T @ (q - p @ pi)
    posterior_uncertainty = tau_sigma - gain.T @ p @ tau_sigma
    posterior_uncertainty = (posterior_uncertainty + posterior_uncertainty.T) / 2
    return {
        "prior_returns": pi, "posterior_returns": posterior_mu,
        "prior_covariance": sigma,
        "posterior_mean_uncertainty": posterior_uncertainty,
        "view_residuals_before": q - p @ pi,
        "view_residuals_after": q - p @ posterior_mu,
        "view_covariance": omega, "tau": float(tau),
        "risk_aversion": float(risk_aversion),
    }


def optimise_black_litterman(posterior_returns, covariance, *, risk_aversion=3.0,
                             max_weight=0.35, previous_weights=None,
                             turnover_penalty=0.0):
    """Long-only mean-variance allocation with optional L1 turnover penalty."""
    mu = np.asarray(posterior_returns, dtype=float).reshape(-1)
    sigma = _validate_covariance(covariance)
    n = len(mu)
    if n == 0 or sigma.shape != (n, n) or not np.isfinite(mu).all():
        raise ValueError("Posterior returns and covariance dimensions must agree.")
    if risk_aversion <= 0 or turnover_penalty < 0:
        raise ValueError("Risk aversion must be positive and turnover penalty non-negative.")
    if not 0 < max_weight <= 1 or max_weight * n < 1:
        raise ValueError("max_weight is infeasible for the number of assets.")
    previous = None
    if previous_weights is not None:
        previous = np.asarray(previous_weights, dtype=float).reshape(-1)
        if len(previous) != n or not np.isfinite(previous).all() or (previous < 0).any():
            raise ValueError("Previous weights are invalid.")
        if not np.isclose(previous.sum(), 1.0, atol=1e-6):
            raise ValueError("Previous weights must sum to one.")

    def objective(w):
        utility = float(mu @ w - 0.5 * risk_aversion * (w @ sigma @ w))
        turnover = float(np.abs(w - previous).sum()) if previous is not None else 0.0
        return -utility + turnover_penalty * turnover

    result = minimize(objective, np.full(n, 1/n), method="SLSQP",
                      bounds=[(0.0, max_weight)] * n,
                      constraints=[{"type": "eq", "fun": lambda w: w.sum()-1.0}],
                      options={"maxiter": 2000, "ftol": 1e-12})
    if not result.success:
        raise RuntimeError(f"Black-Litterman optimisation failed: {result.message}")
    weights = np.maximum(result.x, 0)
    weights /= weights.sum()
    return {
        "weights": weights, "expected_return": float(mu @ weights),
        "volatility": float(np.sqrt(max(weights @ sigma @ weights, 0.0))),
        "utility": float(-result.fun),
        "turnover": float(np.abs(weights-previous).sum()) if previous is not None else None,
        "solver_success": bool(result.success),
        "objective": "BL posterior mean-variance utility with optional L1 turnover penalty",
    }
