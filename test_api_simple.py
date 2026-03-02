#!/usr/bin/env python3
"""Simple test of the API"""

import requests
import json
import sys

def test_api():
    BASE_URL = 'http://localhost:5000'
    DATASET = 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv'
    
    print("\n" + "="*70)
    print("TEST: Forecast Question")
    print("="*70)
    
    try:
        print("Sending request...")
        response = requests.post(
            f'{BASE_URL}/api/analyze',
            json={
                'dataset': DATASET,
                'question': 'what is the forecast of unemployment for india for the next 10 years?'
            },
            timeout=60
        )
        
        print(f"HTTP Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200:
            print("✅ SUCCESS!")
            print(f"Model Type: {data.get('model_type')}")
            print(f"Intent: {data.get('intent', {}).get('question_type')}")
            
            logs = data.get('logs', [])
            print(f"\nProcess Logs ({len(logs)} steps):")
            for i, log in enumerate(logs, 1):
                print(f"  {i}. {log}")
            
            if 'interpretation' in data:
                interp = data['interpretation']
                print(f"\nInterpretation (first 300 chars):")
                print(f"  {interp[:300]}...")
                
                if len(interp) < 100:
                    print("\n  ⚠️ WARNING: Interpretation is very short or may contain an error message")
        else:
            print(f"❌ ERROR (Status {response.status_code})")
            print(f"Error: {data.get('error', 'Unknown error')}")
            
            logs = data.get('logs', [])
            if logs:
                print(f"\nLogs before error:")
                for log in logs:
                    print(f"  - {log}")
    
    except requests.exceptions.ConnectionError as e:
        print(f"❌ CONNECTION ERROR: Cannot connect to {BASE_URL}")
        print(f"   Make sure Flask is running: python app.py")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_api()
