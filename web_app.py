"""
Espresso web UI.

Run:
    python web_app.py

Then open:
    http://127.0.0.1:5000
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from data_utils import get_column_samples, get_year_columns, load_data, pivot_indicator_panel
from diagnostics import run_arima_diagnostics, run_did_diagnostics, run_ols_diagnostics
from html_report import create_html_report
from interpretation import interpret_diagnostics, interpret_results
from model_specs import MODEL_SPECS
from models import (
    run_arima,
    run_diff_in_diff,
    run_entity_fixed_effects,
    run_exp_smoothing,
    run_first_difference,
    run_linear_trend,
    run_log_linear,
    run_log_log,
    run_median_quantile,
    run_ols,
    run_panel_ols,
    run_polynomial_ols,
    run_pooled_ols,
    run_random_walk,
    run_time_fixed_effects,
)
from selector import select_admissible_models


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR = BASE_DIR / "uploads"

OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


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


def _get_col_val(mapping_field):
    if isinstance(mapping_field, dict):
        return mapping_field.get("value")
    return mapping_field


def _model_label(model_name):
    return MODEL_SPECS.get(model_name, {}).get("display_name", model_name)


def _json_ready(value):
    """Convert pandas/numpy values into JSON-safe Python primitives."""
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [_json_ready(v) for v in value]
    if not isinstance(value, (dict, list, tuple, str, bytes)):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _profile_dataframe(df):
    year_cols = get_year_columns(df)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    likely_unit = next(
        (c for c in df.columns if c.lower() in {"country", "unit", "state", "firm", "entity"}),
        None,
    )
    likely_time = next(
        (c for c in df.columns if c.lower() in {"year", "time", "date", "period"}),
        None,
    )
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": df.columns.tolist(),
        "numeric_columns": numeric_cols,
        "year_columns": year_cols,
        "likely_unit": likely_unit,
        "likely_time": likely_time,
        "is_wide_indicator": bool(year_cols),
        "preview": df.head(8).fillna("").to_dict(orient="records"),
    }


def _bundled_datasets():
    datasets = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(path, nrows=50)
            profile = _profile_dataframe(df)
        except Exception:
            profile = {"rows": 0, "columns": 0, "column_names": []}
        datasets.append({
            "id": path.name,
            "name": path.name,
            "rows": profile.get("rows", 0),
            "columns": profile.get("columns", 0),
            "column_names": profile.get("column_names", []),
        })
    return datasets


def _fallback_intent(question, df):
    """Best-effort parser used when Gemini is unavailable."""
    q = question.lower()
    cols = df.columns.tolist()
    lower_to_col = {c.lower(): c for c in cols}

    if any(word in q for word in ["forecast", "predict", "project", "future", "next"]):
        qtype = "forecast"
    elif any(word in q for word in ["effect", "impact", "cause", "affect", "treatment"]):
        qtype = "causal_effect"
    else:
        qtype = "association"

    def mentioned(candidates):
        for c in candidates:
            if c.lower() in q:
                return c
        return None

    outcome = mentioned(cols)
    treatment = None
    for c in cols:
        if c == outcome:
            continue
        if c.lower() in q:
            treatment = c
            break

    if not outcome:
        numeric = df.select_dtypes(include="number").columns.tolist()
        outcome = next((c for c in numeric if c.lower() not in {"year", "time"}), None)
    if not treatment and qtype != "forecast":
        treatment = (
            lower_to_col.get("treatment")
            or lower_to_col.get("interest_rate")
            or next((c for c in df.select_dtypes(include="number").columns if c != outcome), None)
        )

    return {
        "question_type": qtype,
        "outcome": outcome,
        "treatment": treatment,
        "time": lower_to_col.get("year") or lower_to_col.get("time") or lower_to_col.get("date"),
        "unit": lower_to_col.get("country") or lower_to_col.get("unit") or lower_to_col.get("state"),
        "unit_value": None,
        "forecast_periods": 5 if qtype == "forecast" else None,
        "pre_period": None,
    }


def _fallback_mapping(intent, df):
    cols = df.columns.tolist()
    lower_to_col = {c.lower(): c for c in cols}

    def resolve(value):
        if not value:
            return None
        return lower_to_col.get(str(value).lower(), value if value in cols else None)

    return {
        "outcome": {"type": "column", "value": resolve(intent.get("outcome"))},
        "treatment": {"type": "column", "value": resolve(intent.get("treatment"))},
        "time": {"type": "column", "value": resolve(intent.get("time"))},
        "unit": {"type": "column", "value": resolve(intent.get("unit"))},
        "pivot": False,
        "indicator_column": None,
        "year_columns": None,
        "notes": "Local fallback mapping",
    }


def _parse_and_map(question, df):
    try:
        from llm import identify_unit_value, map_columns, parse_question
    except Exception:
        identify_unit_value = None
        map_columns = None
        parse_question = None

    intent = parse_question(question) if parse_question else None
    if not intent:
        intent = _fallback_intent(question, df)
    intent["question"] = question

    mapping = map_columns(intent, get_column_samples(df)) if map_columns else None
    if not mapping or not mapping.get("outcome"):
        mapping = _fallback_mapping(intent, df)

    unit_value_desc = intent.get("unit_value")
    unit_col_name = _get_col_val(mapping.get("unit"))
    if unit_value_desc and unit_col_name and unit_col_name in df.columns and identify_unit_value:
        identified_unit = identify_unit_value(unit_value_desc, unit_col_name, df)
        if identified_unit:
            intent["identified_unit"] = identified_unit
            intent["unit_column"] = unit_col_name

    return intent, mapping


def _prepare_data(df, intent, mapping):
    outcome_val = _get_col_val(mapping.get("outcome"))
    treatment_val = _get_col_val(mapping.get("treatment"))

    if mapping.get("pivot") or isinstance(_get_col_val(mapping.get("time")), list):
        indicator_col = mapping.get("indicator_column") or "SERIES_NAME"
        year_cols = mapping.get("year_columns") or get_year_columns(df)
        long_df, unit_col, ind_col = pivot_indicator_panel(
            df, indicator_col=indicator_col, year_cols=year_cols
        )

        outcome_df = treatment_df = None
        if outcome_val:
            mask = long_df[ind_col].astype(str).str.contains(
                re.escape(str(outcome_val)), case=False, na=False
            )
            outcome_df = long_df[mask][[unit_col, "year", "value"]].rename(
                columns={"value": str(outcome_val)}
            )
        if treatment_val:
            mask = long_df[ind_col].astype(str).str.contains(
                re.escape(str(treatment_val)), case=False, na=False
            )
            treatment_df = long_df[mask][[unit_col, "year", "value"]].rename(
                columns={"value": str(treatment_val)}
            )

        if outcome_df is not None and treatment_df is not None:
            df = outcome_df.merge(treatment_df, on=[unit_col, "year"], how="inner")
        elif outcome_df is not None:
            df = outcome_df

        if intent.get("identified_unit") and unit_col in df.columns:
            df = df[df[unit_col] == intent["identified_unit"]].copy()

        intent.update({
            "outcome": outcome_val,
            "treatment": treatment_val,
            "unit": unit_col,
            "time": "year",
        })
        return df, intent

    if outcome_val:
        intent["outcome"] = outcome_val
    if treatment_val:
        intent["treatment"] = treatment_val
    time_val = _get_col_val(mapping.get("time"))
    unit_val = _get_col_val(mapping.get("unit"))
    if time_val:
        intent["time"] = time_val
    if unit_val:
        intent["unit"] = unit_val
    return df, intent


def _run_selected_model(df, intent, model_name, forecast_periods=None):
    outcome_col = intent.get("outcome")
    treatment_col = intent.get("treatment")
    time_col = intent.get("time")
    unit_col = intent.get("unit")
    args = SimpleNamespace(question=intent.get("question"), forecast_periods=forecast_periods)

    if model_name in FORECAST_RUNNERS:
        diag = run_arima_diagnostics(df, outcome_col, time_col)
        result = FORECAST_RUNNERS[model_name](
            df,
            outcome_col,
            time_col,
            unit_col,
            forecast_periods=forecast_periods or intent.get("forecast_periods") or 5,
        )
        if "error" in result:
            raise ValueError(result["error"])
        interp = interpret_results(
            args.question,
            outcome_col,
            None,
            model_name,
            result,
            diag,
            unit_name=intent.get("identified_unit"),
            unit_description=intent.get("unit_value"),
        )
        order = result.get("arima_order", (1, 0, 0))
        model_label = f"ARIMA{order}" if model_name == "arima" else _model_label(model_name)
        return {
            "model": model_label,
            "model_key": model_name,
            "forecasts": result.get("forecasts", []),
            "forecast_times": result.get("forecast_times", []),
            "ci_lower": result.get("ci_lower", []),
            "ci_upper": result.get("ci_upper", []),
            "historical_values": result.get("historical_values", []),
            "historical_times": result.get("historical_times", []),
            "last_value": result.get("last_value"),
            "rmse": result.get("rmse"),
            "n_obs": result.get("n_obs"),
            "aic": result.get("aic"),
            "engine": result.get("engine"),
            "llm_interpretation": interp,
            "diagnostics": diag,
        }

    if model_name in ("diff_in_diff", "panel_ols", "entity_fe", "first_difference") and unit_col and time_col:
        diag = run_did_diagnostics(df, outcome_col, treatment_col, time_col, unit_col)
    else:
        diag = run_ols_diagnostics(df, outcome_col, treatment_col)

    runner = REGRESSION_RUNNERS[model_name]
    if model_name in ("diff_in_diff", "panel_ols", "first_difference"):
        result = runner(df, outcome_col, treatment_col, time_col, unit_col)
    elif model_name == "entity_fe":
        result = runner(df, outcome_col, treatment_col, unit_col)
    elif model_name == "time_fe":
        result = runner(df, outcome_col, treatment_col, time_col)
    else:
        result = runner(df, outcome_col, treatment_col)

    if "error" in result:
        raise ValueError(result["error"])

    effect = result.get("treatment_effect", result.get("effect", result.get("slope", 0)))
    se = result.get("se", 0) or 0
    pval = result.get("pvalue", 1) or 1
    interp = interpret_results(
        args.question,
        outcome_col,
        treatment_col,
        model_name,
        result,
        diag,
        unit_name=intent.get("identified_unit"),
        unit_description=intent.get("unit_value"),
    )

    return {
        "model": _model_label(model_name),
        "model_key": model_name,
        "effect": effect,
        "se": se,
        "p_value": pval,
        "ci_lower": result.get("ci_lower", effect - 1.96 * se),
        "ci_upper": result.get("ci_upper", effect + 1.96 * se),
        "r_squared": result.get("r_squared"),
        "n_obs": result.get("n_obs"),
        "n_units": result.get("n_units"),
        "n_periods": result.get("n_periods"),
        "fe_type": result.get("fe_type", ""),
        "se_type": result.get("se_type", ""),
        "llm_interpretation": interp,
        "diagnostics": diag,
    }


def run_web_analysis(data_path, question, model_override=None, forecast_periods=None):
    df = load_data(data_path)
    intent, mapping = _parse_and_map(question, df)
    prepared_df, intent = _prepare_data(df, intent, mapping)
    valid_models, rejected = select_admissible_models(intent, prepared_df)

    if not valid_models:
        raise ValueError("No valid model found for this question and dataset.")

    if model_override:
        if model_override not in valid_models:
            reason = rejected.get(model_override, "model does not match this question/data")
            raise ValueError(f"Requested model '{model_override}' cannot run: {reason}")
        model_name = model_override
    else:
        model_name = valid_models[0]

    result_record = _run_selected_model(prepared_df, intent, model_name, forecast_periods)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = OUTPUT_DIR / f"espresso_report_{ts}.html"
    report_path = create_html_report(
        str(output_path),
        intent,
        mapping,
        [result_record],
        data_sample=prepared_df.head(200),
    )

    diagnostics = result_record.get("diagnostics", {})
    return {
        "intent": intent,
        "mapping": mapping,
        "selected_model": model_name,
        "selected_model_label": _model_label(model_name),
        "valid_models": valid_models,
        "rejected_models": rejected,
        "result": result_record,
        "diagnostics_text": interpret_diagnostics(diagnostics),
        "report_url": f"/reports/{Path(report_path).name}",
        "data_profile": _profile_dataframe(prepared_df),
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        models=[
            {"key": key, "name": spec["display_name"], "type": spec["question_type"]}
            for key, spec in MODEL_SPECS.items()
        ],
        datasets=_bundled_datasets(),
    )


@app.route("/api/datasets")
def api_datasets():
    return jsonify({"datasets": _bundled_datasets()})


@app.route("/api/datasets/<dataset_id>")
def api_dataset_profile(dataset_id):
    safe_name = secure_filename(dataset_id)
    path = DATA_DIR / safe_name
    if not path.exists():
        return jsonify({"error": "Dataset not found"}), 404
    return jsonify(_profile_dataframe(pd.read_csv(path)))


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        question = request.form.get("question", "").strip()
        model = request.form.get("model") or None
        forecast_periods_raw = request.form.get("forecast_periods", "").strip()
        forecast_periods = int(forecast_periods_raw) if forecast_periods_raw else None

        if not question:
            return jsonify({"error": "Please enter a research question."}), 400

        uploaded = request.files.get("dataset_file")
        dataset_choice = request.form.get("dataset_choice")

        if uploaded and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            if not filename.lower().endswith(".csv"):
                return jsonify({"error": "Please upload a CSV file."}), 400
            data_path = UPLOAD_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{filename}"
            uploaded.save(data_path)
        elif dataset_choice:
            data_path = DATA_DIR / secure_filename(dataset_choice)
            if not data_path.exists():
                return jsonify({"error": "Selected dataset was not found."}), 400
        else:
            return jsonify({"error": "Choose a bundled dataset or upload a CSV file."}), 400

        result = run_web_analysis(data_path, question, model, forecast_periods)
        return jsonify(_json_ready(result))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/reports/<filename>")
def reports(filename):
    return send_from_directory(OUTPUT_DIR, secure_filename(filename))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
