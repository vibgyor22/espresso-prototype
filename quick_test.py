import requests
import json

BASE_URL = 'http://localhost:5000'
DATASET = 'data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv'

print('\n' + '='*70)
print('TEST 1: Forecast Question')
print('='*70)

response = requests.post(f'{BASE_URL}/api/analyze', 
    json={'dataset': DATASET, 'question': 'what is the forecast of unemployment for india for the next 10 years?'},
    timeout=30
)

print(f'Status: {response.status_code}')
result = response.json()

if 'error' in result:
    print(f'ERROR: {result["error"]}')
    print(f'Logs: {result.get("logs", [])}')
else:
    print(f'Model: {result.get("model_type")}')
    print(f'Logs: {len(result.get("logs", []))} steps')
    if 'interpretation' in result:
        interp = result['interpretation']
        if len(interp) > 300:
            print(f'Interpretation (first 300 chars): {interp[:300]}...')
        else:
            print(f'Interpretation: {interp}')
    print(f'Result keys: {result.keys()}')

print('\n' + '='*70)
print('TEST 2: Causal Question')
print('='*70)

response2 = requests.post(f'{BASE_URL}/api/analyze', 
    json={'dataset': DATASET, 'question': 'does more debt in a country impact its economic growth?'},
    timeout=30
)

print(f'Status: {response2.status_code}')
result2 = response2.json()

if 'error' in result2:
    print(f'ERROR: {result2["error"]}')
    print(f'Logs: {result2.get("logs", [])}')
else:
    print(f'Model: {result2.get("model_type")}')
    print(f'Logs: {len(result2.get("logs", []))} steps')
