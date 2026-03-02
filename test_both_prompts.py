"""
Test script to verify the two prompts work correctly
"""
import requests
import json
import sys

def test_arima_forecast():
    """Test ARIMA forecast question"""
    print("\n" + "="*70)
    print("TEST 1: ARIMA Forecast - India Unemployment")
    print("="*70)
    
    question = "what's the forecast of unemployment for india for the next 10 years?"
    print(f"\nQuestion: {question}\n")
    
    try:
        response = requests.post('http://127.0.0.1:5000/api/analyze', 
            json={
                'dataset': 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv',
                'question': question
            }, 
            timeout=180
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✓ Model Type: {data.get('model_type', 'N/A')}")
            print(f"✓ Has Interpretation: {'interpretation' in data}")
            print(f"✓ Has Diagnostics: {'diagnostics' in data}")
            print(f"✓ Has Model Result: {'model_result' in data}")
            
            print(f"\n--- Processing Logs ({len(data.get('logs', []))} total) ---")
            for log in data.get('logs', []):
                print(f"  {log}")
            
            if 'model_result' in data:
                result = data['model_result']
                print(f"\n--- Model Results ---")
                print(f"Forecast Next Period: {result.get('forecast_next_period')}")
                print(f"AR(1) Coefficient: {result.get('ar1_coef')}")
                print(f"RMSE: {result.get('rmse')}")
            
            if 'diagnostics' in data:
                print(f"\n--- Diagnostics Summary ---")
                print(data.get('diagnostics', ''))
            
            if 'interpretation' in data:
                print(f"\n--- AI Interpretation ---")
                interp = data.get('interpretation', '')
                print(interp[:500] + "..." if len(interp) > 500 else interp)
            
            print("\n✅ ARIMA TEST PASSED")
            return True
        else:
            error_data = response.json()
            print(f"\n❌ ERROR: {error_data.get('error')}")
            print("\n❌ ARIMA TEST FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        print("\n❌ ARIMA TEST FAILED")
        return False

def test_did_causal():
    """Test DiD causal question"""
    print("\n" + "="*70)
    print("TEST 2: Difference-in-Differences - Debt Impact on Growth")
    print("="*70)
    
    question = "does more debt in a country impact its economic growth?"
    print(f"\nQuestion: {question}\n")
    
    try:
        response = requests.post('http://127.0.0.1:5000/api/analyze', 
            json={
                'dataset': 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv',
                'question': question
            }, 
            timeout=180
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✓ Model Type: {data.get('model_type', 'N/A')}")
            print(f"✓ Has Interpretation: {'interpretation' in data}")
            print(f"✓ Has Diagnostics: {'diagnostics' in data}")
            print(f"✓ Has Model Result: {'model_result' in data}")
            
            print(f"\n--- Processing Logs ({len(data.get('logs', []))} total) ---")
            for log in data.get('logs', []):
                print(f"  {log}")
            
            if 'model_result' in data:
                result = data['model_result']
                print(f"\n--- Model Results ---")
                print(f"Treatment Effect: {result.get('treatment_effect')}")
                print(f"Standard Error: {result.get('se')}")
                print(f"P-value: {result.get('pvalue')}")
                print(f"R-squared: {result.get('r_squared')}")
            
            if 'diagnostics' in data:
                print(f"\n--- Diagnostics Summary ---")
                print(data.get('diagnostics', ''))
            
            if 'interpretation' in data:
                print(f"\n--- AI Interpretation ---")
                interp = data.get('interpretation', '')
                print(interp[:500] + "..." if len(interp) > 500 else interp)
            
            print("\n✅ DiD TEST PASSED")
            return True
        else:
            error_data = response.json()
            print(f"\n❌ ERROR: {error_data.get('error')}")
            
            if 'logs' in error_data:
                print(f"\n--- Logs ---")
                for log in error_data.get('logs', []):
                    print(f"  {log}")
            
            print("\n❌ DiD TEST FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        print("\n❌ DiD TEST FAILED")
        return False

if __name__ == '__main__':
    print("\n🧪 ESPRESSO API TESTING SUITE")
    print("Testing both prompts for flawless execution\n")
    
    # Test 1: ARIMA
    test1_passed = test_arima_forecast()
    
    # Test 2: DiD
    test2_passed = test_did_causal()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"ARIMA Forecast Test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"DiD Causal Test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print("="*70)
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED - System working flawlessly!")
        sys.exit(0)
    else:
        print("\n⚠️ SOME TESTS FAILED - Review errors above")
        sys.exit(1)
