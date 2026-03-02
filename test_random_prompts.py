"""
Test script to run 10 random prompts and check for inconsistencies
"""
import subprocess
import sys

# 10 diverse test prompts
test_prompts = [
    "forecast gdp for United States next 5 years",
    "what is the inflation forecast for Japan for the next 3 years?",
    "forecast unemployment for the largest economy in asia next 10 years",
    "predict gdp growth for Germany over the next 7 years",
    "what will happen to unemployment in Canada in the next 5 years?",
    "forecast inflation for the most populous country next 10 years",
    "gdp forecast for France next 5 years",
    "what is the unemployment outlook for Brazil for 10 years?",
    "forecast gdp for the happiest country in scandinavia next 5 years",
    "predict inflation for United Kingdom next 10 years"
]

data_file = "data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv"

results = []

print("=" * 80)
print("TESTING 10 RANDOM PROMPTS")
print("=" * 80)

for i, prompt in enumerate(test_prompts, 1):
    print(f"\n[Test {i}/10] {prompt}")
    print("-" * 80)
    
    cmd = [
        "python", "run_analysis.py",
        "--data", data_file,
        "--question", prompt
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )
        
        output = result.stdout + result.stderr
        
        # Check for key elements
        has_unit_identified = "Unit ->" in output or "identified unit" in output.lower()
        has_forecast_table = "FORECAST TABLE" in output
        has_interpretation = "INTERPRETATION" in output
        has_error = "ERROR" in output or result.returncode != 0
        
        # Extract unit if identified
        unit_name = None
        for line in output.split('\n'):
            if "Unit ->" in line:
                unit_name = line.split("Unit ->")[1].strip()
                break
            elif "Filtered to" in line:
                parts = line.split("Filtered to")[1].split(":")
                if parts:
                    unit_name = parts[0].strip()
                    break
        
        # Extract forecast periods
        forecast_periods = None
        for line in output.split('\n'):
            if "FORECAST TABLE" in line and "periods" in line:
                # Extract number between ( and periods
                import re
                match = re.search(r'\((\d+)\s+periods', line)
                if match:
                    forecast_periods = match.group(1)
                break
        
        result_summary = {
            'prompt': prompt,
            'unit_identified': has_unit_identified,
            'unit_name': unit_name,
            'forecast_table': has_forecast_table,
            'forecast_periods': forecast_periods,
            'interpretation': has_interpretation,
            'error': has_error,
            'exit_code': result.returncode
        }
        
        results.append(result_summary)
        
        print(f"  [OK] Unit: {unit_name if unit_name else 'NOT IDENTIFIED'}")
        print(f"  [OK] Forecast Periods: {forecast_periods if forecast_periods else 'N/A'}")
        print(f"  [OK] Has Interpretation: {'Yes' if has_interpretation else 'No'}")
        print(f"  [OK] Status: {'ERROR' if has_error else 'SUCCESS'}")
        
    except subprocess.TimeoutExpired:
        print(f"  [X] TIMEOUT - Test took too long")
        results.append({
            'prompt': prompt,
            'unit_identified': False,
            'unit_name': None,
            'forecast_table': False,
            'forecast_periods': None,
            'interpretation': False,
            'error': True,
            'exit_code': -1
        })
    except Exception as e:
        print(f"  [X] EXCEPTION: {e}")
        results.append({
            'prompt': prompt,
            'unit_identified': False,
            'unit_name': None,
            'forecast_table': False,
            'forecast_periods': None,
            'interpretation': False,
            'error': True,
            'exit_code': -1
        })

# Generate summary report
print("\n" + "=" * 80)
print("SUMMARY REPORT")
print("=" * 80)

successful = sum(1 for r in results if not r['error'])
failed = sum(1 for r in results if r['error'])
unit_identified = sum(1 for r in results if r['unit_identified'])
has_interpretation = sum(1 for r in results if r['interpretation'])

print(f"\nTotal Tests: {len(results)}")
print(f"Successful: {successful}")
print(f"Failed: {failed}")
print(f"Unit Identified: {unit_identified}/{len(results)}")
print(f"Interpretations Generated: {has_interpretation}/{len(results)}")

# Check for inconsistencies
print("\n" + "=" * 80)
print("INCONSISTENCIES DETECTED")
print("=" * 80)

inconsistencies = []

for r in results:
    issues = []
    
    if r['error']:
        issues.append("Failed to complete")
    
    if not r['unit_identified'] and ("country" in r['prompt'].lower() or "states" in r['prompt'].lower() or "japan" in r['prompt'].lower()):
        issues.append("Unit not identified despite country mention")
    
    if not r['interpretation']:
        issues.append("No interpretation generated")
    
    if not r['forecast_table'] and not r['error']:
        issues.append("No forecast table in output")
    
    if r['forecast_periods']:
        # Check if forecast periods match what was requested
        if "5 years" in r['prompt'] and r['forecast_periods'] != "5":
            issues.append(f"Asked for 5 years, got {r['forecast_periods']}")
        elif "3 years" in r['prompt'] and r['forecast_periods'] != "3":
            issues.append(f"Asked for 3 years, got {r['forecast_periods']}")
        elif "7 years" in r['prompt'] and r['forecast_periods'] != "7":
            issues.append(f"Asked for 7 years, got {r['forecast_periods']}")
        elif "10 years" in r['prompt'] and r['forecast_periods'] != "10":
            issues.append(f"Asked for 10 years, got {r['forecast_periods']}")
    
    if issues:
        inconsistencies.append({
            'prompt': r['prompt'],
            'unit': r['unit_name'],
            'issues': issues
        })

if inconsistencies:
    for inc in inconsistencies:
        print(f"\n[X] Prompt: {inc['prompt']}")
        print(f"  Unit: {inc['unit']}")
        for issue in inc['issues']:
            print(f"  - {issue}")
else:
    print("\n[OK] No inconsistencies detected!")

print("\n" + "=" * 80)
print("DETAILED RESULTS")
print("=" * 80)

for i, r in enumerate(results, 1):
    status = "[OK]" if not r['error'] else "[X]"
    print(f"\n{status} Test {i}: {r['prompt'][:60]}...")
    print(f"   Unit: {r['unit_name'] if r['unit_name'] else 'N/A'}")
    print(f"   Periods: {r['forecast_periods'] if r['forecast_periods'] else 'N/A'}")
    print(f"   Status: {'SUCCESS' if not r['error'] else 'FAILED'}")
