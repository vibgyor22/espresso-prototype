"""
What-if / scenario simulation.

Two surfaces use this:
  - The REPL command `what if treatment = 12` (one-shot, local computation).
  - The HTML report's slider widget (same math, executed client-side from the
    coefficients we embed; this module also generates that embedded JSON).

The math is deliberately simple — we never let the LLM compute. Predictions and
intervals come from the stored model coefficients and standard errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class WhatIfResult:
    scenario: dict
    predicted: float
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    delta_vs_baseline: Optional[float] = None
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "predicted": self.predicted,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "delta_vs_baseline": self.delta_vs_baseline,
            "explanation": self.explanation,
        }


# ---------------------------------------------------------------------------
# Regression: y_hat = intercept + slope * x  (with SE propagation)
# ---------------------------------------------------------------------------

def regression_predict(
    result: dict, x_value: float, x_mean: Optional[float] = None
) -> WhatIfResult:
    """Predict outcome at a chosen predictor value from a stored regression result."""
    intercept = result.get("intercept", 0.0) or 0.0
    slope = result.get("slope", result.get("treatment_effect", result.get("effect", 0.0))) or 0.0
    se = result.get("se", 0.0) or 0.0

    y_hat = intercept + slope * x_value
    ci_lo = y_hat - 1.96 * se * abs(x_value if x_mean is None else (x_value - x_mean))
    ci_hi = y_hat + 1.96 * se * abs(x_value if x_mean is None else (x_value - x_mean))

    baseline_x = x_mean if x_mean is not None else 0.0
    baseline_y = intercept + slope * baseline_x

    return WhatIfResult(
        scenario={"x": x_value},
        predicted=y_hat,
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        delta_vs_baseline=y_hat - baseline_y,
        explanation=(
            f"At predictor = {x_value:g}, predicted outcome is {y_hat:,.4f}. "
            f"Compared to baseline ({baseline_x:g}), that's a shift of "
            f"{y_hat - baseline_y:+,.4f}."
        ),
    )


# ---------------------------------------------------------------------------
# ARIMA / forecast: shift the last observed value, re-walk the forecast
# ---------------------------------------------------------------------------

def forecast_shock(result: dict, shock: float) -> WhatIfResult:
    """Apply a one-period additive shock to the most recent value and re-forecast."""
    last = result.get("last_value", 0.0) or 0.0
    forecasts = list(result.get("forecasts", []) or [])
    ar1 = result.get("ar1_coef", 0.0) or 0.0

    shocked_last = last + shock
    # Simple AR(1) propagation: shock decays by ar1 each step.
    new_forecasts = []
    decay = 1.0
    for i, f in enumerate(forecasts):
        new_forecasts.append(f + shock * decay)
        decay *= ar1 if abs(ar1) < 1 else 0.0

    return WhatIfResult(
        scenario={"shock": shock, "shocked_last": shocked_last},
        predicted=new_forecasts[0] if new_forecasts else shocked_last,
        delta_vs_baseline=shock,
        explanation=(
            f"Applying a one-period shock of {shock:+.4f} to the last observed "
            f"value ({last:,.4f} → {shocked_last:,.4f}) shifts the next-period "
            f"forecast by approximately {shock:+.4f}; the impact decays at "
            f"rate {ar1:.2f} thereafter."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch + JSON for HTML slider
# ---------------------------------------------------------------------------

def simulate(model_result: dict, scenario: dict) -> WhatIfResult:
    """Top-level entry. Picks the right simulator based on what's in `scenario`."""
    if "shock" in scenario:
        return forecast_shock(model_result, float(scenario["shock"]))
    if "x" in scenario or "treatment_value" in scenario:
        x = float(scenario.get("x", scenario.get("treatment_value")))
        return regression_predict(model_result, x, scenario.get("x_mean"))
    raise ValueError("Unrecognized scenario; expected one of {x, treatment_value, shock}")


def html_payload(model_result: dict, model_key: str) -> dict[str, Any]:
    """
    Build the JSON payload the HTML report embeds so the slider can compute
    predictions in the browser without a server round-trip.
    """
    is_forecast = model_key in {"arima", "linear_trend", "exp_smoothing", "random_walk"}
    if is_forecast:
        last = model_result.get("last_value", 0.0) or 0.0
        return {
            "kind": "forecast",
            "last_value": last,
            "forecasts": list(model_result.get("forecasts", []) or []),
            "ar1": model_result.get("ar1_coef", 0.0) or 0.0,
            "ci_lower": list(model_result.get("ci_lower", []) or []),
            "ci_upper": list(model_result.get("ci_upper", []) or []),
        }
    intercept = model_result.get("intercept", 0.0) or 0.0
    slope = (
        model_result.get("slope")
        or model_result.get("treatment_effect")
        or model_result.get("effect")
        or 0.0
    )
    se = model_result.get("se", 0.0) or 0.0
    return {
        "kind": "regression",
        "intercept": intercept,
        "slope": slope,
        "se": se,
        "x_mean": model_result.get("x_mean"),
    }
