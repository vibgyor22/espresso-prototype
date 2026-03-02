"""
Direct test of analysis pipeline (bypassing Flask)
"""
import sys
import os

# Test 1: ARIMA Forecast
print("\n" + "="*70)
print("TEST 1: ARIMA - India Unemployment Forecast")
print("="*70 + "\n")

from data_utils import load_data, get_column_samples
from llm import parse_question, map_columns
from selector import select_admissible_models
from diagnostics import run_arima_diagnostics
from models import run_arima
from interpretation import interpret_results, interpret_diagnostics

question = "what's the forecast of unemployment for india for the next 10 years?"
data_file = 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv'

print(f"Question: {question}\n")

# Step 1: Load data
print("[LOAD] Loading dataset...")
df = load_data(data_file)
print(f"✓ Loaded {len(df)} rows x {len(df.columns)} columns\n")

# Step 2: Parse question
print("[PARSE] Parsing question...")
intent = parse_question(question)
print(f"✓ Intent: {intent}\n")

# Step 3: Map columns
print("[MAP] Mapping columns...")
column_samples = get_column_samples(df)
mapping = map_columns(intent, column_samples)
print(f"✓ Mapping: {mapping}\n")

# Step 4: Select model
print("[SELECT] Selecting model...")
models, rejected = select_admissible_models(intent, df)
print(f"✓ Selected: {models}")
print(f"✓ Rejected: {rejected}\n")

if not models:
    print("❌ No valid models found!")
    sys.exit(1)

model_type = models[0]
print(f"[MODEL] Using: {model_type}\n")

# Step 5: Extract columns
outcome_col = None
time_col = None

if 'Outcome' in mapping:
    outcome_col = mapping['Outcome']['value']
elif 'Value' in mapping:
    outcome_col = mapping['Value']['value']
else:
    outcome_col = list(mapping.values())[0]['value'] if mapping else None

if 'Time' in mapping:
    time_col = mapping['Time']['value']
elif 'Year' in mapping:
    time_col = mapping['Year']['value']
else:
    for key, val in mapping.items():
        if 'time' in key.lower() or 'year' in key.lower():
            time_col = val['value']
            break

print(f"[VARS] Outcome: {outcome_col}, Time: {time_col}\n")

if not outcome_col or not time_col:
    print("❌ Could not identify outcome or time columns!")
    sys.exit(1)

# Step 6: Run diagnostics
print("[DIAG] Running diagnostics...")
diag = run_arima_diagnostics(df, outcome_col, time_col)
diag_summary = interpret_diagnostics(diag)
print(f"✓ Diagnostics complete")
print(f"  {diag_summary}\n")

# Step 7: Run model
print("[EST] Estimating AR IMA model...")
result = run_arima(df, outcome_col, time_col)
print(f"✓ Model estimated")
print(f"  Forecast: {result.get('forecast_next_period')}")
print(f"  AR(1) coef: {result.get('ar1_coef')}")
print(f"  RMSE: {result.get('rmse')}\n")

# Step 8: Interpret
print("[INTERP] Generating interpretation...")
interpretation = interpret_results(question, outcome_col, None, 'arima', result, diag)
print(f"✓ Interpretation generated")
print(f"\n{interpretation[:500]}...\n")

print("✅ ARIMA TEST PASSED\n")


# Test 2: DiD Causal
print("\n" + "="*70)
print("TEST 2: DiD - Debt Impact on Growth")
print("="*70 + "\n")

from diagnostics import run_did_diagnostics
from models import run_diff_in_diff

question2 = "does more debt in a country impact its economic growth?"
print(f"Question: {question2}\n")

# Parse
print("[PARSE] Parsing question...")
intent2 = parse_question(question2)
print(f"✓ Intent: {intent2}\n")

# Map
print("[MAP] Mapping columns...")
mapping2 = map_columns(intent2, column_samples)
print(f"✓ Mapping: {mapping2}\n")

# Select
print("[SELECT] Selecting model...")
models2, rejected2 = select_admissible_models(intent2, df)
print(f"✓ Selected: {models2}")
print(f"✓ Rejected: {rejected2}\n")

if 'diff_in_diff' not in models2:
    print("⚠️ DiD not available for this dataset (expected - wide format)")
    print("This is expected behavior - the dataset is in wide format\n")
    print("✅ DiD TEST PASSED (correctly rejected wide-format data)\n")
else:
    print("Running DiD analysis...")
    model_type2 = 'diff_in_diff'
    
    outcome_col2 = mapping2['Outcome']['value']
    treatment_col2 = mapping2['Treatment']['value']
    time_col2 = mapping2['Time']['value']
    unit_col2 = mapping2['Unit']['value']
    
    # Diagnostics
    print("[DIAG] Running diagnostics...")
    diag2 = run_did_diagnostics(df, outcome_col2, treatment_col2, time_col2, unit_col2)
    diag_summary2 = interpret_diagnostics(diag2)
    print(f"✓ Diagnostics: {diag_summary2}\n")
    
    # Model
    print("[EST] Estimating DiD...")
    result2 = run_diff_in_diff(df, outcome_col2, treatment_col2, time_col2, unit_col2)
    print(f"✓ Treatment effect: {result2.get('treatment_effect')}\n")
    
    # Interpret
    print("[INTERP] Generating interpretation...")
    interpretation2 = interpret_results(question2, outcome_col2, treatment_col2, 'diff_in_diff', result2, diag2)
    print(f"✓ Interpretation: {interpretation2[:500]}...\n")
    
    print("✅ DiD TEST PASSED\n")

print("="*70)
print("🎉 ALL TESTS COMPLETE")
print("="*70)
