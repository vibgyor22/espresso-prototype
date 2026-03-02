#!/usr/bin/env python
"""Test the reshape logic for causal analysis on wide-format data"""

import pandas as pd
from data_utils import load_data, pivot_indicator_panel, is_panel_data, get_column_samples
from llm import parse_question, map_columns
from selector import select_admissible_models
import json

# Load the test data
print("[TEST] Loading dataset...")
df = load_data('data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv')
print(f"[TEST] Data shape: {df.shape}")
print(f"[TEST] Columns (first 10): {df.columns[:10].tolist()}")

# Test causal question
question = "Does higher government debt reduce economic growth?"
print(f"\n[TEST] Question: {question}")

# Parse the question
print("[TEST] Parsing question...")
intent = parse_question(question)
print(f"[TEST] Parsed intent: {intent}")

# Check initial model selection (should fail on wide data)
print("[TEST] Checking model selection on original data...")
models, rejected = select_admissible_models(intent, df)
print(f"[TEST] Initial models: {models}")
print(f"[TEST] Rejected: {rejected}")

# Now try to reshape
if not models and intent.get('question_type') == 'causal_effect':
    print("\n[TEST] Attempting reshape...")
    try:
        df_long, unit_col, indicator_col = pivot_indicator_panel(df)
        print(f"[OK] Reshape successful!")
        print(f"[TEST] New shape: {df_long.shape}")
        print(f"[TEST] New columns: {df_long.columns.tolist()}")
        print(f"[TEST] Unit column: {unit_col}")
        print(f"[TEST] Indicator column: {indicator_col}")
        
        # Update intent
        intent['time'] = 'year'
        intent['unit'] = unit_col
        print(f"\n[TEST] Updated intent: {intent}")
        
        # Re-map columns
        print("[TEST] Re-mapping columns...")
        column_samples = get_column_samples(df_long)
        print(f"[TEST] Column samples available")
        
        mapping = map_columns(intent, column_samples)
        print(f"[TEST] New mapping keys: {list(mapping.keys())}")
        for key, val in mapping.items():
            if isinstance(val, dict) and 'value' in val:
                print(f"  {key}: {val['value']}")
        
        # Try model selection again
        print("\n[TEST] Retrying model selection...")
        models, rejected = select_admissible_models(intent, df_long)
        print(f"[OK] Final models: {models}")
        print(f"[REJECTED] {rejected}")
        
    except Exception as e:
        print(f"[ERROR] Reshape failed: {e}")
        import traceback
        traceback.print_exc()

print("\n[TEST] Done!")
