"""
Tool wrappers used by the coordinator.

These are thin adapters around the deterministic statistical core. Each
returns a small JSON-ish dict plus a one-line `preview` and a `justification`
the renderer surfaces in the terminal.

We intentionally don't expose these to a free-form LLM tool-calling loop —
the coordinator drives them in a deterministic order, which is more reliable
and still feels agentic to the user because every step is announced with
*why*.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd

from data_utils import get_column_samples, get_year_columns, pivot_indicator_panel
from selector import select_admissible_models
from model_specs import MODEL_SPECS
from diagnostics import run_arima_diagnostics, run_did_diagnostics, run_ols_diagnostics
from models import (
    run_arima, run_diff_in_diff, run_entity_fixed_effects, run_exp_smoothing,
    run_first_difference, run_linear_trend, run_log_linear, run_log_log,
    run_median_quantile, run_ols, run_panel_ols, run_polynomial_ols,
    run_pooled_ols, run_random_walk, run_time_fixed_effects,
)
from llm import identify_unit_value, map_columns as llm_map_columns, parse_question as llm_parse_question


FORECAST_RUNNERS = {
    "arima": run_arima,
    "linear_trend": run_linear_trend,
    "exp_smoothing": run_exp_smoothing,
    "random_walk": run_random_walk,
}
REGRESSION_RUNNERS = {
    "diff_in_diff": run_diff_in_diff,
    "panel_ols": run_panel_ols,
    "entity_fe": run_entity_fixed_effects,
    "time_fe": run_time_fixed_effects,
    "first_difference": run_first_difference,
    "ols": run_ols,
    "pooled_ols": run_pooled_ols,
    "log_linear": run_log_linear,
    "log_log": run_log_log,
    "polynomial_ols": run_polynomial_ols,
    "median_quantile": run_median_quantile,
}


def _get_col(field) -> Optional[str]:
    if isinstance(field, dict):
        v = field.get("value")
        if isinstance(v, list):
            return v[0] if v else None
        return v
    if isinstance(field, list):
        return field[0] if field else None
    return field


def _get_extra_treatments(mapping_treatment) -> list[str]:
    """Return additional treatment columns beyond the primary one (multi-predictor questions)."""
    if isinstance(mapping_treatment, dict):
        v = mapping_treatment.get("value")
    else:
        v = mapping_treatment
    if isinstance(v, list) and len(v) > 1:
        return list(v[1:])
    return []


# ---------------------------------------------------------------------------
# parse_question
# ---------------------------------------------------------------------------

def parse_question(text: str) -> dict:
    intent = llm_parse_question(text) or {}
    if not intent:
        # local fallback so we never hard-fail
        intent = _fallback_parse(text)
    return intent


def _fallback_parse(text: str) -> dict:
    t = text.lower()
    if any(w in t for w in ("forecast", "predict", "project", "next year", "future")):
        qt = "forecast"
    elif any(w in t for w in ("effect", "impact", "cause", "affect", "caused")):
        qt = "causal_effect"
    else:
        qt = "association"
    return {"question_type": qt, "outcome": None, "treatment": None, "time": None, "unit": None}


# ---------------------------------------------------------------------------
# map_columns
# ---------------------------------------------------------------------------

def map_columns(intent: dict, df: pd.DataFrame, profile_text: str = "") -> dict:
    samples = get_column_samples(df)
    mapping = llm_map_columns(intent, samples) or {}
    return mapping


# ---------------------------------------------------------------------------
# prepare_data — pivot wide-indicator panels and filter to a unit if needed
# ---------------------------------------------------------------------------

def prepare_data(df: pd.DataFrame, mapping: dict, intent: dict) -> tuple[pd.DataFrame, dict]:
    """Returns (prepared_df, updated_intent)."""
    out_intent = dict(intent)
    out_intent["question"] = intent.get("question", "")

    outcome_val = _get_col(mapping.get("outcome"))
    treatment_val = _get_col(mapping.get("treatment"))

    if mapping.get("pivot") or isinstance(_get_col(mapping.get("time")), list):
        # Always use the best human-readable indicator column (not LLM's guess which
        # may pick machine-code columns like SERIES_CODE over INDICATOR).
        from data_utils import find_indicator_column as _find_ind
        detected_ind_col = _find_ind(df)
        indicator_col = detected_ind_col or mapping.get("indicator_column") or "SERIES_NAME"
        year_cols = mapping.get("year_columns") or get_year_columns(df)
        long_df, unit_col, ind_col = pivot_indicator_panel(
            df, indicator_col=indicator_col, year_cols=year_cols
        )

        outcome_df = treatment_df = None
        if outcome_val:
            mask = long_df[ind_col].astype(str).str.contains(re.escape(str(outcome_val)), case=False, na=False)
            outcome_df = long_df[mask][[unit_col, "year", "value"]].rename(columns={"value": str(outcome_val)})
        if treatment_val:
            mask = long_df[ind_col].astype(str).str.contains(re.escape(str(treatment_val)), case=False, na=False)
            treatment_df = long_df[mask][[unit_col, "year", "value"]].rename(columns={"value": str(treatment_val)})

        if outcome_df is not None and treatment_df is not None:
            new_df = outcome_df.merge(treatment_df, on=[unit_col, "year"], how="inner")
        elif outcome_df is not None:
            new_df = outcome_df
        else:
            new_df = long_df

        # filter to a specific unit if the user named one
        unit_desc = intent.get("unit_value")
        identified = None
        if unit_desc and unit_col in new_df.columns:
            identified = identify_unit_value(unit_desc, unit_col, new_df)
            if identified:
                new_df = new_df[new_df[unit_col] == identified].copy()
        # After filtering to a single unit, the data is no longer a panel —
        # downgrade to a time-series so the selector picks single-series models.
        effective_unit = None if identified else unit_col
        out_intent.update({
            "outcome": outcome_val, "treatment": treatment_val,
            "unit": effective_unit, "time": "year",
            "identified_unit": identified,
            "_panel_collapsed": bool(identified),
        })
        return new_df, out_intent

    # Tidy data: just update the intent with resolved column names.
    if outcome_val:
        out_intent["outcome"] = outcome_val
    if treatment_val:
        out_intent["treatment"] = treatment_val
    # Store additional predictors for multi-predictor comparison
    extra = _get_extra_treatments(mapping.get("treatment"))
    extra_valid = [c for c in extra if c and c in df.columns]
    if extra_valid:
        out_intent["_extra_treatments"] = extra_valid
    time_val = _get_col(mapping.get("time"))
    if time_val:
        out_intent["time"] = time_val
    unit_map = _get_col(mapping.get("unit"))
    if unit_map:
        out_intent["unit"] = unit_map

    # Filter to a specific unit if requested
    unit_desc = intent.get("unit_value")
    if unit_desc and out_intent.get("unit") and out_intent["unit"] in df.columns:
        identified = identify_unit_value(unit_desc, out_intent["unit"], df)
        if identified:
            df = df[df[out_intent["unit"]] == identified].copy()
            out_intent["identified_unit"] = identified
            # Collapsed to a single time series — drop unit so the right
            # selector branch fires (OLS / ARIMA / linear trend etc.).
            out_intent["unit"] = None
            out_intent["_panel_collapsed"] = True
    return df, out_intent


# ---------------------------------------------------------------------------
# select_model
# ---------------------------------------------------------------------------

def select_model(intent: dict, df: pd.DataFrame, override: Optional[str] = None) -> dict:
    valid, rejected = select_admissible_models(intent, df)
    if override:
        if override in valid:
            chosen = override
        elif override in rejected:
            return {
                "error": f"Override '{override}' cannot run: {rejected[override]}",
                "valid": valid, "rejected": rejected,
            }
        else:
            return {
                "error": f"Override '{override}' isn't valid for question type "
                         f"'{intent.get('question_type')}'.",
                "valid": valid, "rejected": rejected,
            }
    else:
        if not valid:
            return {"error": "No admissible model found", "valid": valid, "rejected": rejected}
        chosen = valid[0]
    return {
        "model_key": chosen,
        "display_name": MODEL_SPECS[chosen]["display_name"],
        "alternatives": [m for m in valid if m != chosen],
        "rejected": rejected,
    }


# ---------------------------------------------------------------------------
# run_diagnostics / run_model
# ---------------------------------------------------------------------------

def run_diagnostics(model_key: str, df: pd.DataFrame, intent: dict) -> dict:
    outcome = intent.get("outcome"); treatment = intent.get("treatment")
    time = intent.get("time"); unit = intent.get("unit")
    if model_key in FORECAST_RUNNERS:
        return run_arima_diagnostics(df, outcome, time)
    if model_key in ("diff_in_diff", "panel_ols", "first_difference", "entity_fe"):
        return run_did_diagnostics(df, outcome, treatment, time or "year", unit)
    return run_ols_diagnostics(df, outcome, treatment)


def run_model(model_key: str, df: pd.DataFrame, intent: dict, forecast_periods: int = 10) -> dict:
    outcome = intent.get("outcome"); treatment = intent.get("treatment")
    time = intent.get("time"); unit = intent.get("unit")
    if model_key in FORECAST_RUNNERS:
        result = FORECAST_RUNNERS[model_key](df, outcome, time, unit, forecast_periods=forecast_periods)
    elif model_key in ("diff_in_diff", "panel_ols", "first_difference"):
        result = REGRESSION_RUNNERS[model_key](df, outcome, treatment, time, unit)
    elif model_key == "entity_fe":
        result = REGRESSION_RUNNERS[model_key](df, outcome, treatment, unit)
    elif model_key == "time_fe":
        result = REGRESSION_RUNNERS[model_key](df, outcome, treatment, time)
    else:
        result = REGRESSION_RUNNERS[model_key](df, outcome, treatment)

    # Attach raw scatter + time-series data for terminal viz
    if model_key not in FORECAST_RUNNERS and "error" not in result:
        if treatment and outcome and treatment in df.columns and outcome in df.columns:
            try:
                # Paired scatter (same row = same observation, no separate dropna)
                paired = df[[treatment, outcome]].copy()
                paired[treatment] = pd.to_numeric(paired[treatment], errors="coerce")
                paired[outcome]   = pd.to_numeric(paired[outcome],   errors="coerce")
                paired = paired.dropna()
                if len(paired) > 600:
                    paired = paired.sample(600)   # random each run, no fixed seed
                result["_x_values"] = paired[treatment].tolist()
                result["_y_values"] = paired[outcome].tolist()
                result["x_mean"] = float(paired[treatment].mean())
                # Unit labels for color-coded scatter (panel data)
                if unit and unit in df.columns:
                    sub = df[[treatment, outcome, unit]].copy()
                    sub[treatment] = pd.to_numeric(sub[treatment], errors="coerce")
                    sub[outcome]   = pd.to_numeric(sub[outcome],   errors="coerce")
                    sub = sub.dropna(subset=[treatment, outcome])
                    if len(sub) > 600:
                        sub = sub.sample(600)
                    result["_unit_labels"] = sub[unit].astype(str).tolist()
                    result["_x_values"] = sub[treatment].tolist()
                    result["_y_values"] = sub[outcome].tolist()
            except Exception:
                pass

        # Time-series data: outcome over time — find best time column from df
        if outcome and outcome in df.columns:
            try:
                # Find a usable time column: try intent time, then datetime cols, then year-like
                time_col = None
                if time and time in df.columns:
                    time_col = time
                if not time_col:
                    for col in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[col]):
                            time_col = col; break
                if not time_col:
                    # fallback: any numeric column that looks like years
                    for col in df.columns:
                        try:
                            vals = pd.to_numeric(df[col], errors="coerce").dropna()
                            if len(vals) > 0 and 1800 <= vals.mean() <= 2100 and vals.std() < 50:
                                time_col = col; break
                        except Exception:
                            pass
                if time_col:
                    ts = df[[time_col, outcome]].copy()
                    ts[outcome] = pd.to_numeric(ts[outcome], errors="coerce")
                    ts = ts.dropna()
                    if pd.api.types.is_datetime64_any_dtype(ts[time_col]):
                        ts = ts.sort_values(time_col)
                        ts[time_col] = ts[time_col].dt.year  # convert to numeric year
                    ts = ts.groupby(time_col)[outcome].mean().reset_index()
                    result["_ts_times"] = ts[time_col].tolist()
                    result["_ts_values"] = ts[outcome].tolist()
            except Exception:
                pass
    return result


# ---------------------------------------------------------------------------
# Diagnostic-driven model switching
# ---------------------------------------------------------------------------

CORRECTIVE_SWITCH = {
    # If parallel trends fail in DiD, fall back to first-difference
    ("diff_in_diff", "parallel_trends"): "first_difference",
    # If panel_ols has bad pre-trends or autocorrelation, also fall back to FD
    ("panel_ols", "autocorrelation"): "first_difference",
}


def detect_critical_violations(diag: dict) -> list[str]:
    out = []
    for v in diag.get("violations", []):
        vl = v.lower()
        if "parallel trends" in vl:
            out.append("parallel_trends")
        if "autocorrelation" in vl or "ljung" in vl:
            out.append("autocorrelation")
    return out


def maybe_corrective_model(model_key: str, diag: dict, valid_alternatives: list[str]) -> Optional[str]:
    for v in detect_critical_violations(diag):
        alt = CORRECTIVE_SWITCH.get((model_key, v))
        if alt and alt in valid_alternatives:
            return alt
    return None
