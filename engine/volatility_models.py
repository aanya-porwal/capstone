"""Student-t GARCH(1,1) volatility estimation and risk forecasting.

Input is a one-dimensional series of daily simple returns in decimal units.
The conditional mean is demeaned; variance dynamics are estimated by MLE.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import t as student_t


def _unpack(theta):
    omega = float(np.exp(np.clip(theta[0], -30, 5)))
    a = np.exp(theta[1])
    b = np.exp(theta[2])
    denom = 1.0 + a + b
    alpha = float(0.999 * a / denom)
    beta = float(0.999 * b / denom)
    nu = float(2.05 + np.exp(np.clip(theta[3], -3, 5)))
    return omega, alpha, beta, nu


def _variance_path(eps, omega, alpha, beta, initial_variance):
    h = np.empty(len(eps), dtype=float)
    h[0] = max(float(initial_variance), 1e-12)
    for i in range(1, len(eps)):
        h[i] = omega + alpha * eps[i-1]**2 + beta * h[i-1]
    return np.maximum(h, 1e-12)


def _negative_log_likelihood(theta, eps, initial_variance):
    omega, alpha, beta, nu = _unpack(theta)
    h = _variance_path(eps, omega, alpha, beta, initial_variance)
    z2 = eps**2 / h
    # Student-t density scaled to unit variance.
    constant = (gammaln((nu+1)/2) - gammaln(nu/2)
                - 0.5*np.log(np.pi*(nu-2)))
    log_density = (constant - 0.5*np.log(h)
                   - ((nu+1)/2)*np.log1p(z2/(nu-2)))
    value = -float(np.sum(log_density))
    return value if np.isfinite(value) else 1e100


def fit_garch_t(returns, *, maxiter=3000):
    """Fit GARCH(1,1) with Student-t innovations by constrained MLE."""
    x = np.asarray(returns, dtype=float).reshape(-1)
    x = x[np.isfinite(x)]
    if len(x) < 100:
        raise ValueError("At least 100 finite daily returns are required.")
    if np.max(np.abs(x)) > 1.0:
        raise ValueError("Returns must be decimal values, not percentage points.")
    mean = float(x.mean())
    eps = x - mean
    variance = max(float(np.var(eps, ddof=1)), 1e-8)
    # Starting values: alpha=0.05, beta=0.90, nu=8.
    theta0 = np.array([np.log(variance*0.05), np.log(.05/.90),
                       np.log(.90/.05), np.log(6.0)])
    result = minimize(_negative_log_likelihood, theta0,
                      args=(eps, variance), method="L-BFGS-B",
                      options={"maxiter": int(maxiter), "ftol": 1e-10})
    if not result.success and not np.isfinite(result.fun):
        raise RuntimeError(f"GARCH estimation failed: {result.message}")
    omega, alpha, beta, nu = _unpack(result.x)
    h = _variance_path(eps, omega, alpha, beta, variance)
    persistence = alpha + beta
    long_run_variance = omega / max(1.0-persistence, 1e-8)
    return {
        "mean_daily": mean, "omega": omega, "alpha": alpha, "beta": beta,
        "persistence": persistence, "degrees_of_freedom": nu,
        "conditional_variance": h, "conditional_volatility": np.sqrt(h),\n        "last_innovation_squared": float(eps[-1]**2),
        "long_run_daily_variance": long_run_variance,
        "log_likelihood": -float(result.fun), "aic": float(2*4 + 2*result.fun),
        "observations": int(len(x)), "converged": bool(result.success),
        "optimizer_message": str(result.message),
        "model": "GARCH(1,1) with Student-t innovations",
    }


def forecast_garch_volatility(fit, horizon_days=21):
    """Analytical multi-step variance forecast, returned as daily and annualised vol."""
    if horizon_days < 1:
        raise ValueError("Forecast horizon must be positive.")
    alpha, beta = fit["alpha"], fit["beta"]
    persistence = alpha + beta
    h_next = (fit["omega"] + alpha*fit["conditional_variance"][-1]
              * 0 + beta*fit["conditional_variance"][-1])
    # The last observed shock is not stored separately; use last conditional variance
    # and the fitted long-run level for the multi-step recursion.
    long_run = fit["long_run_daily_variance"]
    forecasts = np.array([
        long_run + persistence**k * (h_next-long_run)
        for k in range(horizon_days)
    ])
    forecasts = np.maximum(forecasts, 1e-12)
    return {
        "horizon_days": int(horizon_days),
        "daily_volatility_forecast": np.sqrt(forecasts),
        "annualised_volatility_forecast": np.sqrt(forecasts*252),
        "terminal_annualised_volatility": float(np.sqrt(forecasts[-1]*252)),
        "long_run_annualised_volatility": float(np.sqrt(long_run*252)),
    }


def student_t_var_cvar(fit, confidence=0.95):
    """One-day parametric VaR/CVaR under fitted conditional Student-t innovations."""
    if not 0.5 < confidence < 1:
        raise ValueError("confidence must be between 0.5 and 1.")
    nu = fit["degrees_of_freedom"]
    sigma = float(fit["conditional_volatility"][-1])
    mean = fit["mean_daily"]
    # Standardise Student-t to unit variance.
    scale = np.sqrt((nu-2)/nu)
    q = float(student_t.ppf(1-confidence, df=nu)*scale)
    density = float(student_t.pdf(q/scale, df=nu)/scale)
    # Expected lower-tail return for standardised Student-t.
    tail_mean = -density * (nu + (q/scale)**2) / ((nu-1)*(1-confidence)) * scale
    var_loss = -(mean + sigma*q)
    cvar_loss = -(mean + sigma*tail_mean)
    return {
        "confidence": float(confidence), "var": float(var_loss),
        "cvar": float(cvar_loss), "conditional_sigma": sigma,
        "degrees_of_freedom": float(nu),
        "method": "parametric one-day Student-t conditional tail risk",
    }
