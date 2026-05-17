<div align="center">

# Espresso Protocol

**Your data. A question. Real econometrics — in your terminal.**

[**espressoprotocol.in**](https://espressoprotocol.in) · [Install](#install) · [Quick start](#quick-start) · [What it does](#what-it-does)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brown.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-gold.svg)](LICENSE)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)]()

</div>

---

## The idea

Most data tools make you do the statistics. Espresso does the statistics *for* you.

You load a spreadsheet, ask a question in plain English, and Espresso figures out the rest: which columns matter, which econometric model is appropriate, whether the model's assumptions hold, and what the numbers actually mean for your question. It narrates every decision in plain English so you can follow along — or override anything.

It is not a chatbot. The numbers are computed by deterministic Python — the same estimators academics use. The AI layer handles the judgment calls: reading your question, matching it to your data, choosing between models, and translating coefficients into human language.

Think of it as a senior statistician who happens to know your dataset.

---

## Install

```bash
pip install git+https://github.com/vibgyor22/Espresso-Protocol.git
```

Then add your API key (free tier is enough):

```bash
# Create a .env file in your working directory:
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Or use Gemini instead:
echo "GEMINI_API_KEY=your-key-here" > .env
```

Get a free key at [console.anthropic.com](https://console.anthropic.com) (Claude) or [aistudio.google.com](https://aistudio.google.com) (Gemini).

---

## Quick start

```bash
espresso
```

That opens the interactive terminal. Then just talk to it:

```
◈  load my_data.csv
◈  did the policy change in 2018 affect unemployment?
◈  what if unemployment were 2% lower?
◈  export
```

No quotes. No flags. No commands to memorise.

---

## What it does

**Reads any data format** — CSV, TSV, Excel (multi-sheet), Parquet. Automatically profiles every column: type, range, missing values, which role it likely plays.

**Understands your question** — distinguishes between causal questions ("did X cause Y?"), association questions ("is X related to Y?"), and forecasts ("what will X be next year?").

**Picks the right model automatically** — 15+ econometric methods. Difference-in-differences, panel OLS with two-way fixed effects, ARIMA, entity fixed effects, log-log regression, quantile regression, and more. If the first model's assumptions fail, it switches to a corrective one and tells you why.

**Runs diagnostics before trusting the numbers** — heteroscedasticity, autocorrelation, non-normality, parallel trends. Applies robust or clustered standard errors as appropriate.

**Interprets in plain English** — four layers of context: why these columns, why this model, what the numbers mean, and the qualitative read: domain knowledge, trends in your actual data, what empirical literature usually finds, a sanity check on sign and magnitude.

**Suggests follow-ups** — robustness checks, subset analyses, what-if scenarios. Pick by number.

**Stays in the terminal by default** — rich formatted tables, coefficient bars, ASCII charts. Type `export` to get a self-contained interactive HTML dashboard with sliders.

The statistics are deterministic. The math never goes through an LLM.

---

## Two ways to use it

### Interactive REPL (recommended)

```bash
espresso
```

```
◈  load gdp_data.csv
◈  how does trade openness affect GDP growth?
◈  is that a big effect compared to what the literature finds?
◈  what if trade openness were 10 percentage points higher?
◈  export
```

After each analysis you can keep chatting. Ask follow-up questions about the result, run what-if scenarios, request robustness checks — no need to re-run anything.

### One-shot command

```bash
espresso analyze data.csv -q "What drove unemployment in the 2008 recession?"
```

```bash
# With HTML export
espresso analyze data.csv -q "Forecast inflation for the next 5 years" --export report.html

# With explicit column overrides
espresso analyze data.csv -q "..." \
  --outcome gdp_growth --treatment interest_rate \
  --model diff_in_diff --unit country --time year
```

---

## REPL reference

| What you type | What happens |
|---|---|
| `load path/to/file.csv` | Load a dataset (CSV, Excel, Parquet) |
| Any question | Run a full econometric analysis |
| A number (e.g. `2`) | Run the suggested follow-up |
| `what if <var> = <value>` | Predict outcome at a scenario value |
| `what if shock = <n>` | Shift a forecast baseline |
| `export` | Save a self-contained HTML dashboard |
| `export table` | Export a LaTeX + Markdown regression table |
| `eras` | Break down results by historical era |
| `context` | Show relevant world events for this analysis |
| `robustness` | Run alternative model specifications |
| `verdict` | Re-print the plain-English conclusion |
| `?p-value`, `?fixed effects` | Define any statistical term |
| `show profile` | Re-print the data profile |
| `explain` | Toggle step-by-step annotation mode |

---

## Supported models

| Type | Models |
|---|---|
| **Causal** | Difference-in-differences (TWFE) |
| **Forecast** | ARIMA (auto-order), linear trend, exponential smoothing, random walk |
| **Association** | Panel OLS (TWFE), entity FE, time FE, first-difference, OLS, pooled OLS, log-linear, log-log, polynomial OLS, median/quantile regression |

All regression models apply robust (HC1) or clustered standard errors automatically.

---

## Data formats

Espresso reads:

- **CSV / TSV** — any delimiter, auto-detected
- **Excel** — `.xlsx`, multi-sheet (you pick the sheet in the REPL)
- **Parquet** — full support
- **Panel data** — unit × time structure auto-detected
- **Cross-sectional** — single-period data
- **Time series** — single-entity with a time column

---

## What you need

- Python 3.10 or later
- An API key from Anthropic or Google (free tier works fine)
- A data file with at least two numeric columns

Espresso runs fully offline if no API key is set — you get deterministic statistics but no qualitative interpretation.

---

## Why not just use Python / R / Excel?

Python and R are powerful but require you to already know which model to use, how to run diagnostics, what the assumptions are, how to interpret the output, and what to do when something fails. Excel can't run any of this.

Espresso handles all of that. The model selection, the diagnostics, the interpretation, the fallback logic — it is the analysis layer, not just the calculation layer. You focus on the question; Espresso handles the methodology.

It is not a replacement for statisticians. It is what you reach for before you need one.

---

## Project

**Website:** [espressoprotocol.in](https://espressoprotocol.in)
**Status:** Beta — CLI is stable, Python API may change
**License:** MIT

Contributions welcome. Open an issue or PR.
