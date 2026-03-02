# ESPRESSO - Technical Reference & Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           USER INPUT: Question + Data                        │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────▼────────────┐
         │   Parse Question (LLM) │
         │   - Identify intent    │
         │   - Extract entities   │
         └───────────┬────────────┘
                     │
         ┌───────────▼──────────────┐
         │   Map Columns (LLM)      │
         │   - Match to dataset     │
         │   - Handle pivoting      │
         └───────────┬──────────────┘
                     │
         ┌───────────▼──────────────┐
         │   Select Models (Rule)   │
         │   - Choose DiD or ARIMA  │
         │   - Validate structure   │
         └───────────┬──────────────┘
                     │
    ┌────────────────┴────────────────┐
    │                                  │
    ▼ STEP 1: Diagnostics            ▼ STEP 1: Diagnostics
  DiD Branch                          ARIMA Branch
    │                                  │
    ├─ Heteroscedasticity              ├─ Stationarity
    ├─ Multicollinearity               ├─ Autocorrelation
    ├─ Autocorrelation                 ├─ Normality
    ├─ Normality                       └─ [Print to Terminal]
    └─ [Print to Terminal]
    │                                  │
    ▼ STEP 2: Model                   ▼ STEP 2: Model
  run_diff_in_diff()                 run_arima()
    │                                  │
    ├─ Calculate effect                ├─ Fit AR(1)
    ├─ Compute SE & p-val              ├─ Generate forecast
    ├─ 95% CI                          ├─ Calculate RMSE
    └─ [Print to Terminal]             └─ [Print to Terminal]
    │                                  │
    ▼ STEP 3: Interpretation          ▼ STEP 3: Interpretation
  LLM Prompt with DiD stats          LLM Prompt with ARIMA stats
  (effect, SE, p-val, R², CI)        (forecast, AR coef, RMSE)
    │                                  │
    └──────────────┬──────────────────┘
                   │
         ┌─────────▼──────────┐
         │  Generate LLM      │
         │  Interpretation    │
         │  (5-point answer)  │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │  Create HTML       │
         │  Report with       │
         │  Diagnostics +     │
         │  Interpretation    │
         │  + Visualizations  │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │  OUTPUT:           │
         │  - Terminal output │
         │  - HTML report     │
         └────────────────────┘
```

---

## Module Reference

### `run.py` - Main Orchestration

**Entry Point:**
- `main(args)` - Orchestrates entire pipeline

**Flow:**
1. Load data via `load_data()`
2. Parse question via `parse_question()`
3. Map columns via `map_columns()`
4. Select models via `select_admissible_models()`
5. For each model:
   - Call diagnostics (Step 1)
   - Run model (Step 2)
   - Get interpretation (Step 3)
   - Store results
6. Generate HTML report
7. Output summary

**Key Variables:**
- `original_question` - User's original question (stored for interpretation)
- `model_results` - Dict with all model outputs
- `model_results[model_type]['diagnostics']` - Diagnostic results
- `model_results[model_type]['llm_interpretation']` - Interpretation text

---

### `diagnostics.py` - Pre-Analysis Checks

**Main Functions:**

#### `run_did_diagnostics(data, outcome_col, treatment_col, time_col, unit_col)`
Runs all 5 diagnostic tests for Difference-in-Differences

**Returns:**
```python
{
    'model': 'Difference-in-Differences',
    'checks': [
        {
            'test': 'Heteroscedasticity (Breusch-Pagan)',
            'is_violated': bool,
            'interpretation': str,
            'correction': str
        },
        # ... 4 more checks ...
    ],
    'violations': ['Breusch-Pagan', 'Durbin-Watson'],
    'corrections': ['Use robust standard errors (HC1)', '...']
}
```

#### `run_arima_diagnostics(data, outcome_col, time_col)`
Runs all 5 diagnostic tests for ARIMA

**Returns:** Same structure as `run_did_diagnostics()`

**Individual Test Functions:**

```python
def check_heteroscedasticity(residuals, y_fitted):
    """Breusch-Pagan test (p < 0.05 = violated)"""
    
def check_multicollinearity(X):
    """VIF calculation (VIF > 10 = violated)"""
    
def check_stationarity(series, name='Series'):
    """ADF test (p < 0.05 = violated, i.e., non-stationary)"""
    
def check_autocorrelation(residuals):
    """Durbin-Watson test (DW ≈ 2 is good, <1.5 or >2.5 = violated)"""
    
def check_normality_of_residuals(residuals):
    """Shapiro-Wilk test (p < 0.05 = violated, i.e., non-normal)"""
```

**Each returns:**
```python
{
    'test': 'Test Name',
    'is_violated': bool,
    'interpretation': 'Human-readable result',
    'correction': 'Suggested fix'
}
```

---

### `interpretation.py` - LLM Interpretation

**Main Function:**

#### `interpret_results(question, outcome_name, treatment_name, model_type, result_dict)`

Feeds model results to Gemini with context-aware prompt

**Input:**
- `question` (str): Original user question
- `outcome_name` (str): Outcome variable name
- `treatment_name` (str): Treatment variable name
- `model_type` (str): 'diff_in_diff' or 'arima'
- `result_dict` (dict): Model results with statistics

**Returns:**
- (str): 5-point interpretation answering original question

**Process for DiD:**
1. Extract: effect, SE, p-value, R², N
2. Build prompt with all statistics
3. Request 5-point interpretation
4. Return LLM response

**Process for ARIMA:**
1. Extract: forecast, AR coef, RMSE, last value
2. Build prompt with forecast details
3. Request 5-point interpretation
4. Return LLM response

#### `interpret_diagnostics(diagnostics_result)`

Formats diagnostic results for terminal display

**Input:**
```python
{
    'checks': [...],
    'violations': [...],
    'corrections': [...]
}
```

**Output:**
```
PRE-ANALYSIS DIAGNOSTICS (Model Type)
============================================================
   [FAIL] Test 1: Interpretation
   [OK] Test 2: Interpretation
   ...
VIOLATIONS DETECTED:
   - Violation 1
   - Violation 2
CORRECTIONS APPLIED:
   - Correction 1
   - Correction 2
```

---

### `llm.py` - LLM Integration

**Functions:**

#### `parse_question(question_text)`
Uses Gemini to understand user's question

**Returns:**
```python
{
    'type': 'causal_effect' | 'forecasting',
    'outcome_variable': str,
    'treatment_variable': str,
    'time_variable': str,
    'unit_variable': str
}
```

#### `map_columns(intent, column_samples)`
Maps intent variables to actual data columns

**Returns:**
```python
{
    'Outcome': {'type': 'column', 'value': 'col_name'},
    'Treatment': {'type': 'column', 'value': 'col_name'},
    'Time': {'type': 'column', 'value': 'col_name'},
    'Unit': {'type': 'column', 'value': 'col_name'}
}
```

#### `query_gemini(prompt)` [NEW]
Generic function to query Gemini API

**Input:**
- `prompt` (str): Question/instruction for LLM

**Returns:**
- (str): LLM response or empty string if error

**Error Handling:**
- Catches API errors (429, 400, etc.)
- Returns empty string instead of crashing
- Prints error message to terminal

---

### `models.py` - Statistical Models

#### `run_diff_in_diff(data, outcome_col, treatment_col, time_col, unit_col)`

Difference-in-Differences estimation

**Returns:**
```python
{
    'treatment_effect': float,       # Beta coefficient
    'se': float,                     # Standard error
    'pvalue': float,                 # p-value (two-tailed)
    'ci_lower': float,               # 95% CI lower bound
    'ci_upper': float,               # 95% CI upper bound
    'r_squared': float,              # Model R²
    't_stat': float,                 # t-statistic
    'n_obs': int,                    # Number of observations
    'model': str                     # Model name
}
```

#### `run_arima(data, outcome_col, time_col)`

ARIMA (AR(1)) forecasting

**Returns:**
```python
{
    'forecast_next_period': float,   # Forecasted value
    'ar1_coef': float,               # AR(1) coefficient
    'rmse': float,                   # Root mean squared error
    'last_value': float,             # Last observed value
    'model': str                     # Model name
}
```

---

### `html_report.py` - Report Generation

**Key Function:**

#### `_format_diagnostics(diagnostics)`

Converts diagnostic dict to HTML with styling

**Input:**
```python
{
    'checks': [...],
    'violations': [...],
    'corrections': [...]
}
```

**Output:**
HTML string with:
- Diagnostic checks with color-coded status ([OK]=green, [FAIL]=red)
- Violations list
- Corrections list

**CSS Classes:**
- `.diagnostics-section` - Light blue background
- `.check-pass` - Green text color
- `.check-fail` - Red text color
- `.llm-interpretation` - Beige background

**Integration Points:**
- DiD section: Includes diagnostics after result metrics
- ARIMA section: Includes diagnostics after result metrics
- Both: Include LLM interpretation section after diagnostics

---

## Data Structures

### Diagnostics Result

```python
{
    'model': 'Difference-in-Differences',
    'checks': [
        {
            'test': 'Test Name',
            'is_violated': bool,
            'interpretation': 'Result description',
            'correction': 'Suggested fix'
        },
        # ... more checks ...
    ],
    'violations': ['Violation 1', 'Violation 2'],
    'corrections': ['Correction 1', 'Correction 2']
}
```

### Model Results (DiD)

```python
{
    'model': 'diff_in_diff',
    'treatment_effect': 0.40,
    'se': 0.83,
    'pvalue': 0.6387,
    'ci_lower': -1.23,
    'ci_upper': 2.03,
    'r_squared': 0.1167,
    't_stat': 0.479,
    'n_obs': 20,
    'diagnostics': {...},           # From diagnostics module
    'llm_interpretation': 'Text...'  # From interpretation module
}
```

### Model Results (ARIMA)

```python
{
    'model': 'arima',
    'forecast_next_period': 105.5,
    'ar1_coef': 0.85,
    'rmse': 2.1,
    'last_value': 100.0,
    'diagnostics': {...},           # From diagnostics module
    'llm_interpretation': 'Text...'  # From interpretation module
}
```

---

## Execution Flow (Detailed)

### Step 1: Diagnostics

**Input:** Model type, data, column names  
**Process:**
1. Select diagnostic function (DiD or ARIMA)
2. Run each test in sequence
3. Collect results with violations
4. Generate corrections list
5. Return structured dict

**Output:** Diagnostics dict  
**Terminal:** Formatted with [OK]/[FAIL] status

### Step 2: Model

**Input:** Data, column names, model type  
**Process:**
1. Select model function (DiD or ARIMA)
2. Execute model with data
3. Calculate all statistics
4. Return results dict

**Output:** Model results dict with all statistics  
**Terminal:** Formatted result summary

### Step 3: Interpretation

**Input:** Original question, model results, model type  
**Process:**
1. Extract key statistics from results
2. Build detailed prompt with context
3. Call `query_gemini()` with prompt
4. Return LLM response (5-point explanation)

**Output:** Interpretation text  
**Terminal:** Plain-English explanation  
**Stored:** In model_results['llm_interpretation']

---

## Error Handling

### Data Errors
- Invalid file path → "File not found"
- Missing columns → "Column not found"
- Insufficient data → "Not enough observations"

### API Errors
- Rate limit (429) → Retry wait or fail gracefully
- Auth error (403) → Check credentials
- Timeout → Use default interpretation

### Model Errors
- Singular matrix → DiD regression fails
- All zeros/constants → ARIMA fails
- Caught and reported in results

### Diagnostic Errors
- NaN/inf values → Individual test skipped
- Test-specific errors → Recorded in checks
- Non-fatal → Pipeline continues

---

## Performance Optimization Tips

### Diagnostics Optimization
- VIF only for small X (< 100 columns)
- ADF test slow for large series (use sampling)
- Parallel execution possible for 5 tests

### LLM Optimization
- Cache identical prompts
- Use shorter prompts for rate limiting
- Batch multiple analyses

### HTML Generation
- Avoid regenerating plots (cache SVG)
- Minimize CSS (inline for small reports)
- Compress final HTML

---

## Testing Checklist

For developers modifying code:

- [ ] Diagnostic tests run without error
- [ ] Violations correctly detected (p-value thresholds)
- [ ] Corrections list non-empty when violations exist
- [ ] Model executes with correct statistics
- [ ] LLM interpretation answers original question
- [ ] HTML report generates with all sections
- [ ] Terminal output formatting is correct
- [ ] No Unicode encoding issues
- [ ] Error handling catches edge cases
- [ ] Results match between terminal and HTML

---

## Extension Points

### Adding New Diagnostic Tests

1. Create test function in `diagnostics.py`:
```python
def check_my_test(data, column):
    """Test for something specific."""
    # ... computation ...
    return {
        'test': 'My Test Name',
        'is_violated': p_value < 0.05,
        'interpretation': 'Result description',
        'correction': 'How to fix it'
    }
```

2. Add to `run_did_diagnostics()`:
```python
checks.append(check_my_test(data, outcome_col))
```

3. Add correction suggestion logic

### Adding New Model

1. Implement in `models.py`:
```python
def run_my_model(data, ...):
    # ... computation ...
    return {
        'model': 'my_model',
        'result': value,
        # ... other stats ...
    }
```

2. Update `selector.py` to recognize when model is valid

3. Add case in `run.py` for model execution

4. Update `html_report.py` to visualize results

---

## Dependencies & Versions

```
Python: 3.14+
pandas: 1.x+
numpy: 1.x+
scipy: 1.x+ (for statistical tests)
google-genai: Latest (Gemini API)
matplotlib: 3.x+ (for plotting)
```

---

## Documentation References

- **USER_GUIDE.md** - End user documentation
- **PHASE4_STATUS.md** - Project status and completion report
- **PHASE4_COMPLETE.md** - Detailed feature breakdown
- **CODE COMMENTS** - Inline documentation in source files

---

**Last Updated:** January 31, 2025  
**Maintainer:** Espresso Development Team  
**Version:** 1.0
