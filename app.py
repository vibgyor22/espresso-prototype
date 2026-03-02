"""
Espresso Web Interface - Advanced Chat-Style Statistical Analysis Platform
Modern UI with white and latte brown theme, integrated visualizations
"""

from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import base64
from io import BytesIO
import traceback

# Import Espresso modules
from data_utils import load_data, get_column_samples, pivot_indicator_panel, is_panel_data
from llm import parse_question, map_columns
from selector import select_admissible_models
from diagnostics import run_did_diagnostics, run_arima_diagnostics
from models import run_diff_in_diff, run_arima
from interpretation import interpret_results, interpret_diagnostics

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Store recent analyses
analyses_history = []
max_history = 20

def to_jsonable(obj):
    """Recursively convert objects to JSON-serializable types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, np.ndarray):
        return [to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.Series):
        return [to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return [to_jsonable(row) for row in obj.to_dict(orient='records')]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]
    return str(obj)

def get_available_datasets():
    """Get list of available datasets"""
    datasets = []
    data_dir = 'data'
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith('.csv'):
                file_path = os.path.join(data_dir, file)
                size = os.path.getsize(file_path) / (1024*1024)  # Size in MB
                datasets.append({
                    'name': file,
                    'path': file_path,
                    'size': f'{size:.2f}MB'
                })
    return sorted(datasets, key=lambda x: x['name'])


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'espresso-api'})


@app.route('/')
def index():
    """Render main chat interface"""
    datasets = get_available_datasets()
    return render_template('index.html', datasets=datasets)


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Run statistical analysis via API"""
    try:
        sys.stdout.flush()
        logs = []
        
        print("\n[API] ========== NEW ANALYSIS REQUEST ==========", flush=True)
        
        data = request.json
        data_file = data.get('dataset')
        question = data.get('question')
        
        print(f"[API] Dataset: {data_file}, Question: {question[:50]}...", flush=True)
        
        if not data_file or not question:
            return jsonify({'error': 'Dataset and question required'}), 400
        
        # Check file exists
        if not os.path.exists(data_file):
            return jsonify({'error': f'Dataset not found: {data_file}'}), 404
        
        # Load and analyze
        log_msg = f"[LOAD] Loading {os.path.basename(data_file)}..."
        logs.append(log_msg)
        print(f"[API] {log_msg}", flush=True)
        df = load_data(data_file)
        print(f"[API] Data loaded: {len(df)} rows", flush=True)
        logs.append(f"[OK] Loaded {len(df)} rows x {len(df.columns)} columns")
        
        log_msg = f"[PARSE] Parsing question..."
        logs.append(log_msg)
        print(f"[API] {log_msg}", flush=True)
        intent = parse_question(question)
        
        if not intent:
            return jsonify({'error': 'Could not understand question'}), 400
        logs.append(f"✓ Detected: {intent.get('question_type', 'unknown')} question")
        
        log_msg = f"[MAP] Mapping columns to variables..."
        logs.append(log_msg)
        print(f"[API] {log_msg}", flush=True)
        column_samples = get_column_samples(df)
        mapping = map_columns(intent, column_samples)
        logs.append(f"[OK] Mapped {len(mapping)} variables:")
        for key, val in mapping.items():
            if isinstance(val, dict) and 'value' in val:
                logs.append(f"     {key}: {val['value']}")
        print(f"[API] Mapping result: {list(mapping.keys())}", flush=True)
        
        # ============================================================
        # APPLY MAPPING: Handle pivot transformation if needed
        # ============================================================
        time_mapping = mapping.get('time')
        time_value = time_mapping.get('value') if isinstance(time_mapping, dict) else time_mapping
        if not mapping.get('pivot') and isinstance(time_value, list):
            mapping['pivot'] = True
        if not mapping.get('pivot') and mapping.get('year_columns'):
            mapping['pivot'] = True

        print(f"[API] Mapping pivot flag: {mapping.get('pivot', False)}", flush=True)
        
        if mapping.get('pivot'):
            try:
                log_msg = f"[PIVOT] Data is wide-format, pivoting to long..."
                logs.append(log_msg)
                print(f"[API] {log_msg}", flush=True)
                
                from data_utils import get_year_columns
                import re
                
                indicator_col = mapping.get('indicator_column', 'SERIES_CODE')
                year_cols = mapping.get('year_columns') or get_year_columns(df)
                
                # Pivot the data
                df_long, unit_col_detected, indicator_col_detected = pivot_indicator_panel(df, indicator_col=indicator_col, year_cols=year_cols)
                
                logs.append(f"[OK] Pivoted to {len(df_long)} rows")
                logs.append(f"     Unit: {unit_col_detected}, Indicator: {indicator_col_detected}")
                
                # Extract outcome indicator series
                out_val = mapping.get('outcome', {}).get('value') if isinstance(mapping.get('outcome'), dict) else mapping.get('outcome')
                outcome_df = None
                if out_val:
                    outcome_df = df_long[df_long[indicator_col_detected].astype(str).str.contains(re.escape(str(out_val)), case=False, na=False, regex=True)]
                    outcome_df = outcome_df[[unit_col_detected, 'year', 'value']].rename(columns={'value': out_val}).copy()
                    logs.append(f"[OK] Extracted outcome: {out_val} ({len(outcome_df)} rows)")
                
                # Extract treatment indicator series (if causal question)
                tr_val = mapping.get('treatment', {}).get('value') if isinstance(mapping.get('treatment'), dict) else mapping.get('treatment')
                treatment_df = None
                if tr_val and tr_val != 'None':
                    treatment_df = df_long[df_long[indicator_col_detected].astype(str).str.contains(re.escape(str(tr_val)), case=False, na=False, regex=True)]
                    treatment_df = treatment_df[[unit_col_detected, 'year', 'value']].rename(columns={'value': tr_val}).copy()
                    logs.append(f"[OK] Extracted treatment: {tr_val} ({len(treatment_df)} rows)")
                
                # Merge outcome and treatment
                if outcome_df is not None:
                    if treatment_df is not None:
                        df = outcome_df.merge(treatment_df, on=[unit_col_detected, 'year'], how='outer')
                        intent['outcome'] = out_val
                        intent['treatment'] = tr_val
                        logs.append(f"[OK] Merged outcome + treatment ({len(df)} rows)")
                    else:
                        df = outcome_df
                        intent['outcome'] = out_val
                        intent['treatment'] = None
                        logs.append(f"[OK] Using outcome only ({len(df)} rows)")
                    
                    intent['unit'] = unit_col_detected
                    intent['time'] = 'year'
                    
            except Exception as pivot_err:
                log_msg = f"[WARN] Pivot failed: {str(pivot_err)[:100]}"
                logs.append(log_msg)
                print(f"[API] {log_msg}", flush=True)
        
        log_msg = f"[SELECT] Selecting optimal model..."
        logs.append(log_msg)
        print(f"[API] {log_msg}", flush=True)
        models, rejected = select_admissible_models(intent, df)
        
        if not models:
            # Still no models after reshape attempt
            if intent.get('question_type') == 'causal_effect':
                error_msg = (
                    f"⚠️ Causal Analysis Not Possible\n\n"
                    f"Your question asks about causal effects: '{question}'\n\n"
                    f"<strong>What was tried:</strong>\n"
                    f"✓ Attempted to reshape wide-format data to long panel format\n"
                    f"✓ Re-mapped columns to find treatment and outcome variables\n"
                    f"✗ Could not identify consistent treatment variation across units\n\n"
                    f"<strong>Why it didn't work:</strong>\n"
                    f"The system needs data where:\n"
                    f"• Same outcome variable (e.g., GDP growth) across multiple countries\n"
                    f"• Same treatment variable (e.g., debt levels) across multiple countries\n"
                    f"• Variation in treatment across units (some countries have more/less debt)\n"
                    f"• Time variation showing before/after effects\n\n"
                    f"This dataset may contain {mapping.get('outcome', 'outcome')} and {mapping.get('treatment', 'treatment')} "
                    f"but not in a format that allows causal comparison.\n\n"
                    f"<strong>Suggestion:</strong> Try a forecast question instead, like 'What will happen to {intent.get('outcome', 'this variable')} next year?'"
                )
                return jsonify({
                    'error': error_msg,
                    'intent': intent,
                    'mapping': mapping,
                    'rejected_models': rejected,
                    'logs': logs
                }), 400
            
            return jsonify({
                'error': f'No valid models found for this data structure: {rejected}',
                'intent': intent,
                'mapping': mapping,
                'logs': logs
            }), 400
        
        # Run analysis for first valid model
        model_type = models[0]
        log_msg = f"[RUN] Running {model_type.upper()} analysis..."
        logs.append(log_msg)
        print(f"[API] {log_msg}", flush=True)
        
        result = {
            'question': question,
            'intent': intent,
            'model_type': model_type,
            'mapping': mapping,
            'timestamp': datetime.now().isoformat(),
            'logs': logs
        }
        
        if model_type == 'diff_in_diff':
            outcome_col = intent.get('outcome')
            treatment_col = intent.get('treatment')
            time_col = intent.get('time')
            unit_col = intent.get('unit')
            
            # Run diagnostics
            logs.append("[DIAG] Running diagnostic tests...")
            diag = run_did_diagnostics(df, outcome_col, treatment_col, time_col, unit_col)
            diag_summary = interpret_diagnostics(diag)
            logs.append(f"[OK] Diagnostics complete")
            
            # Run model
            logs.append("[EST] Estimating model...")
            model_result = run_diff_in_diff(df, outcome_col, treatment_col, time_col, unit_col)
            logs.append(f"[OK] Model estimated")
            
            # Get interpretation
            logs.append("[INTERP] Generating interpretation...")
            interpretation = interpret_results(
                question,
                outcome_col,
                treatment_col,
                'diff_in_diff',
                model_result,
                diag
            )
            logs.append("[OK] Analysis complete")
            
            result.update({
                'diagnostics': diag_summary,
                'diagnostics_data': diag,
                'model_result': model_result,
                'interpretation': interpretation
            })
            
        elif model_type == 'arima':
            # Get the outcome column
            outcome_col = intent.get('outcome')
            if not outcome_col:
                # Fallback: try to find from mapping
                if isinstance(mapping.get('outcome'), dict):
                    outcome_col = mapping['outcome'].get('value')
                elif isinstance(mapping.get('outcome'), str):
                    outcome_col = mapping['outcome']
            elif outcome_col not in df.columns:
                # If intent outcome isn't a column, fallback to mapping
                if isinstance(mapping.get('outcome'), dict):
                    outcome_col = mapping['outcome'].get('value')
                elif isinstance(mapping.get('outcome'), str):
                    outcome_col = mapping['outcome']
            
            # Get the time column
            time_col = intent.get('time')
            if not time_col:
                if isinstance(mapping.get('time'), dict):
                    time_col = mapping['time'].get('value')
                elif isinstance(mapping.get('time'), str):
                    time_col = mapping['time']
            elif time_col not in df.columns:
                if isinstance(mapping.get('time'), dict):
                    time_col = mapping['time'].get('value')
                elif isinstance(mapping.get('time'), str):
                    time_col = mapping['time']
            
            if not outcome_col or not time_col:
                return jsonify({
                    'error': f'Could not identify outcome or time columns for ARIMA',
                    'mapping': mapping,
                    'logs': logs
                }), 400
            
            # Run diagnostics
            logs.append("[DIAG] Running diagnostic tests...")
            diag = run_arima_diagnostics(df, outcome_col, time_col)
            diag_summary = interpret_diagnostics(diag)
            logs.append(f"[OK] Diagnostics complete")
            
            # Run model
            logs.append("[EST] Estimating model...")
            model_result = run_arima(df, outcome_col, time_col)
            logs.append(f"[OK] Model estimated")
            
            # Get interpretation
            logs.append("[INTERP] Generating interpretation...")
            interpretation = interpret_results(
                question,
                outcome_col,
                None,
                'arima',
                model_result,
                diag
            )
            logs.append(f"[OK] Analysis complete")
            
            result.update({
                'diagnostics': diag_summary,
                'diagnostics_data': diag,
                'model_result': model_result,
                'interpretation': interpretation
            })
        
        # Add to history
        analyses_history.insert(0, {
            'question': question,
            'model': model_type,
            'timestamp': result['timestamp'],
            'dataset': data_file
        })
        if len(analyses_history) > max_history:
            analyses_history.pop()
        
        return jsonify(to_jsonable(result))
        
    except Exception as e:
        print(f"\n[ERROR] Exception in analyze(): {str(e)}", flush=True)
        print(f"[ERROR] Type: {type(e).__name__}", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def get_history():
    """Get analysis history"""
    return jsonify(analyses_history)


@app.route('/api/datasets')
def get_datasets():
    """Get available datasets"""
    return jsonify(get_available_datasets())


if __name__ == '__main__':
    print("\n" + "="*60)
    print("ESPRESSO - Advanced Statistical Analysis Platform")
    print("="*60)
    print("Starting web interface on http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=False, port=5000, use_reloader=False)
