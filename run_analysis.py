"""
Espresso CLI - Command-line analysis tool
Clean, simple interface for running statistical analyses
"""
import argparse
import sys
import warnings
warnings.filterwarnings('ignore')

from data_utils import load_data, get_column_samples, pivot_indicator_panel, get_year_columns
from llm import parse_question, map_columns
from selector import select_admissible_models
from diagnostics import run_arima_diagnostics, run_did_diagnostics
from models import run_arima, run_diff_in_diff
from interpretation import interpret_results, interpret_diagnostics
from html_report import create_html_report
from datetime import datetime, timezone

def main():
    parser = argparse.ArgumentParser(description='Espresso Statistical Analysis Engine')
    parser.add_argument("--data", required=True, help="Path to CSV data file")
    parser.add_argument("--question", required=True, help="Research question")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  ESPRESSO - Statistical Analysis Engine")
    print("=" * 70)

    # 1. LOAD DATA
    print(f"\n[1/6] Loading data...")
    try:
        df = load_data(args.data)
        print(f"      Loaded {len(df):,} rows x {len(df.columns)} columns")
    except Exception as e:
        print(f"      ERROR: {e}")
        return 1

    # 2. PARSE QUESTION
    print(f"\n[2/6] Understanding question...")
    print(f"      '{args.question}'")
    intent = parse_question(args.question)
    if not intent:
        print("      ERROR: Could not parse question")
        return 1
    
    # Store the original question in the intent for HTML report
    intent['question'] = args.question
    
    print(f"      Type: {intent.get('question_type', 'unknown').upper()}")
    print(f"      Outcome: {intent.get('outcome')}")
    print(f"      Treatment: {intent.get('treatment', 'None')}")

    # 3. MAP COLUMNS
    print(f"\n[3/6] Mapping variables to data columns...")
    samples = get_column_samples(df)
    mapping = map_columns(intent, samples)
    
    if mapping:
        outcome_val = mapping.get('outcome', {}).get('value') if isinstance(mapping.get('outcome'), dict) else mapping.get('outcome')
        treatment_val = mapping.get('treatment', {}).get('value') if isinstance(mapping.get('treatment'), dict) else mapping.get('treatment')
        print(f"      Outcome -> {outcome_val}")
        print(f"      Treatment -> {treatment_val if treatment_val else 'None'}")
        
        # Identify specific unit if unit_value is provided
        unit_value_desc = intent.get('unit_value')
        identified_unit = None
        
        if unit_value_desc:
            # Get the unit column name from mapping
            unit_col_mapping = mapping.get('unit', {})
            if isinstance(unit_col_mapping, dict):
                unit_col_name = unit_col_mapping.get('value')
            else:
                unit_col_name = unit_col_mapping
            
            if unit_col_name and unit_col_name in df.columns:
                from llm import identify_unit_value
                identified_unit = identify_unit_value(unit_value_desc, unit_col_name, df)
                
                if identified_unit:
                    print(f"      Unit -> {identified_unit}")
                    intent['identified_unit'] = identified_unit
                    intent['unit_column'] = unit_col_name
                else:
                    print(f"      Unit -> Could not identify '{unit_value_desc}' in data")
            else:
                print(f"      Unit -> Column not found in data")
        
        # Handle pivoting if needed
        if mapping.get('pivot') or isinstance(mapping.get('time', {}).get('value'), list):
            print(f"\n[4/6] Transforming data (wide to long format)...")
            indicator_col = mapping.get('indicator_column', 'SERIES_NAME')
            year_cols = mapping.get('year_columns') or get_year_columns(df)
            
            long_df, unit_col, ind_col = pivot_indicator_panel(df, indicator_col=indicator_col, year_cols=year_cols)
            print(f"      Pivoted to {len(long_df):,} rows")
            
            # Extract outcome and treatment series
            import re
            if outcome_val:
                outcome_df = long_df[long_df[ind_col].astype(str).str.contains(re.escape(str(outcome_val)), case=False, na=False)]
                outcome_df = outcome_df[[unit_col, 'year', 'value']].rename(columns={'value': str(outcome_val)})
            
            if treatment_val:
                treatment_df = long_df[long_df[ind_col].astype(str).str.contains(re.escape(str(treatment_val)), case=False, na=False)]
                treatment_df = treatment_df[[unit_col, 'year', 'value']].rename(columns={'value': str(treatment_val)})
            
            if outcome_val and treatment_val:
                df = outcome_df.merge(treatment_df, on=[unit_col, 'year'], how='inner')
            elif outcome_val:
                df = outcome_df
            
            # Filter to specific unit if identified
            identified_unit = intent.get('identified_unit')
            if identified_unit and unit_col in df.columns:
                original_rows = len(df)
                df = df[df[unit_col] == identified_unit].copy()
                print(f"      Filtered to {identified_unit}: {len(df):,} rows (from {original_rows:,})")
                
                if len(df) == 0:
                    print(f"      ERROR: No data found for {identified_unit}")
                    return 1
            
            intent['outcome'] = outcome_val
            intent['treatment'] = treatment_val
            intent['unit'] = unit_col
            intent['time'] = 'year'
        else:
            print(f"\n[4/6] Data format validation...")
            print(f"      Data is already in correct format")
    
    # 5. SELECT MODEL
    print(f"\n[5/6] Selecting statistical model...")
    models, rejected = select_admissible_models(intent, df)
    
    if not models:
        print(f"      ERROR: No valid models found")
        for model, reason in rejected.items():
            print(f"        {model}: {reason}")
        return 1
    
    model = models[0]
    print(f"      Selected: {model.upper()}")
    
    # 6. RUN ANALYSIS
    print(f"\n[6/6] Running analysis...")
    print("=" * 70)
    
    outcome_col = intent.get('outcome')
    treatment_col = intent.get('treatment')
    time_col = intent.get('time')
    unit_col = intent.get('unit')
    forecast_periods = intent.get('forecast_periods', 10)  # Get forecast periods from intent, default 10
    
    results = []
    
    if model == 'arima':
        # Display unit prominently
        identified_unit = intent.get('identified_unit')
        unit_display = f" - {identified_unit}" if identified_unit else ""
        
        # Diagnostics
        print(f"\nPRE-ANALYSIS DIAGNOSTICS{unit_display}")
        print("-" * 70)
        diag = run_arima_diagnostics(df, outcome_col, time_col)
        print(interpret_diagnostics(diag))
        
        # Run model with dynamic forecast periods
        print(f"\nARIMA FORECAST RESULTS{unit_display}")
        print("-" * 70)
        result = run_arima(df, outcome_col, time_col, unit_col, forecast_periods=forecast_periods)
        
        if 'error' in result:
            print(f"ERROR: {result['error']}")
            return 1
        
        # Display results
        forecasts = result.get('forecasts', [])
        forecast_times = result.get('forecast_times', [])
        ar_coef = result.get('ar1_coef', 0)
        
        print(f"\nModel Coefficient (AR1): {ar_coef:.4f}")
        print(f"Process: {'Stable' if abs(ar_coef) < 1 else 'High persistence / potentially explosive'}")
        print(f"Model Quality (RMSE): {result.get('rmse', 0):.4f}")
        print(f"Observations: {result.get('n_obs', 0)}")
        
        unit_suffix = f" - {identified_unit}" if identified_unit else ""
        print(f"\nFORECAST TABLE ({len(forecasts)} periods{unit_suffix})")
        print("-" * 70)
        print(f"{'Period':<10} {'Year':<10} {'Forecast':>15}")
        print("-" * 70)
        for i, (time, fc) in enumerate(zip(forecast_times, forecasts), 1):
            print(f"t+{i:<8} {int(time):<10} {fc:>15.4f}")
        
        # Interpretation
        print(f"\nINTERPRETATION")
        print("-" * 70)
        unit_description = intent.get('unit_value')  # Original description like "most populous country"
        interp = interpret_results(args.question, outcome_col, None, 'arima', result, diag, unit_name=identified_unit, unit_description=unit_description)
        print(interp)
        
        results.append({
            'model': 'ARIMA (AR(1))',
            'forecasts': forecasts,
            'forecast_times': forecast_times,
            'ar1_coef': ar_coef,
            'rmse': result.get('rmse'),
            'n_obs': result.get('n_obs'),
            'historical_values': result.get('historical_values', []),
            'historical_times': result.get('historical_times', []),
            'llm_interpretation': interp,
            'diagnostics': diag
        })
    
    elif model == 'diff_in_diff':
        # Diagnostics
        print(f"\nPRE-ANALYSIS DIAGNOSTICS")
        print("-" * 70)
        diag = run_did_diagnostics(df, outcome_col, treatment_col, time_col, unit_col)
        print(interpret_diagnostics(diag))
        
        # Run model
        print(f"\nDIFFERENCE-IN-DIFFERENCES RESULTS")
        print("-" * 70)
        result = run_diff_in_diff(df, outcome_col, treatment_col, time_col, unit_col)
        
        if 'error' in result:
            print(f"ERROR: {result['error']}")
            return 1
        
        effect = result.get('treatment_effect', 0)
        se = result.get('se', 0)
        pval = result.get('pvalue', 1)
        
        print(f"\nTreatment Effect: {effect:,.2f}")
        print(f"Standard Error: {se:,.2f}")
        print(f"P-value: {pval:.4f}")
        print(f"Significant: {'Yes' if pval < 0.05 else 'No'}")
        print(f"R-squared: {result.get('r_squared', 0):.4f}")
        
        # Interpretation
        print(f"\nINTERPRETATION")
        print("-" * 70)
        identified_unit = intent.get('identified_unit')
        unit_description = intent.get('unit_value')
        interp = interpret_results(args.question, outcome_col, treatment_col, 'diff_in_diff', result, diag, unit_name=identified_unit, unit_description=unit_description)
        print(interp)
        
        results.append({
            'model': 'Difference-in-Differences',
            'effect': effect,
            'se': se,
            'p_value': pval,
            'r_squared': result.get('r_squared'),
            'n_obs': result.get('n_obs'),
            'llm_interpretation': interp,
            'diagnostics': diag
        })
    
    # Generate HTML report
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = f"outputs/espresso_report_{ts}.html"
        html_path = create_html_report(out_path, intent, mapping, results, data_sample=df.head(200))
        print(f"\n" + "=" * 70)
        print(f"HTML REPORT: {html_path}")
        print("=" * 70 + "\n")
    except Exception as e:
        print(f"\nWarning: Could not create HTML report: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
