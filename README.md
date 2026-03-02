# Espresso Prototype

Espresso makes rigorous statistical analysis accessible from the command line. Provide a CSV file and a plain-English research question — Espresso auto-detects the question type, maps variables, selects a model, and delivers results in seconds.

---

## 🚀 Quick Start

### Install dependencies
```bash
pip install pandas numpy scipy google-generativeai
```

### Set your LLM API key
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

### Run an analysis
```bash
# Time series forecast
python run_analysis.py --data "data/test_panel.csv" --question "What will unemployment be next year?"

# Causal effect
python run_analysis.py --data "data/test_causal.csv" --question "Does treatment improve outcomes?"

# Your own data
python run_analysis.py --data "your_file.csv" --question "Your research question?"
```

Results appear in the terminal immediately. An HTML report is saved to `outputs/`.

---

## 📂 Project Structure

```
espresso-prototype/
│
├── run_analysis.py       Main CLI entry point
├── data_utils.py         Data loading and pivoting utilities
├── llm.py                LLM integration (question parsing, column mapping)
├── selector.py           Model admissibility checks
├── diagnostics.py        Pre-analysis diagnostic tests
├── models.py             Statistical models (DiD, ARIMA)
├── interpretation.py     LLM-powered result interpretation
├── model_specs.py        Model definitions
├── html_report.py        HTML report generation
│
└── data/
    ├── test_panel.csv    12-row time series test dataset
    ├── test_causal.csv   20-row causal inference test dataset
    └── dataset_*.csv     IMF macroeconomic dataset
```

---

## 📋 Features

- **Automatic variable mapping** — no manual column selection
- **Question-type detection** — forecast vs. causal effect
- **Two statistical models**:
  - **Difference-in-Differences** for causal inference in panel data
  - **ARIMA (AR(1))** for time series forecasting
- **Pre-analysis diagnostics** — stationarity, treatment variation checks
- **LLM-powered interpretation** — plain-English explanation of results
- **HTML report** saved to `outputs/` after each run
- **Wide-format support** — auto-pivots indicator-style data to long format

---

## ⚠️ Known Limitations

- Large complex datasets with many indicators may have LLM mapping issues
- ARIMA assumes a single time series (aggregates multi-unit data)
- No interactive refinement if automatic mapping fails

---

## 🔧 Technical Specifications

| Item | Detail |
|------|--------|
| Language | Python 3.10+ |
| Core packages | pandas, numpy, scipy |
| LLM | Google Gemini 2.0 Flash Lite (`google-generativeai`) |
| Models | Difference-in-Differences (OLS), ARIMA AR(1) |
| Supported formats | Tidy (long) CSV, wide indicator-style CSV (auto-pivoted) |

---

**Last Updated**: March 2026
