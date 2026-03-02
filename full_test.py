#!/usr/bin/env python3
"""Complete test of the Espresso analysis pipeline"""

import os
import sys
import json
import traceback

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_utils import load_data, get_column_samples
from llm import parse_question, map_columns
from selector import select_admissible_models
from diagnostics import run_arima_diagnostics
from models import run_arima
from interpretation import interpret_diagnostics, interpret_results

def test_forecast_pipeline():
    """Test the complete forecast pipeline"""
    
    print("\n" + "="*70)
    print("COMPLETE ESPRESSO ANALYSIS PIPELINE TEST")
    print("="*70)
    
    dataset_path = 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv'
    question = "what is the forecast of unemployment for india for the next 10 years?"
    
    try:
        print("\n[1/8] Loading data...")
        df = load_data(dataset_path)
        print(f"     [OK] Loaded {len(df)} rows x {len(df.columns)} columns")
        
        print("\n[2/8] Parsing question...")
        intent = parse_question(question)
        print(f"     [OK] Type: {intent.get('question_type')}")
        
        print("\n[3/8] Getting column samples...")
        column_samples = get_column_samples(df)
        print(f"     [OK] Got {len(column_samples)} column samples")
        
        print("\n[4/8] Mapping columns...")
        mapping = map_columns(intent, column_samples)
        print(f"     [OK] Mapped {len(mapping)} variables")
        
        print("\n[5/8] Selecting models...")
        models, rejected = select_admissible_models(intent, df)
        print(f"     [OK] Selected: {models}")
        
        if not models:
            print("     [ERROR] No models selected")
            return False
        
        model_type = models[0]
        
        if model_type == 'arima':
            outcome_col = None
            if 'Outcome' in mapping:
                outcome_col = mapping['Outcome']['value']
            elif 'Value' in mapping:
                outcome_col = mapping['Value']['value']
            else:
                outcome_col = list(mapping.values())[0]['value']
            
            time_col = None
            if 'Time' in mapping:
                time_col = mapping['Time']['value']
            elif 'Year' in mapping:
                time_col = mapping['Year']['value']
            else:
                for key, val in mapping.items():
                    if 'time' in key.lower() or 'year' in key.lower():
                        time_col = val['value']
                        break
            
            print(f"     [OK] Outcome column: {outcome_col}")
            print(f"     [OK] Time column: {time_col}")
            
            print("\n[6/8] Running diagnostics...")
            diag = run_arima_diagnostics(df, outcome_col, time_col)
            diag_summary = interpret_diagnostics(diag)
            print(f"     [OK] Diagnostics complete")
            
            print("\n[7/8] Estimating ARIMA model...")
            model_result = run_arima(df, outcome_col, time_col)
            print(f"     [OK] Model estimated")
            print(f"     Results: {list(model_result.keys())}")
            
            print("\n[8/8] Generating interpretation...")
            interpretation = interpret_results(
                question,
                outcome_col,
                None,
                'arima',
                model_result,
                diag
            )
            print(f"     [OK] Interpretation generated")
            print(f"     Length: {len(interpretation)} characters")
            
            if len(interpretation) < 50:
                print("     [WARNING] Interpretation is very short")
                print(f"     Content: {interpretation}")
                return False
            
            print("\n" + "="*70)
            print("SUCCESS: Full pipeline completed!")
            print("="*70)
            print(f"\nInterpretation preview (first 300 chars):\n{interpretation[:300]}...")
            
            return True
        else:
            print(f"[ERROR] Unexpected model type: {model_type}")
            return False
    
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_forecast_pipeline()
    sys.exit(0 if success else 1)
