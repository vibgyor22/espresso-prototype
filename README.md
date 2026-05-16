# Espresso

> Agentic econometric analyst for the terminal. Think *Claude Code, but for econometrics*.

You bring a question and a data file. Espresso decides which columns to use, which model is appropriate, which pre-analysis diagnostics matter, and what to do when something fails — narrating every choice in plain English you can actually follow. No statistical background required.

```bash
pip install espresso-protocol
espresso analyze gdp.csv --question "Did the 2020 stimulus boost employment?"
```

## What it does

- **Reads your data** — CSV, TSV, Excel (multi-sheet), Parquet. Profiles every column (type, range, missingness, candidate role).
- **Understands your question** — figures out whether you're asking about a causal effect, a correlation, or a forecast.
- **Picks the right columns** — matches the words in your question to actual columns, and asks you only if it's genuinely unsure.
- **Picks the right model** — 15+ econometric methods. Diff-in-differences, panel OLS with TWFE, ARIMA, log-log, quantile regression, more.
- **Runs pre-analysis diagnostics** — stationarity, parallel trends, heteroscedasticity, autocorrelation, normality. Switches to a corrective model when assumptions fail, and tells you why.
- **Interprets in plain English** — four layers: *why these columns*, *why this model*, *the numbers*, and the qualitative reading: domain context, past trends in your data, recent events that may have shaped it, what empirical literature usually finds, and a sanity check on sign and magnitude.
- **Suggests follow-ups** — robustness checks, subset analyses, what-if scenarios — pick by number.
- **Stays in the terminal by default** — rich tables, ascii forecast charts, coefficient bars. Type `export` to get a self-contained HTML dashboard with what-if sliders.

The statistics are deterministic. The agent layer decides what to run; the math itself never goes through an LLM.

## Quickstart

```bash
# One-shot
espresso analyze data.csv -q "What's the effect of minimum wage on employment?"

# With an HTML dashboard
espresso analyze data.csv -q "Forecast unemployment for 10 years" --export report.html

# Interactive REPL
espresso
[espresso] » load data/test_panel.csv
[espresso] » did the policy work?
[espresso] » what if treatment = 12
[espresso] » ?p-value
[espresso] » export
```

## Why not ChatGPT?

ChatGPT will tell you *about* difference-in-differences. Espresso *runs* difference-in-differences on your data, *checks the assumptions*, *switches to a more robust estimator* if pre-trends fail, *tells you whether the magnitude is plausible* given what the literature finds, *flags omitted-variable bias when the sign looks weird*, and produces numbers you can trust because the math is deterministic Python, not an LLM hallucinating a p-value.

If you want a senior statistician sitting next to you who happens to know your dataset and a thousand papers — that's the goal.

## REPL commands

| Command | What it does |
|---|---|
| `load <path>` | Load a CSV / TSV / XLSX / Parquet file |
| `ask <question>` | Run an analysis (also: just type a question) |
| `what if <var> = <n>` | Predict outcome at a scenario value |
| `what if shock = <n>` | Forecast: shift the most recent value |
| `?<term>` | Define a term (e.g. `?p-value`, `?fixed effects`) |
| `show profile` / `show interpretation` | Re-print sections |
| `export [path.html]` | Save a self-contained dashboard |
| `<number>` | Pick a suggested follow-up |

## Expert overrides

Most of the time you don't need these. When you do:

```bash
espresso analyze data.csv -q "..." \
  --outcome gdp_per_capita --treatment policy \
  --unit country --time year \
  --model diff_in_diff --level expert --no-clarify
```

## Setup

```bash
git clone https://github.com/vibgyor22/espresso-protocol
cd espresso-protocol
pip install -e .
echo "GEMINI_API_KEY=your_key" > .env
```

Espresso uses Gemini for question parsing, column mapping, and qualitative interpretation. If the LLM is offline or out of quota, the deterministic fallbacks still produce a complete analysis — just with less qualitative narration.

## Supported models

**Causal:** difference-in-differences (TWFE).
**Forecasting:** ARIMA (auto-order), linear trend, exponential smoothing, random walk.
**Association:** panel OLS (TWFE), entity FE, time FE, first-difference, OLS, pooled OLS, log-linear, log-log, polynomial OLS, median quantile regression.

All regression models use robust or clustered standard errors as appropriate.

## Documentation

- [Usage and commands](docs/USAGE.md)
- [Worked examples](docs/EXAMPLES.md)

## License

MIT.

## Status

Beta. The CLI surface is stable; the Python API may move.
