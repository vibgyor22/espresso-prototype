# Espresso

**AI econometrics for causal reasoning, forecasting, and empirical discovery.**

Espresso turns a plain-English research question and a CSV file into a structured econometric workflow. It reads the question, maps the data, selects an admissible model, runs diagnostics, estimates results, and produces a clear HTML report.

The goal is simple: make rigorous empirical analysis feel as direct as asking the question.

## Why Espresso Exists

Most statistical tools expect the user to already know the model, the formula, the data shape, the assumptions, and the diagnostic checks. Espresso reverses that workflow.

You ask:

> Does treatment improve GDP growth?

Espresso responds with a research pipeline:

- identifies the question as causal, forecasting, or associational
- maps natural-language concepts to columns in the dataset
- checks whether the data can support the requested model
- runs econometric diagnostics before estimation
- estimates the model with robust or clustered uncertainty where appropriate
- explains the result in language a human decision-maker can use
- saves a polished report for sharing, review, and iteration

Espresso is built for students, analysts, researchers, founders, policy teams, and anyone who wants to move from raw data to statistical reasoning without wrestling with boilerplate.

## What Espresso Can Do

Espresso supports a growing model library across three major analysis modes.

### Causal Reasoning

For questions about effects, impact, treatment, policy, or intervention:

- Difference-in-Differences with two-way fixed effects
- unit and time fixed effects support
- treatment variation checks
- parallel-trends diagnostics
- clustered standard errors for panel settings

### Forecasting

For questions about what happens next:

- auto-order ARIMA
- linear trend forecasts
- exponential smoothing
- random-walk baseline forecasts
- forecast intervals and fit diagnostics

### Association And Econometric Discovery

For questions about relationships, elasticities, and patterns:

- OLS with HC1 robust standard errors
- pooled OLS
- panel OLS with two-way fixed effects
- entity fixed effects
- time fixed effects
- first-difference regression
- log-linear regression
- log-log elasticity models
- quadratic OLS
- median quantile regression

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file with your Gemini API key:

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

Run your first analysis:

```bash
python run_analysis.py --data data/test_causal.csv --question "Does treatment affect GDP growth?"
```

Espresso prints the result in the terminal and writes a shareable HTML report to `outputs/`.

## Example Workflows

### Estimate A Causal Effect

```bash
python run_analysis.py \
  --data data/test_causal.csv \
  --question "Does treatment affect GDP growth?"
```

Espresso detects a causal-effect question and uses Difference-in-Differences when the panel structure and treatment variation support it.

### Forecast A Time Series

```bash
python run_analysis.py \
  --data data/test_panel.csv \
  --question "Forecast unemployment for the next 3 years" \
  --forecast-periods 3
```

Espresso estimates a forecasting model, prints the forecast table, and includes uncertainty bands in the report.

### Explore A Relationship

```bash
python run_analysis.py \
  --data data/test_panel.csv \
  --question "What is the relationship between interest rate and unemployment?" \
  --model panel_ols
```

Espresso can automatically choose a model, or you can select one explicitly with `--model`.

## Supported Models

Use this command to see the live model registry:

```bash
python run_analysis.py --list-models
```

| Model | Use case |
|---|---|
| `diff_in_diff` | causal effects in panel data |
| `arima` | time-series forecasting |
| `linear_trend` | transparent trend forecasting |
| `exp_smoothing` | short or noisy time-series forecasting |
| `random_walk` | persistent-series forecast baseline |
| `panel_ols` | association with unit and time fixed effects |
| `entity_fe` | within-unit association |
| `time_fe` | association after common time shocks |
| `first_difference` | association in within-unit changes |
| `ols` | cross-sectional regression |
| `pooled_ols` | pooled regression over all observations |
| `log_linear` | semi-elasticity estimation |
| `log_log` | elasticity estimation |
| `polynomial_ols` | nonlinear quadratic relationships |
| `median_quantile` | median relationship robust to outliers |

## Data Shapes

Espresso works with standard tidy data:

```csv
country,year,treatment,gdp_growth
USA,2018,0,2.0
USA,2019,0,2.3
USA,2020,1,1.5
```

It can also reshape wide indicator-style datasets with year columns:

```csv
country,series_name,2000,2001,2002
India,Unemployment,7.3,7.1,7.0
India,GDP growth,3.8,4.8,3.9
```

## Reports

Every successful run creates a self-contained HTML report with:

- the original research question
- selected model and model metadata
- diagnostics and warnings
- estimates, uncertainty, and significance
- forecast charts or coefficient visualizations
- plain-English interpretation

Reports are saved in `outputs/`.

## Testing

Run the test suite with:

```bash
python -m pytest tests/ -v
```

The tests cover data utilities, model selection, diagnostics, forecasting, causal estimation, and the expanded econometric model library.

## Philosophy

Espresso is not trying to hide statistics. It is trying to make statistical reasoning easier to begin, easier to audit, and easier to communicate.

The future of applied econometrics should feel less like memorizing syntax and more like asking better questions.

Espresso is a step toward that future.

## Current Boundaries

- Espresso is best for first-pass analysis and model exploration.
- Causal estimates still require a credible research design.
- LLM-based column mapping can make mistakes on ambiguous datasets.
- Forecasts are currently univariate after optional panel aggregation.
- Regression support is currently focused on single-predictor workflows.
