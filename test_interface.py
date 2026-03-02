#!/usr/bin/env python3
"""Test the web interface with various questions"""

import requests
import json
import time

BASE_URL = 'http://localhost:5000'
DATASET = 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv'

QUESTIONS = [
    'does more debt in a country impact its economic growth?',
    "what's the forecast of unemployment for india for the next 10 years?",
]

def test_question(question):
    """Test a single question"""
    print(f"\n\n{'='*70}")
    print(f"TESTING: {question}")
    print(f"{'='*70}")
    
    try:
        response = requests.post(f'{BASE_URL}/api/analyze', 
            json={'dataset': DATASET, 'question': question},
            timeout=30
        )
        
        print(f"\n📊 HTTP Status: {response.status_code}")
        result = response.json()
        
        if 'error' in result:
            print(f"\n❌ ERROR: {result['error']}")
            if 'logs' in result:
                print("\n📋 Logs before error:")
                for log in result['logs']:
                    print(f"  {log}")
            return False
        else:
            print(f"\n✅ SUCCESS!")
            print(f"   Model Type: {result.get('model_type')}")
            print(f"   Intent: {result.get('intent', {}).get('question_type')}")
            
            print(f"\n📋 Process Logs:")
            for i, log in enumerate(result.get('logs', []), 1):
                print(f"  {i}. {log}")
            
            if 'interpretation' in result and result['interpretation']:
                print(f"\n💡 Interpretation Preview:")
                interpretation = result['interpretation'][:200]
                print(f"  {interpretation}...")
            
            return True
    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    print("\n🧪 ESPRESSO INTERFACE TESTING")
    print(f"Testing against: {BASE_URL}")
    print(f"Dataset: {DATASET}")
    
    results = {}
    for question in QUESTIONS:
        success = test_question(question)
        results[question] = success
        time.sleep(1)  # Be nice to the server
    
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for question, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {question[:60]}")
