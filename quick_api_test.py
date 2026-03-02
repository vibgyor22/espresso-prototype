"""
Simple API test using a separate Python process
Run this while Flask server is running in another terminal
"""
import requests
import json
import time

print("🧪 Testing Espresso API")
print("Make sure Flask server is running on http://127.0.0.1:5000\n")

time.sleep(1)

# Test ARIMA
print("=" * 70)
print("TEST 1: ARIMA Forecast")
print("=" * 70)

try:
    response = requests.post(
        'http://127.0.0.1:5000/api/analyze',
        json={
            'dataset': 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv',
            'question': "what's the forecast of unemployment for india for the next 10 years?"
        },
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"✅ Model: {data.get('model_type')}")
        print(f"✅ Logs: {len(data.get('logs', []))} entries")
        print("\nFirst 10 logs:")
        for log in data.get('logs', [])[:10]:
            print(f"  {log}")
    else:
        print(f"❌ Status: {response.status_code}")
        print(f"❌ Error: {response.json().get('error')}")
        
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n")

# Test DiD
print("=" * 70)
print("TEST 2: DiD Causal")
print("=" * 70)

try:
    response = requests.post(
        'http://127.0.0.1:5000/api/analyze',
        json={
            'dataset': 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv',
            'question': "does more debt in a country impact its economic growth?"
        },
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"✅ Model: {data.get('model_type')}")
        print(f"✅ Logs: {len(data.get('logs', []))} entries")
    elif response.status_code == 400:
        print(f"⚠️ Status: {response.status_code} (Expected - wide format)")
        data = response.json()
        print(f"⚠️ Reason: {data.get('error')[:100]}...")
        print("✅ This is correct behavior for wide-format data")
    else:
        print(f"❌ Status: {response.status_code}")
        print(f"❌ Error: {response.json().get('error')}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
