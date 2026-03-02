# Espresso Terminal Visualizations

## Overview
The Espresso statistical inference prototype now features fancy ASCII visualizations and formatted output directly in the terminal. No need for external plotting libraries or complex GUI - all results are displayed with professional ASCII charts and tables.

## Features Added

### 1. Difference-in-Differences (DiD) Model Results
**Visualization Elements:**
- **Effect Distribution Bar**: Shows where the point estimate falls within the confidence interval
- **Confidence Interval Display**: Visual indication of whether CI includes zero
- **Formatted Statistics Table**: Clean table layout with all model parameters
- **Significance Indicators**: Stars (***,**,*) and "ns" labels for quick interpretation

**Example Output:**
```
   +==== DIFFERENCE-IN-DIFFERENCES RESULTS ====+
   |
   |  TREATMENT EFFECT ESTIMATE
   |  Point estimate:            0.397619  ns
   |  Std. error:                0.830702
   |  95% CI:  [  -1.230558,    2.025796]
   |
   |  EFFECT DISTRIBUTION:
   | ----------------------|----------------------
   | 95% CI includes zero (not significant at 5%)
   |
   |  TEST STATISTICS
   |  t-statistic:                 0.4787
   |  p-value:                   0.638660
   |  R-squared:                   0.1167
   |  N observations:                  20
   |
   +==========================================+
```

### 2. ARIMA/Time Series Forecast Results
**Visualization Elements:**
- **Model Parameters**: Clear display of AR(1) coefficient and intercept
- **Process Stability**: Indicates if process is mean-reverting or explosive
- **Trajectory Bars**: ASCII bar chart showing last value vs. forecast
- **Fit Quality Indicator**: EXCELLENT/GOOD/FAIR/POOR with visual badges
- **Change Metrics**: Shows expected change and percent change

**Example Output:**
```
   +==== ARIMA (AR(1)) TIME SERIES FORECAST ====+
   |
   |  MODEL PARAMETERS
   |  AR(1) coefficient:        -0.153846
   |  Intercept:                 5.364957
   |  Process type:          Mean-reverting (STABLE)
   |
   |  FORECAST RESULTS
   |  Last observed value:       3.600000
   |  Forecast for t+1:          4.652137
   |  Expected change:           1.052137
   |  Percent change:              29.23%
   |
   |  TRAJECTORY
   |  Last value:     [###################           ] 3.6000
   |  Forecast (t+1): [#########################     ] 4.6521
   |
   +===========================================+
```

### 3. Model Comparison Summary
**Visualization Elements:**
- **Effect Bars**: ASCII + or - bar showing effect size
- **Significance Status**: Clear indication of statistical significance
- **Quality Ratings**: Visual fit quality indicators [EEEE]/[EEE-]/[EE--]/[E---]
- **Forecast Metrics**: Next period forecast with RMSE display

**Example Output:**
```
======================================================================
MODEL COMPARISON SUMMARY
======================================================================

   Model 1: Difference-in-Differences
   ----------------------------------------------------------------
   |  Treatment Effect: [+++++++             ]     0.3976
   |  Status:           NOT SIGNIFICANT (ns)                     (p=0.6387)

   Model 2: ARIMA (AR(1))
   ----------------------------------------------------------------
   |  Next Period Forecast:     4.6521
   |  Model Error (RMSE):       0.7789
   |  Fit Quality:         GOOD     [EEE-]
```

### 4. LLM Variable Mapping Display
**Visualization Elements:**
- **Auto-applied mapping**: Shows what the LLM detected without user confirmation
- **Formatted table**: Clear display of mapped columns
- **Notes section**: LLM explanation of its decision

**Example Output:**
```
   LLM Variable Mapping (Auto-Applied):
   ------------------------------------------------------------------
   |  Outcome:       {'type': 'column', 'value': 'gdp_growth'}      |
   |  Treatment:     {'type': 'column', 'value': 'treatment'}       |
   |  Time:          {'type': 'column', 'value': 'year'}            |
   |  Unit:          {'type': 'column', 'value': 'country'}         |
   ------------------------------------------------------------------
```

## Helper Functions

### `draw_distribution_bar(value, min_val, max_val, width=40)`
Creates an ASCII bar showing the position of a point estimate within a range (useful for confidence intervals).

### `draw_histogram(values, bins=10, width=40, height=5)`
Generates an ASCII histogram for visualizing distributions of values.

## Terminal Output Quality Features

1. **Box Drawing**: Professional box characters (╔╚╝═║┌┐└┘├┤┬┴┼) for structured output
2. **ASCII Bars**: Simple + and # characters for cross-platform compatibility (Windows-safe)
3. **Color-coded Status**: ✓, ✗ replaced with [OK], [ERROR] for Windows compatibility
4. **Proper Spacing**: Consistent indentation and alignment for readability
5. **Statistical Notation**: Significance codes (***,**,*,ns) for quick interpretation

## User Experience Improvements

1. **No User Interaction Required**: Automatic LLM mapping eliminates yes/no prompts
2. **Rich Visual Feedback**: Professional-looking output without leaving the terminal
3. **Compact Display**: All information fits in a standard terminal window
4. **Real-time Results**: Instant feedback as models are computed
5. **Clear Interpretation**: Plain English explanations alongside statistical results

## Usage Examples

### Forecast Analysis
```bash
python run.py --data "data/test_panel.csv" --question "What will unemployment be next year?"
```

### Causal Analysis
```bash
python run.py --data "data/test_causal.csv" --question "Does policy treatment affect GDP growth?"
```

### Large Datasets
```bash
python run.py --data "data/imf_dataset.csv" --question "Does government spending affect GDP growth?"
```

## Statistics Displayed

### For Difference-in-Differences
- Point estimate (treatment effect)
- Standard error
- 95% Confidence interval
- t-statistic
- p-value
- R-squared
- Sample size

### For ARIMA/Time Series
- AR(1) coefficient
- Intercept
- Forecast for next period
- AIC (model fit metric)
- RMSE (prediction error)
- Process stability assessment
