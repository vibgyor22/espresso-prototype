"""
What-if engine tests. Predictions and CIs are closed-form, so we can compare
exactly.
"""

from __future__ import annotations

import math

from espresso.whatif import regression_predict, forecast_shock, simulate, html_payload


def test_regression_predict_basic():
    result = {"intercept": 2.0, "slope": 0.5, "se": 0.1}
    wi = regression_predict(result, x_value=10.0, x_mean=5.0)
    # y_hat = 2 + 0.5 * 10 = 7
    assert math.isclose(wi.predicted, 7.0, rel_tol=1e-9)
    # baseline at x_mean=5 → 2 + 2.5 = 4.5
    assert math.isclose(wi.delta_vs_baseline, 7.0 - 4.5, rel_tol=1e-9)
    # CI half-width = 1.96 * 0.1 * |10 - 5| = 0.98
    assert math.isclose(wi.ci_lower, 7.0 - 0.98, abs_tol=1e-9)
    assert math.isclose(wi.ci_upper, 7.0 + 0.98, abs_tol=1e-9)


def test_regression_predict_from_treatment_effect_field():
    # Many runners store the slope under different keys; the simulator should cope.
    result = {"intercept": 1.0, "treatment_effect": 0.25, "se": 0.0}
    wi = regression_predict(result, x_value=4.0)
    assert math.isclose(wi.predicted, 1.0 + 0.25 * 4.0)


def test_forecast_shock_decays_with_ar1():
    result = {
        "last_value": 10.0,
        "forecasts": [11.0, 11.5, 12.0],
        "ar1_coef": 0.5,
    }
    wi = forecast_shock(result, shock=2.0)
    # First-period shifted forecast = 11 + 2*1.0 = 13
    assert math.isclose(wi.predicted, 13.0)
    # Explanation mentions decay
    assert "decays" in wi.explanation


def test_simulate_dispatches_correctly():
    reg = {"intercept": 0.0, "slope": 1.0, "se": 0.0}
    out = simulate(reg, {"x": 5})
    assert math.isclose(out.predicted, 5.0)

    fc = {"last_value": 0.0, "forecasts": [1.0], "ar1_coef": 0.0}
    out = simulate(fc, {"shock": 3.0})
    assert math.isclose(out.predicted, 4.0)


def test_simulate_rejects_unknown_scenario():
    try:
        simulate({}, {"frob": 1})
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_html_payload_regression():
    p = html_payload({"intercept": 1.0, "slope": 2.0, "se": 0.5, "x_mean": 3.0}, "ols")
    assert p["kind"] == "regression"
    assert p["intercept"] == 1.0
    assert p["slope"] == 2.0
    assert p["x_mean"] == 3.0


def test_html_payload_forecast():
    p = html_payload({"last_value": 5.0, "forecasts": [6.0, 7.0], "ar1_coef": 0.3}, "arima")
    assert p["kind"] == "forecast"
    assert p["forecasts"] == [6.0, 7.0]
    assert p["ar1"] == 0.3
