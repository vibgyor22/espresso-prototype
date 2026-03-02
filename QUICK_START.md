# Espresso Prototype - Quick Start Guide

## What is Espresso?

Espresso is a statistical inference engine that makes rigorous quantitative analysis accessible to non-coders. You ask a question, Espresso figures out which statistical model applies, and runs it automatically.

**Core Philosophy**: LLM handles language understanding, rules enforce statistical rigor, humans stay in control.

---

## 🚀 Quick Start

### Installation
```bash
pip install pandas numpy scipy google-generativeai
```

### Run Analysis
```bash
python run.py --data "path/to/your/data.csv" --question "Your research question here"
```

### Examples

**Forecast Question:**
```bash
python run.py --data "data/test_panel.csv" --question "What will unemployment be next year?"
```
Output: ARIMA model forecasts next period value with confidence interval

**Causal Question:**
```bash
python run.py --data "data/test_causal.csv" --question "Does policy treatment affect GDP growth?"
```
Output: Difference-in-differences treatment effect with statistical significance

---

## 📋 Supported Question Types

### 1. Forecasting
Ask: "What will [variable] be [when]?"
- Example: "What will unemployment be next year?"
- Example: "Forecast inflation for 2027"
- Model Used: ARIMA (AR(1) autoregressive)
- Requirements: Time series data with dates/years

### 2. Causal Effects  
Ask: "Does [treatment] affect [outcome]?"
- Example: "Does government spending increase GDP growth?"
- Example: "Do minimum wage increases reduce employment?"
- Model Used: Difference-in-Differences (DiD)
- Requirements: Panel data (units over time) with treatment variation

---

## 📊 Data Format

### ✓ Tidy Format (Recommended)
```
country,year,outcome,treatment
USA,2020,5.2,1
USA,2021,4.8,1
UK,2020,6.1,0
UK,2021,5.9,0
```

### ✓ Wide Format (Auto-Detected)
```
Country,Indicator,2020,2021,2022
USA,GDP Growth,2.5,5.7,2.1
UK,GDP Growth,1.3,7.4,0.5
USA,Unemployment,3.7,4.2,3.6
UK,Unemployment,4.5,4.1,3.9
```
*System automatically pivots to long format*

---

## 🔬 How It Works (5 Steps)

### Step 1: Load Data
- Reads CSV file into memory
- Checks dimensions and column names
- Validates no critical missing values

### Step 2: Understand Question
- LLM parses your question
- Identifies: question_type (forecast/causal_effect)
- Identifies: outcome, treatment, time, unit variables

### Step 3: Map Variables
- LLM inspects first few rows of data
- Matches logical variable names to actual columns
- Detects if data needs pivoting
- **Auto-applies mapping** (no user confirmation needed)

### Step 4: Validate Data
- Checks if data structure matches model requirements
- Confirms necessary variables exist and vary
- Rejects invalid models with clear reasons

### Step 5: Execute & Display
- Runs the valid statistical model(s)
- Shows formatted results table
- Provides human-readable interpretation
- Displays significance codes (*, **, ***)

---

## 📈 Model Details

### Difference-in-Differences (DiD)
**When to use**: Estimate causal treatment effects in panel data

**Formula**:
```
outcome = β₀ + β₁(treated) + β₂(post) + β₃(treated×post) + ε
         treatment effect = β₃
```

**Output**:
- Treatment effect (causal estimate)
- Standard error & 95% CI
- p-value & significance level
- R² (variance explained)
- Number of observations

**Example Result**:
```
Treatment Effect: 0.397619
Standard Error:   0.830702
t-statistic:      0.4787
p-value:          0.638660  [NOT SIGNIFICANT]
R-squared:        0.1167
```

---

### ARIMA (AR(1) Autoregressive)
**When to use**: Forecast next value in time series

**Formula**:
```
y_t = c + φ₁·y_{t-1} + ε_t
```

**Output**:
- AR(1) coefficient (persistence)
- Forecast for next period
- AIC (model fit quality)
- RMSE (prediction error)
- Dynamics interpretation

**Example Result**:
```
AR(1) Coefficient:    -0.153846
Intercept:             5.364957
Forecast (t+1):        4.652137
AIC:                   2.5005
RMSE:                  0.778864
```

---

## ✅ What Espresso Validates

### For Causal Models (DiD)
- ✓ Data is panel structure (units × time)
- ✓ Treatment variable varies across units
- ✓ Outcome variable exists and is numeric
- ✗ Rejects if: treatment doesn't vary, data isn't panel

### For Forecasting Models (ARIMA)
- ✓ Outcome variable is numeric
- ✓ Time variable exists and is ordered
- ✓ At least 3 observations
- ✗ Rejects if: missing values, single observation

---

## 🎯 Typical Output Example

```
======================================================================
ESPRESSO PROTOTYPE - Statistical Inference Engine
======================================================================

Step 1: Loading data from: data/test_panel.csv
   [OK] Loaded 12 rows, 4 columns

Step 2: Analyzing question...
   Question: "What will unemployment be next year?"
   [OK] Question understood:
      Type: forecast
      Outcome variable: unemployment
      Time variable: year

Step 3: Checking which statistical models are valid...

======================================================================
RESULTS
======================================================================

   Running ARIMA...

   ARIMA (AR(1)) MODEL RESULTS
   ------------------------------------------------------------------
   |  AR(1) Coefficient |       -0.153846         |
   |  Intercept         |        5.364957         |
   |  Forecast (t+1)    |        4.652137         |
   |  AIC               |          2.5005         |
   |  RMSE              |        0.778864         |
   ------------------------------------------------------------------

   >> AR(1) process shows mean-reverting dynamics
   >> Next period forecast: 4.6521

======================================================================
MODEL COMPARISON SUMMARY
======================================================================

   Model 1: ARIMA (AR(1))
   Forecast: 4.652137  RMSE: 0.778864

======================================================================
Analysis complete.
======================================================================
```

---

## ⚙️ System Components

| File | Purpose | Lines |
|------|---------|-------|
| `run.py` | Main orchestration & output | 298 |
| `llm.py` | Natural language understanding | ~120 |
| `models.py` | OLS & AR(1) implementations | 149 |
| `selector.py` | Model validation rules | ~40 |
| `data_utils.py` | Data loading & pivoting | ~80 |
| `model_specs.py` | Model definitions | ~30 |

---

## 🔧 Customization

### Change LLM Model
Edit `llm.py` to use different Google model:
```python
model = genai.GenerativeModel("gemini-2.0-flash-lite")  # ← change this
```

### Add New Model
1. Define in `model_specs.py`
2. Implement in `models.py`
3. Add selection rule in `selector.py`

### Change Data Path
```bash
python run.py --data "your/custom/path.csv" --question "Question"
```

---

## ❓ FAQ

**Q: Do I need coding experience?**  
A: No! Just CSV file + English question + one command.

**Q: Can I use my own data?**  
A: Yes! Any CSV with proper column names.

**Q: How does it know which model to use?**  
A: Automatic detection based on question type + data structure.

**Q: What if the LLM mapping fails?**  
A: Falls back to original column names and reports which models aren't valid.

**Q: Can I use data with missing values?**  
A: Yes, but rows with missing outcome/treatment/time are dropped automatically.

**Q: What's the 95% confidence interval?**  
A: Effect ± 1.96 × SE (for approximately normal distributions).

---

## 🐛 Troubleshooting

### "Module not found" error
```bash
pip install pandas numpy scipy google-generativeai
```

### LLM API error
- Check internet connection
- Verify `GOOGLE_API_KEY` environment variable is set
- Check API quota not exceeded

### "Treatment doesn't vary" error
- Outcome and treatment must be different variables
- Treatment must have multiple distinct values
- Check for typos in variable names

### Unicode/encoding errors
- This should be fixed in latest version
- If persists, try: `chcp 65001` (Windows) to enable UTF-8

---

## 📞 Support

For issues or questions:
1. Check this guide first
2. Review example files in `data/` folder
3. Check logs in terminal output
4. Examine `IMPLEMENTATION_SUMMARY.md` for architecture details

---

**Version**: 1.0 (January 2026)  
**Status**: Production-ready for tidy panel data  
**License**: Internal use only  
**Last Updated**: 2026-01-30
