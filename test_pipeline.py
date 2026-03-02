#!/usr/bin/env python3
"""Direct test of the analyze function without Flask"""

from data_utils import load_data
from llm import parse_question, map_columns
from selector import select_admissible_models
from data_utils import get_column_samples

print("Step 1: Load data")
df = load_data('data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv')
print(f"[OK] Loaded {len(df)} rows")

print("\nStep 2: Parse question")
question = "what is the forecast of unemployment for india?"
intent = parse_question(question)
print(f"[OK] Intent: {intent}")

print("\nStep 3: Get column samples")
column_samples = get_column_samples(df)
print(f"[OK] Got samples for {len(column_samples)} columns")

print("\nStep 4: Map columns")
mapping = map_columns(intent, column_samples)
print(f"[OK] Mapped: {list(mapping.keys())}")

print("\nStep 5: Select models")
try:
    models, rejected = select_admissible_models(intent, df)
    print(f"[OK] Selected models: {models}")
    print(f"[OK] Rejected: {rejected}")
except Exception as e:
    print(f"[ERROR] in select_admissible_models: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\nDirect function test completed successfully!")

