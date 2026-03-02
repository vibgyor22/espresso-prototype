#!/usr/bin/env python
"""Test both analysis prompts and validate results"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"
DATASET = "data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv"

def test_prompt(prompt_text, name):
    """Test a single prompt and return results"""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")
    print(f"Question: {prompt_text}\n")
    
    payload = {
        'dataset': DATASET,
        'question': prompt_text
    }
    
    try:
        start = time.time()
        r = requests.post(f"{BASE_URL}/api/analyze", json=payload, timeout=180)
        elapsed = time.time() - start
        
        print(f"[STATUS] {r.status_code} in {elapsed:.1f}s")
        data = r.json()
        
        # Check for errors
        if 'error' in data:
            print(f"\n[ERROR] {data['error'][:200]}")
            return False
        
        # Show logs
        print(f"\n[LOGS] {len(data.get('logs', []))} entries")
        for log in data.get('logs', [])[-10:]:
            print(f"  {log}")
        
        # Validate model results
        model_type = data.get('model_type')
        model_result = data.get('model_result', {})
        
        print(f"\n[MODEL] {model_type}")
        
        if model_type == 'arima':
            forecast = model_result.get('forecast_next_period')
            rmse = model_result.get('rmse')
            ar1 = model_result.get('ar1_coef')
            stability = model_result.get('process_stability')
            
            print(f"  Forecast: {forecast}")
            print(f"  RMSE: {rmse}")
            print(f"  AR(1): {ar1}")
            print(f"  Stability: {stability}")
            
            # Validation checks
            valid = True
            if forecast is None or forecast == 0:
                print("  ⚠️ ISSUE: Forecast is None or 0")
                valid = False
            if rmse is None or rmse == 0:
                print("  ⚠️ ISSUE: RMSE is None or 0")
                valid = False
            if ar1 is None or ar1 == 0:
                print("  ⚠️ ISSUE: AR(1) is None or 0")
                valid = False
            if stability is None:
                print("  ⚠️ ISSUE: Stability is None")
                valid = False
            
            if valid:
                print("  ✅ All metrics valid!")
                return True
            return False
            
        elif model_type == 'diff_in_diff':
            treatment_effect = model_result.get('treatment_effect')
            se = model_result.get('se')
            pvalue = model_result.get('pvalue')
            r_squared = model_result.get('r_squared')
            
            print(f"  Treatment Effect: {treatment_effect}")
            print(f"  Std Error: {se}")
            print(f"  P-value: {pvalue}")
            print(f"  R²: {r_squared}")
            
            valid = True
            if treatment_effect is None:
                print("  ⚠️ ISSUE: Treatment effect is None")
                valid = False
            if se is None or se <= 0:
                print("  ⚠️ ISSUE: Std error is None or <= 0")
                valid = False
            if pvalue is None or pvalue < 0 or pvalue > 1:
                print("  ⚠️ ISSUE: P-value invalid")
                valid = False
            if r_squared is None or r_squared < 0 or r_squared > 1:
                print("  ⚠️ ISSUE: R² invalid")
                valid = False
            
            if valid:
                print("  ✅ All metrics valid!")
                return True
            return False
        
        print(f"  ⚠️ Unknown model type: {model_type}")
        return False
        
    except Exception as e:
        print(f"[EXCEPTION] {e}")
        import traceback
        traceback.print_exc()
        return False

# Test both prompts
prompts = [
    ("what is the forecast of unemployment for India for the next 10 years?", "ARIMA Forecast"),
    ("does higher government debt reduce economic growth?", "DiD Causal"),
]

results = {}
for prompt, name in prompts:
    results[name] = test_prompt(prompt, name)
    time.sleep(1)

# Summary
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
for name, success in results.items():
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {name}")
