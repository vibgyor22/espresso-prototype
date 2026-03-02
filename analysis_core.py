"""
Core analysis pipeline for Espresso, suitable for use from APIs and the CLI.

This module mirrors the logic in `run_analysis.py` but returns structured
JSON-friendly results instead of printing to stdout.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from data_utils import load_data, get_column_samples, pivot_indicator_panel, get_year_columns
from diagnostics import run_arima_diagnostics, run_did_diagnostics
from html_report import create_html_report
from interpretation import interpret_results, interpret_diagnostics
from llm import parse_question, map_columns, identify_unit_value
from models import run_arima, run_diff_in_diff
from selector import select_admissible_models


def _apply_mapping_and_pivot(
    df,
    intent: Dict[str, Any],
    mapping: Optional[Dict[str, Any]],
) -> Tuple[Any, Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Apply LLM-driven column mapping and any required pivoting/wide→long transforms.

    Returns:
        (transformed_df, updated_intent, mapping_used)
    """
    if not mapping:
        return df, intent, mapping

    outcome_val = (
        mapping.get("outcome", {}).get("value")
        if isinstance(mapping.get("outcome"), dict)
        else mapping.get("outcome")
    )
    treatment_val = (
        mapping.get("treatment", {}).get("value")
        if isinstance(mapping.get("treatment"), dict)
        else mapping.get("treatment")
    )

    # Identify specific unit if a description was provided
    unit_value_desc = intent.get("unit_value")
    identified_unit = None

    if unit_value_desc:
        unit_col_mapping = mapping.get("unit", {})
        if isinstance(unit_col_mapping, dict):
            unit_col_name = unit_col_mapping.get("value")
        else:
            unit_col_name = unit_col_mapping

        if unit_col_name and unit_col_name in df.columns:
            identified_unit = identify_unit_value(unit_value_desc, unit_col_name, df)
            if identified_unit:
                intent["identified_unit"] = identified_unit
                intent["unit_column"] = unit_col_name

    # Handle pivoting if needed (indicator-style datasets)
    if mapping.get("pivot") or isinstance(mapping.get("time", {}).get("value"), list):
        indicator_col = mapping.get("indicator_column", "SERIES_NAME")
        year_cols = mapping.get("year_columns") or get_year_columns(df)

        long_df, unit_col, ind_col = pivot_indicator_panel(
            df, indicator_col=indicator_col, year_cols=year_cols
        )

        # Extract outcome and treatment series
        import re

        if outcome_val:
            outcome_df = long_df[
                long_df[ind_col]
                .astype(str)
                .str.contains(re.escape(str(outcome_val)), case=False, na=False)
            ]
            outcome_df = outcome_df[[unit_col, "year", "value"]].rename(
                columns={"value": str(outcome_val)}
            )
        else:
            outcome_df = None

        if treatment_val:
            treatment_df = long_df[
                long_df[ind_col]
                .astype(str)
                .str.contains(re.escape(str(treatment_val)), case=False, na=False)
            ]
            treatment_df = treatment_df[[unit_col, "year", "value"]].rename(
                columns={"value": str(treatment_val)}
            )
        else:
            treatment_df = None

        if outcome_df is not None and treatment_df is not None:
            df = outcome_df.merge(treatment_df, on=[unit_col, "year"], how="inner")
        elif outcome_df is not None:
            df = outcome_df

        # Filter to specific unit if identified
        identified_unit = intent.get("identified_unit")
        if identified_unit and unit_col in df.columns:
            df = df[df[unit_col] == identified_unit].copy()

        # Update intent to refer to concrete column names
        intent["outcome"] = outcome_val
        intent["treatment"] = treatment_val
        intent["unit"] = unit_col
        intent["time"] = "year"
    else:
        # No pivot required – assume data is already in a column-per-variable format
        pass

    return df, intent, mapping


def _build_spec_summary(intent: Dict[str, Any], model: str) -> str:
    """
    Human-readable summary of the model specification inferred from the question
    and column mapping. This is returned to the console so users can see
    exactly what was estimated.
    """
    outcome = intent.get("outcome") or "<outcome>"
    treatment = intent.get("treatment")
    time = intent.get("time") or "<time>"
    unit = intent.get("unit") or "<unit>"
    forecast_periods = intent.get("forecast_periods", 10)

    if model == "arima":
        return (
            f"AR(1) time-series forecast of '{outcome}' over '{time}' "
            f"(aggregated across '{unit}' if present), forecasting the next "
            f"{forecast_periods} periods."
        )

    if model == "diff_in_diff":
        treat_str = treatment or "<treatment>"
        return (
            f"Difference-in-differences regression on panel data with outcome '{outcome}', "
            f"treatment '{treat_str}', time index '{time}', and unit '{unit}'. "
            "Specification: outcome_it = α + β·(treated_i × post_t) + γ·treated_i + δ·post_t + ε_it, "
            "where β is reported as the treatment effect."
        )

    return f"Model '{model}' with outcome '{outcome}', time '{time}', unit '{unit}'."


def analyze_dataset(
    data_path: str,
    question: str,
) -> Dict[str, Any]:
    """
    High-level analysis entry point for use by the API layer.

    Steps:
      1. Load data
      2. Parse question with LLM
      3. Map logical fields to columns with LLM
      4. Optionally pivot/reshape data
      5. Select admissible model(s)
      6. Run diagnostics and estimation
      7. Generate HTML report

    Returns:
        JSON-serializable dict with:
        - intent
        - mapping
        - selected_model
        - diagnostics
        - model_results (per-model)
        - html_report_path
    """
    # 1. Load data
    df = load_data(data_path)

    # 2. Parse question
    intent = parse_question(question)
    if not intent:
        raise RuntimeError("Could not parse question")

    intent["question"] = question

    # 3. Map columns
    samples = get_column_samples(df)
    mapping = map_columns(intent, samples)

    # 4. Apply mapping and optional pivot
    df_transformed, intent, mapping_used = _apply_mapping_and_pivot(df, intent, mapping)

    outcome_col = intent.get("outcome")
    treatment_col = intent.get("treatment")
    time_col = intent.get("time")
    unit_col = intent.get("unit")
    forecast_periods = intent.get("forecast_periods", 10)

    # 5. Select model
    models, rejected = select_admissible_models(intent, df_transformed)
    if not models:
        raise RuntimeError(f"No valid models found. Rejected: {rejected}")

    model = models[0]

    model_results: List[Dict[str, Any]] = []
    diagnostics_block: Optional[Dict[str, Any]] = None

    # 6. Run diagnostics + estimation
    if model == "arima":
        identified_unit = intent.get("identified_unit")
        unit_description = intent.get("unit_value")

        diag = run_arima_diagnostics(df_transformed, outcome_col, time_col)
        diagnostics_block = {
            "model": "ARIMA (AR(1))",
            "diagnostics": diag,
            "text": interpret_diagnostics(diag),
        }

        result = run_arima(
            df_transformed,
            outcome_col,
            time_col,
            unit_col,
            forecast_periods=forecast_periods,
        )
        if "error" in result:
            raise RuntimeError(result["error"])

        interp = interpret_results(
            question,
            outcome_col,
            None,
            "arima",
            result,
            diag,
            unit_name=identified_unit,
            unit_description=unit_description,
        )

        result_block = {
            "model": "ARIMA (AR(1))",
            "results": result,
            "llm_interpretation": interp,
            "diagnostics": diag,
        }
        model_results.append(result_block)

    elif model == "diff_in_diff":
        diag = run_did_diagnostics(
            df_transformed, outcome_col, treatment_col, time_col, unit_col
        )
        diagnostics_block = {
            "model": "Difference-in-Differences",
            "diagnostics": diag,
            "text": interpret_diagnostics(diag),
        }

        result = run_diff_in_diff(
            df_transformed, outcome_col, treatment_col, time_col, unit_col
        )
        if "error" in result:
            raise RuntimeError(result["error"])

        identified_unit = intent.get("identified_unit")
        unit_description = intent.get("unit_value")

        interp = interpret_results(
            question,
            outcome_col,
            treatment_col,
            "diff_in_diff",
            result,
            diag,
            unit_name=identified_unit,
            unit_description=unit_description,
        )

        result_block = {
            "model": "Difference-in-Differences",
            "results": result,
            "llm_interpretation": interp,
            "diagnostics": diag,
        }
        model_results.append(result_block)

    # 7. HTML report
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = f"outputs/espresso_report_{ts}.html"
    html_path = create_html_report(
        out_path, intent, mapping_used or {}, model_results, data_sample=df_transformed.head(200)
    )

    spec_summary = _build_spec_summary(intent, model)

    return {
        "intent": intent,
        "mapping": mapping_used or {},
        "selected_model": model,
        "rejected_models": rejected,
        "model_results": model_results,
        "diagnostics_overview": diagnostics_block,
        "html_report_path": html_path,
        "spec_summary": spec_summary,
    }


