"""
Espresso CLI — end-to-end statistical analysis pipeline.

Usage:
    python run_analysis.py --data path/to/data.csv --question "your question"

Pipeline:
  1. Load data
  2. Parse question (LLM)
  3. Map columns (LLM)
  4. Transform data (pivot if needed, filter to unit)
  5. Select statistical model
  6. Run diagnostics
  7. Run model
  8. Interpret results (LLM)
  9. Generate HTML report
"""

import argparse
import sys
import warnings
warnings.filterwarnings('ignore')

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from data_utils import load_data, get_column_samples, pivot_indicator_panel, get_year_columns
from selector import select_admissible_models
from diagnostics import (
    run_arima_diagnostics, run_did_diagnostics,
    run_ols_diagnostics
)
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
from html_report import create_html_report
from datetime import datetime, timezone


FORECAST_RUNNERS = {
    'arima': run_arima,
    'linear_trend': run_linear_trend,
    'exp_smoothing': run_exp_smoothing,
    'random_walk': run_random_walk,
}

REGRESSION_RUNNERS = {
    'diff_in_diff': run_diff_in_diff,
    'panel_ols': run_panel_ols,
    'entity_fe': run_entity_fixed_effects,
    'time_fe': run_time_fixed_effects,
    'first_difference': run_first_difference,
    'ols': run_ols,
    'pooled_ols': run_pooled_ols,
    'log_linear': run_log_linear,
    'log_log': run_log_log,
    'polynomial_ols': run_polynomial_ols,
    'median_quantile': run_median_quantile,
}


MODEL_DISPLAY_NAMES = {
    name: spec['display_name'] for name, spec in MODEL_SPECS.items()
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_col_val(mapping_field):
    """Extract a column name from a mapping entry that may be a dict or string."""
    if isinstance(mapping_field, dict):
        return mapping_field.get('value')
    return mapping_field


def _print_header(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def _print_section(title):
    print(f"\n{title}")
    print('-' * 70)


# ---------------------------------------------------------------------------
# Model runners (each returns a results dict ready for html_report)
# ---------------------------------------------------------------------------

def _run_forecast_pipeline(args, intent, df, outcome_col, time_col, unit_col, model_name):
    identified_unit = intent.get('identified_unit')
    forecast_periods = args.forecast_periods or intent.get('forecast_periods') or 10
    display_name = MODEL_DISPLAY_NAMES.get(model_name, model_name)

    unit_display = f" — {identified_unit}" if identified_unit else ""

    # Diagnostics
    _print_section(f"PRE-ANALYSIS DIAGNOSTICS{unit_display}")
    diag = run_arima_diagnostics(df, outcome_col, time_col)
    print(interpret_diagnostics(diag))

    # Run model
    forecast_heading = display_name.upper()
    if "FORECAST" not in forecast_heading:
        forecast_heading = f"{forecast_heading} FORECAST"
    _print_section(f"{forecast_heading}{unit_display}")
    result = FORECAST_RUNNERS[model_name](
        df, outcome_col, time_col, unit_col, forecast_periods=forecast_periods
    )

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return None

    order = result.get('arima_order', (1, 0, 0))
    engine = result.get('engine', '')
    forecasts = result.get('forecasts', [])
    forecast_times = result.get('forecast_times', [])
    ci_lower = result.get('ci_lower', [])
    ci_upper = result.get('ci_upper', [])

    model_label = f"ARIMA{order}" if model_name == 'arima' else display_name
    print(f"\nModel: {model_label}  (engine: {engine})")
    if result.get('aic') is not None:
        print(f"AIC:   {result.get('aic')}")
    print(f"RMSE:  {result.get('rmse', 0):.4f}")
    print(f"N obs: {result.get('n_obs', 0)}")
    print(f"\nFORECAST TABLE ({len(forecasts)} periods{unit_display})")
    print('-' * 70)
    print(f"{'Period':<10} {'Year':<10} {'Forecast':>14} {'95% CI Lower':>14} {'95% CI Upper':>14}")
    print('-' * 70)
    for i, (t, fc) in enumerate(zip(forecast_times, forecasts), 1):
        lo = f"{ci_lower[i-1]:>14.4f}" if ci_lower else "           N/A"
        hi = f"{ci_upper[i-1]:>14.4f}" if ci_upper else "           N/A"
        print(f"t+{i:<8} {int(t):<10} {fc:>14.4f} {lo} {hi}")

    _print_section("INTERPRETATION")
    interp = interpret_results(
        args.question, outcome_col, None, model_name, result, diag,
        unit_name=identified_unit,
        unit_description=intent.get('unit_value')
    )
    print(interp)

    return {
        'model': model_label,
        'model_key': model_name,
        'arima_order': order,
        'engine': engine,
        'forecasts': forecasts,
        'forecast_times': forecast_times,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'ar1_coef': result.get('ar1_coef', 0),
        'aic': result.get('aic'),
        'rmse': result.get('rmse'),
        'n_obs': result.get('n_obs'),
        'historical_values': result.get('historical_values', []),
        'historical_times': result.get('historical_times', []),
        'last_value': result.get('last_value'),
        'llm_interpretation': interp,
        'diagnostics': diag
    }


def _run_did_pipeline(args, intent, df, outcome_col, treatment_col, time_col, unit_col):
    identified_unit = intent.get('identified_unit')

    # Diagnostics
    _print_section("PRE-ANALYSIS DIAGNOSTICS (DiD)")
    diag = run_did_diagnostics(df, outcome_col, treatment_col, time_col, unit_col)
    print(interpret_diagnostics(diag))

    # Run model
    _print_section("DIFFERENCE-IN-DIFFERENCES RESULTS (TWFE)")
    result = run_diff_in_diff(df, outcome_col, treatment_col, time_col, unit_col)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return None

    effect = result.get('treatment_effect', 0)
    se     = result.get('se', 0)
    pval   = result.get('pvalue', 1)
    ci_lo  = result.get('ci_lower', effect - 1.96 * se)
    ci_hi  = result.get('ci_upper', effect + 1.96 * se)

    print(f"\nFixed effects : {result.get('fe_type', 'unit + time')}")
    print(f"SE type       : {result.get('se_type', 'clustered')}")
    print(f"Treatment effect: {effect:,.4f}")
    print(f"Clustered SE    : {se:,.4f}")
    print(f"t-statistic     : {result.get('t_stat', 0):.4f}")
    print(f"P-value         : {pval:.4f}")
    print(f"95% CI          : [{ci_lo:,.4f}, {ci_hi:,.4f}]")
    print(f"Significant     : {'Yes ***' if pval < 0.001 else 'Yes **' if pval < 0.01 else 'Yes *' if pval < 0.05 else 'No'}")
    print(f"R-squared       : {result.get('r_squared', 0):.4f}")
    print(f"N obs / units / periods: {result.get('n_obs',0)} / {result.get('n_units',0)} / {result.get('n_periods',0)}")

    _print_section("INTERPRETATION")
    interp = interpret_results(
        args.question, outcome_col, treatment_col, 'diff_in_diff', result, diag,
        unit_name=identified_unit,
        unit_description=intent.get('unit_value')
    )
    print(interp)

    return {
        'model': 'Difference-in-Differences',
        'effect': effect,
        'se': se,
        'p_value': pval,
        'ci_lower': ci_lo,
        'ci_upper': ci_hi,
        'r_squared': result.get('r_squared'),
        'n_obs': result.get('n_obs'),
        'n_units': result.get('n_units'),
        'n_periods': result.get('n_periods'),
        'fe_type': result.get('fe_type', ''),
        'se_type': result.get('se_type', ''),
        'llm_interpretation': interp,
        'diagnostics': diag
    }


def _run_panel_ols_pipeline(args, intent, df, outcome_col, treatment_col, time_col, unit_col):
    _print_section("PRE-ANALYSIS DIAGNOSTICS (Panel OLS)")
    diag = run_did_diagnostics(df, outcome_col, treatment_col, time_col, unit_col)
    print(interpret_diagnostics(diag))

    _print_section("PANEL OLS RESULTS (Two-Way FE)")
    result = run_panel_ols(df, outcome_col, treatment_col, time_col, unit_col)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return None

    effect = result.get('treatment_effect', 0)
    se     = result.get('se', 0)
    pval   = result.get('pvalue', 1)
    ci_lo  = result.get('ci_lower', effect - 1.96 * se)
    ci_hi  = result.get('ci_upper', effect + 1.96 * se)

    print(f"\nFixed effects : {result.get('fe_type', 'unit + time')}")
    print(f"SE type       : {result.get('se_type', 'clustered')}")
    print(f"Coefficient   : {effect:,.4f}")
    print(f"Clustered SE  : {se:,.4f}")
    print(f"P-value       : {pval:.4f}")
    print(f"95% CI        : [{ci_lo:,.4f}, {ci_hi:,.4f}]")
    print(f"R-squared     : {result.get('r_squared', 0):.4f}")

    _print_section("INTERPRETATION")
    interp = interpret_results(
        args.question, outcome_col, treatment_col, 'panel_ols', result, diag,
        unit_name=intent.get('identified_unit'),
        unit_description=intent.get('unit_value')
    )
    print(interp)

    return {
        'model': 'Panel OLS (Two-Way FE)',
        'effect': effect,
        'se': se,
        'p_value': pval,
        'ci_lower': ci_lo,
        'ci_upper': ci_hi,
        'r_squared': result.get('r_squared'),
        'n_obs': result.get('n_obs'),
        'n_units': result.get('n_units'),
        'n_periods': result.get('n_periods'),
        'fe_type': result.get('fe_type', ''),
        'se_type': result.get('se_type', ''),
        'llm_interpretation': interp,
        'diagnostics': diag
    }


def _run_ols_pipeline(args, intent, df, outcome_col, treatment_col):
    _print_section("PRE-ANALYSIS DIAGNOSTICS (OLS)")
    diag = run_ols_diagnostics(df, outcome_col, treatment_col)
    print(interpret_diagnostics(diag))

    _print_section("OLS RESULTS")
    result = run_ols(df, outcome_col, treatment_col)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return None

    slope  = result.get('slope', 0)
    se     = result.get('se', 0)
    pval   = result.get('pvalue', 1)
    ci_lo  = result.get('ci_lower', slope - 1.96 * se)
    ci_hi  = result.get('ci_upper', slope + 1.96 * se)

    print(f"\nSE type     : {result.get('se_type', 'HC1 robust')}")
    print(f"Intercept   : {result.get('intercept', 0):,.4f}")
    print(f"Slope       : {slope:,.4f}")
    print(f"SE          : {se:,.4f}")
    print(f"P-value     : {pval:.4f}")
    print(f"95% CI      : [{ci_lo:,.4f}, {ci_hi:,.4f}]")
    print(f"R-squared   : {result.get('r_squared', 0):.4f}")

    _print_section("INTERPRETATION")
    interp = interpret_results(
        args.question, outcome_col, treatment_col, 'ols', result, diag
    )
    print(interp)

    return {
        'model': 'OLS',
        'effect': slope,
        'se': se,
        'p_value': pval,
        'ci_lower': ci_lo,
        'ci_upper': ci_hi,
        'r_squared': result.get('r_squared'),
        'n_obs': result.get('n_obs'),
        'se_type': result.get('se_type', ''),
        'llm_interpretation': interp,
        'diagnostics': diag
    }


def _run_generic_regression_pipeline(
    args, intent, df, model_name, outcome_col, treatment_col, time_col=None, unit_col=None
):
    """Run any non-specialized regression-style model and normalize output."""
    display_name = MODEL_DISPLAY_NAMES.get(model_name, model_name)
    _print_section(f"PRE-ANALYSIS DIAGNOSTICS ({display_name})")

    if model_name in ('diff_in_diff', 'panel_ols', 'entity_fe', 'first_difference') and unit_col and time_col:
        diag = run_did_diagnostics(df, outcome_col, treatment_col, time_col, unit_col)
    else:
        diag = run_ols_diagnostics(df, outcome_col, treatment_col)
    print(interpret_diagnostics(diag))

    _print_section(f"{display_name.upper()} RESULTS")
    runner = REGRESSION_RUNNERS[model_name]
    if model_name in ('diff_in_diff', 'panel_ols', 'first_difference'):
        result = runner(df, outcome_col, treatment_col, time_col, unit_col)
    elif model_name == 'entity_fe':
        result = runner(df, outcome_col, treatment_col, unit_col)
    elif model_name == 'time_fe':
        result = runner(df, outcome_col, treatment_col, time_col)
    else:
        result = runner(df, outcome_col, treatment_col)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return None

    effect = result.get('treatment_effect', result.get('effect', result.get('slope', 0)))
    se = result.get('se', 0) or 0
    pval = result.get('pvalue', 1) or 1
    ci_lo = result.get('ci_lower', effect - 1.96 * se)
    ci_hi = result.get('ci_upper', effect + 1.96 * se)

    if result.get('fe_type'):
        print(f"\nFixed effects : {result.get('fe_type')}")
    print(f"SE type       : {result.get('se_type', 'standard')}")
    print(f"Coefficient   : {effect:,.4f}")
    print(f"SE            : {se:,.4f}")
    print(f"t-statistic   : {result.get('t_stat', 0):.4f}")
    print(f"P-value       : {pval:.4f}")
    print(f"95% CI        : [{ci_lo:,.4f}, {ci_hi:,.4f}]")
    print(f"R-squared     : {result.get('r_squared', 0):.4f}")
    print(f"N obs         : {result.get('n_obs', 0):,}")

    _print_section("INTERPRETATION")
    interp = interpret_results(
        args.question, outcome_col, treatment_col, model_name, result, diag,
        unit_name=intent.get('identified_unit'),
        unit_description=intent.get('unit_value')
    )
    print(interp)

    return {
        'model': display_name,
        'model_key': model_name,
        'effect': effect,
        'se': se,
        'p_value': pval,
        'ci_lower': ci_lo,
        'ci_upper': ci_hi,
        'r_squared': result.get('r_squared'),
        'n_obs': result.get('n_obs'),
        'n_units': result.get('n_units'),
        'n_periods': result.get('n_periods'),
        'fe_type': result.get('fe_type', ''),
        'se_type': result.get('se_type', ''),
        'llm_interpretation': interp,
        'diagnostics': diag
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Espresso Statistical Analysis Engine')
    parser.add_argument("--data", help="Path to CSV data file")
    parser.add_argument("--question", help="Research question")
    parser.add_argument(
        "--model",
        choices=sorted(MODEL_SPECS.keys()),
        help="Optional model override. Use --list-models to see descriptions.",
    )
    parser.add_argument(
        "--forecast-periods",
        type=int,
        help="Override the number of forecast periods for forecasting models.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print supported econometric/statistical models and exit.",
    )
    args = parser.parse_args()

    if args.list_models:
        _print_header("SUPPORTED MODELS")
        for name, spec in MODEL_SPECS.items():
            print(f"{name:<18} {spec['display_name']}")
            print(f"  Type: {spec['question_type']}")
            print(f"  {spec['description']}\n")
        return 0

    if not args.data or not args.question:
        parser.error("--data and --question are required unless --list-models is used")

    global interpret_diagnostics, interpret_results
    from interpretation import interpret_diagnostics, interpret_results
    from llm import identify_unit_value, map_columns, parse_question

    _print_header("ESPRESSO — Statistical Analysis Engine")

    # 1. Load data
    print(f"\n[1/6] Loading data…")
    try:
        df = load_data(args.data)
        print(f"      Loaded {len(df):,} rows × {len(df.columns)} columns")
    except Exception as e:
        print(f"      ERROR: {e}")
        return 1

    # 2. Parse question
    print(f"\n[2/6] Understanding question…")
    print(f"      '{args.question}'")
    intent = parse_question(args.question)
    if not intent:
        print("      ERROR: Could not parse question")
        return 1

    intent['question'] = args.question
    print(f"      Type:      {intent.get('question_type', '?').upper()}")
    print(f"      Outcome:   {intent.get('outcome')}")
    print(f"      Predictor: {intent.get('treatment') or 'None'}")

    # 3. Map columns
    print(f"\n[3/6] Mapping variables to columns…")
    samples = get_column_samples(df)
    mapping = map_columns(intent, samples)

    outcome_val   = _get_col_val(mapping.get('outcome'))
    treatment_val = _get_col_val(mapping.get('treatment'))
    print(f"      Outcome   → {outcome_val}")
    print(f"      Predictor → {treatment_val or 'None'}")

    # Resolve specific unit if requested
    unit_value_desc = intent.get('unit_value')
    identified_unit = None
    if unit_value_desc:
        unit_col_map = mapping.get('unit', {})
        unit_col_name = _get_col_val(unit_col_map)
        if unit_col_name and unit_col_name in df.columns:
            identified_unit = identify_unit_value(unit_value_desc, unit_col_name, df)
            if identified_unit:
                print(f"      Unit      → {identified_unit}")
                intent['identified_unit'] = identified_unit
                intent['unit_column'] = unit_col_name
            else:
                print(f"      Unit      → could not resolve '{unit_value_desc}'")

    # 4. Transform data
    print(f"\n[4/6] Preparing data…")
    if mapping.get('pivot') or isinstance(_get_col_val(mapping.get('time')), list):
        print(f"      Pivoting wide → long format…")
        indicator_col = mapping.get('indicator_column', 'SERIES_NAME')
        year_cols = mapping.get('year_columns') or get_year_columns(df)

        long_df, unit_col, ind_col = pivot_indicator_panel(
            df, indicator_col=indicator_col, year_cols=year_cols
        )
        print(f"      Pivoted: {len(long_df):,} rows")

        import re
        outcome_df = treatment_df = None
        if outcome_val:
            mask = long_df[ind_col].astype(str).str.contains(
                re.escape(str(outcome_val)), case=False, na=False
            )
            outcome_df = long_df[mask][[unit_col, 'year', 'value']].rename(
                columns={'value': str(outcome_val)}
            )
        if treatment_val:
            mask = long_df[ind_col].astype(str).str.contains(
                re.escape(str(treatment_val)), case=False, na=False
            )
            treatment_df = long_df[mask][[unit_col, 'year', 'value']].rename(
                columns={'value': str(treatment_val)}
            )

        if outcome_df is not None and treatment_df is not None:
            df = outcome_df.merge(treatment_df, on=[unit_col, 'year'], how='inner')
        elif outcome_df is not None:
            df = outcome_df

        if identified_unit and unit_col in df.columns:
            df = df[df[unit_col] == identified_unit].copy()
            print(f"      Filtered to '{identified_unit}': {len(df):,} rows")
            if len(df) == 0:
                print(f"      ERROR: No data found for '{identified_unit}'")
                return 1

        intent['outcome']   = outcome_val
        intent['treatment'] = treatment_val
        intent['unit']      = unit_col
        intent['time']      = 'year'
    else:
        print("      Data is already in tidy format")
        # Update intent with resolved column names from mapping
        if outcome_val:
            intent['outcome'] = outcome_val
        if treatment_val:
            intent['treatment'] = treatment_val
        time_val = _get_col_val(mapping.get('time'))
        if time_val:
            intent['time'] = time_val
        unit_map = _get_col_val(mapping.get('unit'))
        if unit_map:
            intent['unit'] = unit_map

    # 5. Select model
    print(f"\n[5/6] Selecting statistical model…")
    models, rejected = select_admissible_models(intent, df)

    if not models:
        print("      ERROR: No valid models found")
        for m, reason in rejected.items():
            print(f"        {m}: {reason}")
        return 1

    if args.model:
        if args.model in models:
            model_name = args.model
        elif args.model in rejected:
            print(f"      ERROR: requested model '{args.model}' cannot run: {rejected[args.model]}")
            return 1
        else:
            print(
                f"      ERROR: requested model '{args.model}' does not match "
                f"question type '{intent.get('question_type')}'"
            )
            return 1
    else:
        model_name = models[0]
    print(f"      Selected: {model_name.upper()}")
    print(f"      Label:    {MODEL_DISPLAY_NAMES.get(model_name, model_name)}")
    alternatives = [m for m in models if m != model_name]
    if alternatives:
        print(f"      Alternatives: {', '.join(alternatives)}")
    if rejected:
        for m, r in rejected.items():
            print(f"        [rejected] {m}: {r}")

    # 6. Run analysis
    print(f"\n[6/6] Running analysis…")
    _print_header("ANALYSIS RESULTS")

    outcome_col   = intent.get('outcome')
    treatment_col = intent.get('treatment')
    time_col      = intent.get('time')
    unit_col      = intent.get('unit')

    result_record = None

    if model_name in FORECAST_RUNNERS:
        result_record = _run_forecast_pipeline(
            args, intent, df, outcome_col, time_col, unit_col, model_name
        )

    elif model_name == 'diff_in_diff':
        result_record = _run_did_pipeline(
            args, intent, df, outcome_col, treatment_col, time_col, unit_col
        )

    elif model_name == 'panel_ols':
        result_record = _run_panel_ols_pipeline(
            args, intent, df, outcome_col, treatment_col, time_col, unit_col
        )

    elif model_name == 'ols':
        result_record = _run_ols_pipeline(args, intent, df, outcome_col, treatment_col)

    elif model_name in REGRESSION_RUNNERS:
        result_record = _run_generic_regression_pipeline(
            args, intent, df, model_name, outcome_col, treatment_col, time_col, unit_col
        )

    else:
        print(f"ERROR: No runner implemented for model '{model_name}'")
        return 1

    if result_record is None:
        return 1

    # Generate HTML report
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = f"outputs/espresso_report_{ts}.html"
        html_path = create_html_report(
            out_path, intent, mapping, [result_record],
            data_sample=df.head(200)
        )
        _print_header(f"HTML REPORT: {html_path}")
    except Exception as e:
        print(f"\nWarning: Could not create HTML report: {e}")
        import traceback
        traceback.print_exc()

    return 0


if __name__ == "__main__":
    sys.exit(main())
