import numpy as np
import pytest
from engine.volatility_models import fit_garch_t, forecast_garch_volatility, student_t_var_cvar


def test_garch_fit_returns_valid_persistent_parameters():
    rng = np.random.default_rng(12)
    x = rng.standard_t(7, 1500) * .01
    fit = fit_garch_t(x)
    assert fit["observations"] == 1500
    assert fit["omega"] > 0
    assert fit["alpha"] >= 0 and fit["beta"] >= 0
    assert 0 < fit["persistence"] < .999
    assert fit["degrees_of_freedom"] > 2


def test_garch_forecast_converges_towards_long_run_volatility():
    rng = np.random.default_rng(4)
    fit = fit_garch_t(rng.normal(0, .01, 800))
    forecast = forecast_garch_volatility(fit, horizon_days=1000)
    assert len(forecast["daily_volatility_forecast"]) == 1000
    assert forecast["terminal_annualised_volatility"] == pytest.approx(
        forecast["long_run_annualised_volatility"], rel=.03
    )


def test_student_t_tail_risk_is_ordered():
    fit = fit_garch_t(np.random.default_rng(8).standard_t(6, 1000)*.012)
    risk = student_t_var_cvar(fit, .95)
    assert risk["cvar"] >= risk["var"] > 0


def test_garch_rejects_short_or_percent_unit_series():
    with pytest.raises(ValueError, match="100"):
        fit_garch_t(np.ones(50)*.01)
    with pytest.raises(ValueError, match="decimal"):
        fit_garch_t(np.ones(150)*1.2)
