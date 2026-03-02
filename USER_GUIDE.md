# ESPRESSO - Complete User Guide

## Overview

**Espresso** is an accessible statistical analysis platform that combines:
- 🤖 **LLM Intelligence** (Gemini) for natural language understanding
- 📊 **Statistical Rigor** (pre-analysis diagnostics & validation)
- 📈 **Advanced Models** (Difference-in-Differences, ARIMA)
- 🎯 **Plain English Interpretation** (LLM-powered result explanation)

Ask a question in plain language. Get statistical results, diagnostics, and AI-powered interpretation.

---

## How It Works (3 Steps)

### **STEP 1: Pre-Analysis Diagnostics**

Before running any model, Espresso automatically checks if your data meets statistical assumptions:

```
PRE-ANALYSIS DIAGNOSTICS
============================================================
[OK] Heteroscedasticity: Equal error variance ✓
[FAIL] Multicollinearity: Correlated predictors detected ✗
[OK] Stationarity: Time series is stationary ✓
[FAIL] Autocorrelation: Serial correlation detected ✗
[OK] Normality: Residuals are normally distributed ✓

VIOLATIONS DETECTED:
- Breusch-Pagan test (heteroscedasticity)
- Durbin-Watson test (autocorrelation)

CORRECTIONS APPLIED:
- Use robust standard errors (HC1)
- Consider ARIMA or robust errors
```

**What it tests:**
1. **Heteroscedasticity** - Are errors equally spread?
2. **Multicollinearity** - Are predictors too correlated?
3. **Stationarity** - Is time series stable?
4. **Autocorrelation** - Do errors depend on each other?
5. **Normality** - Are residuals normally distributed?

---

### **STEP 2: Statistical Model**

Based on your question and diagnostics, Espresso runs the appropriate model:

**Difference-in-Differences (DiD):**
- For causal effect estimation with panel data
- Compares treatment vs. control groups over time
- Returns: effect size, standard error, p-value, confidence interval

**ARIMA (AR(1)):**
- For time series forecasting
- Autoregressive model predicting future values
- Returns: forecast, AR coefficient, stability check

Example output:
```
DIFFERENCE-IN-DIFFERENCES
Effect: 0.40 (SE: 0.83)
95% CI: [-1.23, 2.03]
t-stat: 0.479 | p-value: 0.6387
R²: 0.1167 | N: 20
Status: NOT SIGNIFICANT
```

---

### **STEP 3: LLM Interpretation**

Your statistical results are fed to an LLM with your original question to generate a plain-English explanation:

```
LLM INTERPRETATION

1. Statistical Significance:
   The analysis did NOT find a statistically significant effect.

2. Practical Magnitude:
   The estimated treatment effect is 0.40 units, but this is not 
   statistically significant, so we cannot draw firm conclusions.

3. Plain English Explanation:
   The data does not provide strong evidence that the treatment 
   caused changes in GDP growth.

4. Direct Answer to Your Question:
   "Does treatment cause GDP growth?" 
   Answer: No, not based on this analysis.

5. Limitations:
   The p-value (0.6387) is much higher than the 0.05 threshold,
   meaning this result could easily occur by chance. The R² of 0.1167
   indicates the model only explains 11.67% of variation, suggesting
   other factors are more important.
```

---

## Getting Started

### Installation

```bash
cd c:\Users\vibho\Documents\espresso-prototype
```

### Basic Usage

```bash
python run.py --data <path_to_data.csv> --question "<your_question>"
```

### Example 1: Causal Effect (DiD)

```bash
python run.py --data data/test_causal.csv --question "Does treatment cause gdp growth?"
```

**Input Data Format (Long/Tidy):**
```
country,year,treatment,gdp_growth
USA,2015,0,1.2
USA,2016,1,1.5
USA,2017,1,1.6
UK,2015,0,1.0
UK,2016,0,1.1
UK,2017,1,1.8
```

**Output:**
- Terminal: Diagnostics → Model Results → Interpretation
- HTML Report: `outputs/espresso_report_[timestamp].html` with all three sections

---

### Example 2: Time Series Forecast (ARIMA)

```bash
python run.py --data data/test_panel.csv --question "What is the forecast for gdp_growth?"
```

**Input Data Format:**
```
time_index,value
1,100.5
2,102.3
3,104.1
4,105.8
5,107.2
```

---

## Understanding Diagnostics

### What Each Test Means

**1. Heteroscedasticity (Breusch-Pagan)**
- **Passed**: Error variance is consistent across predictions ✓
- **Failed**: Error variance changes based on prediction values ✗
- **Why it matters**: Violators underestimate standard errors (overconfident results)
- **Fix**: Use robust standard errors

**2. Multicollinearity (VIF)**
- **Passed**: Predictors are independent (VIF < 10) ✓
- **Failed**: Predictors are highly correlated (VIF > 10) ✗
- **Why it matters**: Inflated standard errors make estimates unreliable
- **Fix**: Remove correlated features or use regularization

**3. Stationarity (ADF Test)**
- **Passed**: Time series has constant mean and variance ✓
- **Failed**: Time series has trend or changing mean ✗
- **Why it matters**: Non-stationary data violates model assumptions
- **Fix**: Difference the series or use ARIMA

**4. Autocorrelation (Durbin-Watson)**
- **Passed**: Residuals are independent (DW ≈ 2.0) ✓
- **Failed**: Residuals are correlated (DW far from 2) ✗
- **Why it matters**: Correlated errors underestimate uncertainty
- **Fix**: Use robust standard errors or ARIMA

**5. Normality (Shapiro-Wilk)**
- **Passed**: Residuals are normally distributed ✓
- **Failed**: Residuals are skewed or have outliers ✗
- **Why it matters**: Non-normal errors affect p-values and confidence intervals
- **Fix**: Transform outcome or use nonparametric methods

---

## Interpreting Results

### Significance Levels

| p-value | Interpretation | What to Report |
|---------|---|---|
| < 0.001 | Highly significant | Effect is *** (triple star) |
| 0.001 - 0.01 | Very significant | Effect is ** (double star) |
| 0.01 - 0.05 | Significant | Effect is * (single star) |
| 0.05 - 0.10 | Borderline | Marginal evidence |
| > 0.10 | Not significant | No evidence (ns) |

### Effect Size vs. Significance

```
Large effect + High p-value = Unreliable (likely due to chance)
Small effect + Low p-value = Meaningful (effect is real but small)
Large effect + Low p-value = Strong evidence
Small effect + High p-value = No evidence
```

### Reading the 95% Confidence Interval

```
Effect: 0.40 (SE: 0.83)
95% CI: [-1.23, 2.03]

This means:
- Point estimate: 0.40
- Standard error: 0.83
- Range where true effect likely lies: -1.23 to 2.03
- Since 0 is in the range, effect could be zero (not significant)
```

---

## Output Files

### 1. Terminal Output

Contains all three steps:
- Pre-analysis diagnostics with test results
- Model results with statistics
- LLM interpretation answering your question

### 2. HTML Report

Located at: `outputs/espresso_report_[timestamp].html`

Contains:
- **Overview**: Your question and dataset summary
- **Diagnostics Section**: Color-coded test results ([OK] green, [FAIL] red)
- **Model Results**: Statistics, effect sizes, confidence intervals
- **LLM Interpretation**: Plain-English explanation of results
- **Visualizations**: 
  - Confidence interval plots
  - Effect size bar charts
  - Time series forecast comparisons
- **Summary Table**: Quick reference of all statistics

---

## Advanced Features

### Custom Model Selection

Espresso automatically selects appropriate models based on your question and data:

**Your Question Type** → **Selected Model** → **Assumptions Checked**
- "Does X cause Y?" → Difference-in-Differences → Parallel trends, common support
- "What is the forecast?" → ARIMA → Stationarity, autocorrelation
- "How does X affect Y over time?" → DiD → Panel structure, time patterns

### Automatic Variable Mapping

Tell Espresso what you're looking for, not the exact column names:

```bash
python run.py --data data/raw.csv --question "Does higher education reduce unemployment?"
```

Espresso uses LLM to find columns for:
- Outcome: "unemployment" (maps to matching column)
- Treatment: "education" (maps to matching column)
- Time: "year" (auto-detected)
- Units: "country" (auto-detected)

### Robust Error Handling

If diagnostics detect violations, Espresso:
1. **Reports the violation** (What went wrong)
2. **Explains why it matters** (Why is it a problem)
3. **Suggests corrections** (How to fix it)
4. **Still runs the model** (But with caveat in interpretation)

---

## Troubleshooting

### "Error mapping columns"

**Cause**: LLM couldn't understand your question
**Solution**: 
- Be more specific: "Does the treatment variable cause the outcome variable?"
- Use simpler language
- Match question to data column names

### "No valid models found"

**Cause**: Data structure doesn't match model requirements
**For DiD**: Need panel data (multiple units over time)
**For ARIMA**: Need time series (single unit over many time points)

### API Rate Limits

**Cause**: Too many requests to Gemini API in short time
**Solution**: Wait a few moments and try again

### Unicode Encoding Error

**Cause**: Terminal doesn't support special characters (✓, ✗)
**Solution**: Now uses ASCII-safe characters ([OK], [FAIL])

---

## Example: Complete Workflow

### Scenario
You have economic data and want to know: "Does government spending increase growth?"

### Step 1: Prepare Data

```csv
country,year,spending_billions,growth_percent
USA,2010,500,2.1
USA,2011,520,1.6
...
```

### Step 2: Run Analysis

```bash
python run.py --data data/economy.csv --question "Does government spending increase growth?"
```

### Step 3: Review Results

**Terminal Output:**
1. Diagnostics show: autocorrelation violation detected
2. Model shows: effect = 0.15, SE = 0.22, p = 0.51 (not significant)
3. Interpretation: "No evidence that spending affects growth in this data"

**HTML Report:**
- Visualizations showing spending vs. growth over time
- Diagnostic checks highlighted
- Full explanation why results are inconclusive

### Step 4: Decide Next Steps

Based on diagnostics:
- Try ARIMA instead of DiD (due to autocorrelation)
- Difference the data to remove trend
- Add additional control variables
- Collect more data

---

## Key Concepts

### Difference-in-Differences (DiD)

A causal inference method comparing treatment vs. control groups:

```
         Before Treatment    After Treatment
Control: 10 → 12            (change: +2)
Treat:   10 → 15            (change: +5)

Treatment Effect = 5 - 2 = 3 (difference of differences)
```

### ARIMA (AutoRegressive)

A forecasting method using past values to predict future:

```
AR(1) Model: Y(t) = constant + coefficient × Y(t-1) + error(t)

If coefficient = 0.8:
- If today = 100, tomorrow ≈ constant + 0.8×100
- High coefficient = strong momentum
- Coefficient = 0.95+ = potential instability
```

### Statistical Significance

Means results unlikely due to random chance (assuming p < 0.05):
- NOT same as "large effect" or "practical importance"
- Depends on sample size (larger samples easier to get significant)
- Always consider both p-value AND effect size

---

## File Reference

| File | Purpose | Key Functions |
|------|---------|---|
| `run.py` | Main orchestration | Executes 3-step pipeline |
| `diagnostics.py` | Pre-analysis checks | 5 statistical tests |
| `interpretation.py` | LLM layer | Generates plain-English explanations |
| `models.py` | Statistical models | DiD and ARIMA implementations |
| `data_utils.py` | Data loading | Handles CSV/panel data |
| `llm.py` | LLM integration | Gemini API interface |
| `selector.py` | Model selection | Chooses appropriate model |
| `html_report.py` | Report generation | Creates visualizations and HTML |

---

## Tips for Best Results

1. **Use panel data for DiD**
   - Multiple countries/regions over multiple years
   - Clear treatment and control groups
   - Balanced panel preferred

2. **Use long time series for ARIMA**
   - Minimum 20-30 observations
   - Regular time intervals
   - Single series recommended

3. **Ask clear questions**
   - "Does X cause Y?" (good for DiD)
   - "Forecast Y?" (good for ARIMA)
   - "How does X affect Y?" (good for DiD)

4. **Check diagnostics output**
   - Violations don't invalidate results but reduce confidence
   - Follow suggested corrections
   - Report violations in any final writeup

5. **Review LLM interpretation**
   - LLM provides context and plain-English summary
   - Always verify statistics yourself
   - Use interpretation as starting point, not final answer

---

## Version Info

- **Espresso Version**: 1.0 (Phase 4 Complete)
- **Released**: January 31, 2025
- **Python**: 3.14+
- **Key Dependencies**: 
  - pandas (data)
  - numpy/scipy (statistics)
  - google-genai (Gemini API)
  - matplotlib (plotting)

---

**Last Updated**: January 31, 2025
**Status**: Production Ready ✅
