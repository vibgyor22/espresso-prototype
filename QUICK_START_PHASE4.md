# ESPRESSO - Quick Start Guide (Phase 4)

## What is Espresso?

An **accessible statistical analysis engine** that turns plain-language questions into statistical results with LLM-powered interpretation.

**You ask:** "Does treatment increase growth?"  
**Espresso does:** Pre-analysis checks → Statistical model → AI-powered interpretation  
**You get:** 3-step report (diagnostics + results + explanation) in terminal + HTML

---

## Installation (One-Time)

```bash
cd c:\Users\vibho\Documents\espresso-prototype

# Ensure dependencies installed
pip install pandas numpy scipy google-genai matplotlib

# Set API key
# Create .env file with: GOOGLE_API_KEY=your_key_here
```

---

## Basic Usage

### Simplest Command

```bash
python run.py --data data/test_causal.csv --question "Does treatment cause gdp_growth?"
```

### What Happens

1. **Terminal shows 3-step output:**
   - STEP 1: Pre-analysis diagnostics (5 tests, pass/fail status)
   - STEP 2: Model results (effect, p-value, confidence interval)
   - STEP 3: LLM interpretation (5-point plain-English explanation)

2. **HTML report generated:**
   - File saved to: `outputs/espresso_report_[timestamp].html`
   - Open in browser for formatted view with visualizations

---

## Your Data Format

### For Causal Questions (Diff-in-Diff)

Need **panel data** (multiple units × multiple years):

```csv
country,year,treatment,gdp_growth
USA,2010,0,1.2
USA,2011,0,1.5
USA,2012,1,1.6
UK,2010,0,0.8
UK,2011,0,1.0
UK,2012,1,1.5
```

### For Forecast Questions (ARIMA)

Need **time series** (single unit × many time periods):

```csv
time,value
1,100.5
2,102.3
3,104.1
4,105.8
5,107.2
```

---

## Example Workflows

### Example 1: Causal Effect Analysis

**Your question:** "Does higher government spending reduce unemployment?"

**Command:**
```bash
python run.py --data data/econ.csv --question "Does higher government spending reduce unemployment?"
```

**Terminal Output:**
```
STEP 1: PRE-ANALYSIS DIAGNOSTICS
   [OK] Heteroscedasticity: Equal variance ✓
   [OK] Multicollinearity: Low correlation ✓
   [FAIL] Autocorrelation: Serial correlation detected ✗
   [OK] Normality: Normal residuals ✓

VIOLATIONS: Autocorrelation detected
CORRECTIONS: Use robust standard errors or ARIMA

STEP 2: RUNNING DIFF-IN-DIFF MODEL
   Effect: -0.85 (SE 0.32)
   p-value: 0.0089 **
   95% CI: [-1.48, -0.22]
   R²: 0.423

STEP 3: LLM INTERPRETATION
   1. Statistically Significant? YES (p < 0.01)
   2. Magnitude: Government spending reduces unemployment by ~0.85%
   3. Plain English: Higher spending is associated with lower unemployment
   4. Answer: Yes, spending appears to reduce unemployment
   5. Limitations: Autocorrelation detected, use with caution
```

**HTML Report:**
- Diagnostics section (highlighted violations)
- Statistical summary with effect size
- LLM explanation in plain language
- Visualization of treatment effect

---

### Example 2: Time Series Forecast

**Your question:** "What will GDP be next quarter?"

**Command:**
```bash
python run.py --data data/gdp_timeseries.csv --question "What is the forecast for next quarter?"
```

**Terminal Output:**
```
STEP 1: PRE-ANALYSIS DIAGNOSTICS
   [FAIL] Stationarity: Non-stationary trend ✗
   [OK] Autocorrelation: Moderate autocorrelation
   [OK] Normality: Normal residuals ✓

VIOLATIONS: Non-stationary process
CORRECTIONS: Difference the series or use ARIMA with differencing

STEP 2: RUNNING ARIMA MODEL
   Forecast Next Period: 105.2
   Last Value: 103.8
   Change: +1.4 (+1.35%)
   AR(1) Coefficient: 0.89
   Process: Stable

STEP 3: LLM INTERPRETATION
   1. Direction: GDP expected to increase
   2. Magnitude: Growth of +1.4 units (1.35%)
   3. Trend: Strong positive momentum (AR coef = 0.89)
   4. Answer: GDP forecast is 105.2 for next period
   5. Limitations: Based on recent pattern; may not capture future changes
```

---

## Understanding the Output

### STEP 1: Pre-Analysis Diagnostics

**What it does:** Tests if your data meets statistical assumptions

| Status | Meaning | Action |
|--------|---------|--------|
| [OK] | Test passed | Good, proceed with model |
| [FAIL] | Test failed | Violation detected, see correction |

**Tests:**
- **Heteroscedasticity**: Are errors equally spread? (p < 0.05 = fail)
- **Multicollinearity**: Are predictors independent? (VIF > 10 = fail)
- **Autocorrelation**: Are residuals independent? (DW ≠ 2 = fail)
- **Normality**: Are residuals normally distributed? (p < 0.05 = fail)
- **Stationarity**: Is time series stable? (ADF p < 0.05 = fail)

---

### STEP 2: Model Results

**What it shows:** Statistical evidence for your question

| Stat | Meaning | Example |
|------|---------|---------|
| **Effect** | Size of treatment impact | 0.40 units |
| **SE** | Uncertainty in effect | ±0.83 |
| **p-value** | Probability effect is zero | 0.64 (64%) |
| **95% CI** | Confidence interval | [-1.23, 2.03] |
| **R²** | Variance explained | 0.1167 (11.67%) |

**Interpreting p-values:**
- **p < 0.05**: Statistically significant ✓
- **p > 0.05**: Not statistically significant ✗

---

### STEP 3: LLM Interpretation

**What it does:** Explains results in plain English

**5-Point Breakdown:**
1. **Statistical Significance** - Is effect real or random?
2. **Practical Magnitude** - How big is the effect?
3. **Plain English** - What does this mean?
4. **Direct Answer** - Does it answer your question?
5. **Limitations** - What are the caveats?

---

## Output Files

### Terminal Output
Printed directly to console during execution. Shows all 3 steps.

### HTML Report
**Location:** `outputs/espresso_report_[timestamp].html`

**Contains:**
- Executive summary
- Pre-analysis diagnostics with color-coded results
- Statistical results and effect sizes
- LLM interpretation
- Visualizations:
  - Confidence interval plots
  - Effect size comparisons
  - Time series forecasts
- Data table with summary statistics

**Open in browser:**
```bash
# Windows
start outputs\espresso_report_[timestamp].html

# Mac/Linux
open outputs/espresso_report_[timestamp].html
```

---

## Common Questions

### Q: What data format do I need?

**For Causal (DiD):** Panel data with columns for unit, time, treatment, outcome
**For Forecasting (ARIMA):** Time series with time index and values

### Q: How much data do I need?

**Minimum:** 
- DiD: 10 observations (2 units × 5 years)
- ARIMA: 20 observations

**Recommended:**
- DiD: 100+ observations (10+ units × 10+ years)
- ARIMA: 50+ observations (continuous series)

### Q: What if diagnostics fail?

Espresso still runs the model but flags the issue. The interpretation will note limitations. Consider:
- Using suggested corrections
- Trying alternative models
- Collecting more data

### Q: Can I use different column names?

Yes! Tell Espresso what you're looking for, not the exact names:
```bash
python run.py --data data.csv --question "Does schooling affect earnings?"
```

Espresso maps "schooling" → actual education column, "earnings" → actual income column.

### Q: Why is my p-value so high?

Usually means:
- Effect is small relative to noise
- Sample size is small
- Confounding variables not controlled
- Data is noisy

This is **normal**! The analysis is correct. LLM interpretation explains limitations.

---

## Troubleshooting

### Command Won't Run

```bash
# Check Python version
python --version  # Should be 3.8+

# Check dependencies
pip list | findstr "pandas numpy scipy"

# Check file exists
dir data\test_causal.csv
```

### API Rate Limit Error

```
Error calling Gemini: 429 RESOURCE_EXHAUSTED
```

**Fix:** Wait 30 seconds and try again. API has rate limits.

### Unicode Character Error

```
'charmap' codec can't encode character
```

**Fix:** Already fixed in latest version. Update with:
```bash
python run.py ...  # Should work now
```

### No Valid Models Found

```
[ERROR] NO VALID MODELS FOUND
```

**Cause:** Data format doesn't match model requirements

**Fix:**
- For DiD: Ensure panel data (multiple units × years)
- For ARIMA: Ensure time series (one column of values)

---

## Tips for Best Results

✅ **Do:**
- Use clear column names
- Ask specific questions
- Check diagnostics for violations
- Review HTML report visualizations
- Note p-values and effect sizes

❌ **Don't:**
- Ignore diagnostic violations (they matter!)
- Over-interpret non-significant results
- Use data with missing values
- Assume correlation = causation

---

## Advanced Usage

### Run Specific Model

```bash
# Espresso auto-selects, but you can see all models attempted in output
# Currently supports: DiD (causal) and ARIMA (forecasting)
```

### Suppress HTML Generation

```bash
# Currently generates HTML by default
# Output is shown in outputs/ folder
```

### Batch Processing

```bash
# Run multiple questions on same dataset
python run.py --data data.csv --question "Q1"
python run.py --data data.csv --question "Q2"
python run.py --data data.csv --question "Q3"
# Each generates separate HTML report
```

---

## Documentation

For deeper dives, see:

- **USER_GUIDE.md** - Complete user documentation
- **PHASE4_STATUS.md** - Project status report
- **TECHNICAL_REFERENCE.md** - For developers
- **This file** - Quick start (you are here)

---

## Key Files

| File | Purpose |
|------|---------|
| `run.py` | Main entry point |
| `diagnostics.py` | 5 statistical tests |
| `models.py` | DiD and ARIMA implementations |
| `interpretation.py` | LLM result explanation |
| `html_report.py` | Report generation |
| `data/` | Sample datasets |
| `outputs/` | Generated HTML reports |

---

## Sample Commands

```bash
# Causal: Does treatment affect growth?
python run.py --data data/test_causal.csv --question "Does treatment cause gdp_growth?"

# Forecasting: Predict next value
python run.py --data data/test_panel.csv --question "What is the forecast for next period?"

# Custom question
python run.py --data data/custom.csv --question "Does X affect Y?"
```

---

## Next Steps

1. **Run example:** `python run.py --data data/test_causal.csv --question "Does treatment cause gdp_growth?"`
2. **Check output:** Look at terminal and open `outputs/espresso_report_*.html` in browser
3. **Read results:** Focus on STEP 3 (LLM interpretation) for plain-English explanation
4. **Use your data:** Replace with your CSV and your question
5. **Review diagnostics:** Check STEP 1 for any violations and follow suggestions

---

## Support

- Check **USER_GUIDE.md** for common questions
- Review **TECHNICAL_REFERENCE.md** for implementation details
- Check terminal output for specific error messages
- Ensure .env file has valid GOOGLE_API_KEY

---

**Version:** 1.0 (January 31, 2025)  
**Status:** Production Ready ✅

Start analyzing with: `python run.py --data <your_data.csv> --question "<your_question>"`
