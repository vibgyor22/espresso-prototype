### Espresso Demo Scripts (O’Shaughnessy Pitch)

These flows assume the Flask server is running:

```bash
python api_server.py
```

Then open `http://localhost:8000` in the browser.

---

### Demo 1 — Policy Evaluation (Difference-in-Differences)

- **Dataset**: `Policy Evaluation (DiD) Toy Dataset` (`policy_example`)
- **Narrative**: “We’ll test whether an intervention changed outcomes using a proper diff-in-diff model with diagnostics and a full audit trail.”

**Steps**

- In the left panel, select **Policy Evaluation (DiD) Toy Dataset**.
- Point out the **Data Summary** pill: rows, columns, inferred `time` and `unit`.
- Ask in the console:
  - `Does treatment reduce the outcome?`
- Explain what happens:
  - Espresso parses the question into a **causal effect** intent (outcome/treatment/time/unit).
  - Maps intent to concrete columns, checks DiD admissibility, and runs:
    - Pre-analysis diagnostics (heteroskedasticity, autocorrelation, multicollinearity),
    - A DiD regression with an interaction term.
- Click **“Open full console view”**:
  - Show:
    - Effect size + 95% CI bar chart,
    - P-value & R²,
    - Diagnostics tags (OK / violations) and any suggested corrections,
    - LLM explanation that references the **actual coefficient and CI**, not invented numbers.
- Emphasize:
  - All numbers are computed by the model, and the interpretation is a thin language layer over that.
  - The run is added to the **history** and to the on-disk audit log (`outputs/inference_history.jsonl`).

---

### Demo 2 — Macro Forecast (AR(1) Time-Series)

- **Dataset**: `Panel Time Series Toy Dataset` (`panel_forecast_example`)
- **Narrative**: “We’ll forecast a macro-style indicator and watch the forecast cone respond to changes in the question.”

**Steps**

- Select **Panel Time Series Toy Dataset**.
- Ask:
  - `What will the outcome be over the next 8 years?`
- Explain:
  - Espresso interprets this as a **forecast** question and extracts `forecast_periods = 8`.
  - It aggregates to a single series (if panel), runs AR(1), and returns:
    - Last observed value,
    - 8-step dynamic forecast path,
    - AR(1) coefficient, RMSE, and diagnostics for stationarity and residual structure.
- Open the **full console view**:
  - Show the **historical vs. forecast chart** (solid vs. dashed line),
  - Highlight AR(1) coefficient, RMSE, and number of observations,
  - Read 1–2 lines from the interpretation block.
- Variation:
  - Ask again with a different horizon:
    - `What will the outcome be over the next 20 years?`
  - Show that the forecast chart and statistics update, and another run appears in history with its own spec summary.

---

### Demo 3 — “LLMs Can’t Do This” Contrast

- **Dataset**: `IMF Macroeconomic Dataset (Sample)` (`imf_macro_example`)
- **Narrative**: “We’ll pose a rich macro question where a vanilla LLM would hallucinate coefficients. Espresso instead runs diagnostics and real estimation.”

**Steps**

- Select **IMF Macroeconomic Dataset (Sample)**.
- Ask:
  - `What is the effect of higher interest rates on unemployment over time?`
- Explain:
  - Espresso:
    - Detects panel/time structure,
    - Interprets outcome and treatment using the IMF indicators,
    - Chooses an appropriate model (e.g., AR(1) forecast or simple DiD-style setup depending on mapping),
    - Runs diagnostics and returns computed coefficients.
- Open the **console view**:
  - Show the **spec summary** (“Difference-in-differences regression on panel data…” or “AR(1) time-series forecast…”),
  - Show diagnostics tags and interpretation.
- Explicitly contrast with a generic LLM:
  - “If we asked a chat model this question, it would talk *about* economics, but every number on this screen is coming from actual computation on the dataset, with a recorded run ID and machine-readable spec.”

---

### Notes for the Pitch

- Highlight the **separation of layers**:
  - LLM → parses question, maps columns, and explains results.
  - Stats engine → chooses admissible models and runs actual estimation + diagnostics.
- Emphasize:
  - **Audit trail**: every run logged in `outputs/inference_history.jsonl` with dataset, question, model, spec summary, and report path.
  - **Exportable reports**: each run emits a rich HTML report in `outputs/espresso_report_*.html` for later inspection or sharing.

