"""
LLM-based interpretation layer.

Takes statistical results and asks Gemini to explain them in plain English,
answering the original research question directly.

Supported model types:
  - arima       : forecasting
  - diff_in_diff: causal DiD
  - panel_ols   : panel association (TWFE)
  - ols         : cross-sectional association
"""

from llm import query_gemini


FORECAST_MODELS = {'arima', 'linear_trend', 'exp_smoothing', 'random_walk'}
REGRESSION_MODELS = {
    'diff_in_diff',
    'panel_ols',
    'entity_fe',
    'time_fe',
    'first_difference',
    'ols',
    'pooled_ols',
    'log_linear',
    'log_log',
    'polynomial_ols',
    'median_quantile',
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpret_results(
    question,
    outcome_name,
    treatment_name,
    model_type,
    result_dict,
    diagnostics_dict=None,
    unit_name=None,
    unit_description=None,
):
    """
    Generate a plain-English interpretation of model results.

    Args:
        question        : original user question string
        outcome_name    : name of the dependent variable
        treatment_name  : name of the independent / treatment variable
        model_type      : 'arima', 'diff_in_diff', 'panel_ols', or 'ols'
        result_dict     : dict returned by the model runner
        diagnostics_dict: dict returned by the diagnostics runner (optional)
        unit_name       : resolved entity name (e.g. "Finland")
        unit_description: original user description if different (e.g. "happiest country")

    Returns:
        Interpretation string (markdown-lite bullet format)
    """
    try:
        if model_type in FORECAST_MODELS:
            return _interpret_arima(
                question, outcome_name, result_dict,
                diagnostics_dict, unit_name, unit_description
            )
        elif model_type in REGRESSION_MODELS:
            return _interpret_regression(
                question, outcome_name, treatment_name, model_type,
                result_dict, diagnostics_dict, unit_name, unit_description
            )
        else:
            return f"No interpretation available for model type '{model_type}'."
    except Exception as e:
        return f"Interpretation error: {e}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _unit_clause(unit_name, unit_description):
    """Build a consistent 'for X (identified as Y)' clause."""
    if unit_name and unit_description and unit_description.lower() != unit_name.lower():
        return f" for {unit_name} (identified as '{unit_description}')"
    elif unit_name:
        return f" for {unit_name}"
    return ""


def _diag_text(diagnostics_dict):
    """Summarise diagnostic violations for injection into a prompt."""
    if not diagnostics_dict:
        return ""
    violations = diagnostics_dict.get('violations', [])
    corrections = diagnostics_dict.get('corrections', [])
    if not violations:
        return "\nDIAGNOSTICS: All checks passed."
    v_str = ', '.join(violations)
    c_str = ', '.join(corrections) if corrections else 'None applied'
    return f"\nDIAGNOSTIC ISSUES: {v_str}\nCORRECTIONS APPLIED: {c_str}"


def _interpret_arima(question, outcome_name, result_dict, diagnostics_dict, unit_name, unit_description):
    forecasts = result_dict.get('forecasts', [])
    forecast_times = result_dict.get('forecast_times', [])
    last_value = result_dict.get('last_value', 0) or 0
    rmse = result_dict.get('rmse', 0) or 0
    ar1_coef = result_dict.get('ar1_coef', 0) or 0
    arima_order = result_dict.get('arima_order', (1, 0, 0))
    engine = result_dict.get('engine', 'unknown')
    model_label = result_dict.get('model', f'ARIMA{arima_order}')

    n_periods = len(forecasts)
    forecast_next = forecasts[0] if forecasts else 0
    avg_forecast = sum(forecasts) / n_periods if forecasts else forecast_next
    change = forecast_next - last_value
    pct_change = (change / last_value * 100) if last_value else 0

    ci_lower = result_dict.get('ci_lower', [])
    ci_upper = result_dict.get('ci_upper', [])
    ci_str = (
        f"[{ci_lower[0]:.2f}, {ci_upper[0]:.2f}]"
        if ci_lower and ci_upper else "not available"
    )

    unit_clause = _unit_clause(unit_name, unit_description)
    diag = _diag_text(diagnostics_dict)

    prompt = f"""Answer the forecasting question directly using the analysis results.

QUESTION: "{question}"

MODEL: {model_label} (engine: {engine})

FORECAST RESULTS{unit_clause}:
- Variable: {outcome_name}
- Last observed value: {last_value:,.4f}
- Next-period forecast: {forecast_next:,.4f}  (95% CI: {ci_str})
- {n_periods}-period average forecast: {avg_forecast:,.4f}
- Expected change: {change:+,.4f} ({pct_change:+.2f}%)
- Model fit (RMSE): {rmse:,.4f}
- Persistence diagnostic: {ar1_coef:.3f}
- Forecast stability: {"Stable" if abs(ar1_coef) < 0.9 else "High persistence - long-run projections are sensitive to shocks"}{diag}

WRITE YOUR INTERPRETATION:

1. DIRECT ANSWER (1-2 sentences):
What will happen to {outcome_name}{unit_clause}? Give the direction and rough magnitude.{' Clarify you identified the query as ' + unit_name + '.' if unit_description and unit_name and unit_description.lower() != unit_name.lower() else ''}

2. THE FORECAST (2-3 sentences):
From {last_value:,.2f} to {forecast_next:,.2f} next period, and an average of {avg_forecast:,.2f} over {n_periods} periods.
Is this change economically meaningful? What trend does the model capture?

3. MODEL QUALITY & UNCERTAINTY (1-2 sentences):
Comment on the RMSE and confidence interval. Is the forecast reliable?

4. KEY TAKEAWAY (1 sentence):
Bottom line for {outcome_name}{unit_clause}.

FORMATTING:
- No introductory phrases ("Here is…", "Based on…")
- Use plain bullet points (hyphens)
- Write like explaining to a smart colleague
"""
    interp = query_gemini(prompt)
    return interp if interp else _fallback_arima_interpretation(
        outcome_name, result_dict, unit_clause
    )


def _interpret_regression(
    question, outcome_name, treatment_name, model_type,
    result_dict, diagnostics_dict, unit_name, unit_description
):
    effect = result_dict.get('treatment_effect', result_dict.get('slope', 0)) or 0
    se = result_dict.get('se', 0) or 0
    pval = result_dict.get('pvalue', 1) or 1
    r_sq = result_dict.get('r_squared', 0) or 0
    n_obs = result_dict.get('n_obs', 'unknown')
    ci_lower = result_dict.get('ci_lower', effect - 1.96 * se)
    ci_upper = result_dict.get('ci_upper', effect + 1.96 * se)
    se_type = result_dict.get('se_type', 'OLS')
    fe_type = result_dict.get('fe_type', '')

    significance = (
        "*** (p<0.001)" if pval < 0.001 else
        "** (p<0.01)"   if pval < 0.01  else
        "* (p<0.05)"    if pval < 0.05  else
        "not significant (p>=0.05)"
    )

    model_labels = {
        'diff_in_diff': 'Difference-in-Differences (TWFE)',
        'panel_ols':    'Panel OLS (Two-Way FE)',
        'entity_fe':    'Entity Fixed Effects',
        'time_fe':      'Time Fixed Effects',
        'first_difference': 'First-Difference Regression',
        'ols':          'Cross-Sectional OLS',
        'pooled_ols':   'Pooled OLS',
        'log_linear':   'Log-Linear Regression',
        'log_log':      'Log-Log Regression',
        'polynomial_ols': 'Quadratic OLS',
        'median_quantile': 'Median Quantile Regression',
    }
    model_label = model_labels.get(model_type, model_type)

    causal = model_type == 'diff_in_diff'
    effect_label = "causal treatment effect" if causal else "regression coefficient"

    unit_clause = _unit_clause(unit_name, unit_description)
    diag = _diag_text(diagnostics_dict)

    prompt = f"""Answer the research question directly using the statistical results.

QUESTION: "{question}"

MODEL: {model_label}
{f'Fixed effects: {fe_type}' if fe_type else ''}
Standard errors: {se_type}

RESULTS{unit_clause}:
- Outcome: {outcome_name}
- Predictor: {treatment_name}
- {effect_label.capitalize()}: {effect:,.4f}
- SE: {se:,.4f}
- P-value: {pval:.4f}  ({significance})
- 95% CI: [{ci_lower:,.4f}, {ci_upper:,.4f}]
- R-squared: {r_sq:.4f}  ({r_sq*100:.1f}% of variation explained)
- N observations: {n_obs:,}{diag}

WRITE YOUR INTERPRETATION:

1. DIRECT ANSWER (1-2 sentences):
{'Does ' + treatment_name + ' causally affect ' + outcome_name + '?' if causal else 'What is the relationship between ' + treatment_name + ' and ' + outcome_name + '?'}{unit_clause}
Give the sign, magnitude, and significance in plain English.

2. WHAT THE NUMBERS MEAN (2-3 sentences):
Explain the effect size practically. Is {effect:.2f} large or small in context?
{'Mention that unit and time fixed effects were absorbed, so this reflects within-unit variation.' if fe_type else ''}
{'Note any diagnostic corrections that were applied.' if diag else ''}

3. STATISTICAL CONFIDENCE (1-2 sentences):
How confident should we be? Translate the p-value and CI into everyday language.

4. KEY TAKEAWAY (1 sentence):
Bottom line on the {('causal' if causal else 'statistical')} link between {treatment_name} and {outcome_name}.

FORMATTING:
- No introductory phrases
- Plain hyphens for bullets
- Conversational but precise
"""
    interp = query_gemini(prompt)
    return interp if interp else _fallback_regression_interpretation(
        outcome_name, treatment_name, model_label, effect, pval,
        ci_lower, ci_upper, r_sq, n_obs, causal, unit_clause
    )


def _fallback_arima_interpretation(outcome_name, result_dict, unit_clause):
    """Deterministic interpretation when the LLM is unavailable."""
    forecasts = result_dict.get('forecasts', [])
    last_value = result_dict.get('last_value', 0) or 0
    next_value = forecasts[0] if forecasts else result_dict.get('forecast_next_period', 0)
    change = next_value - last_value
    direction = "increase" if change > 0 else "decrease" if change < 0 else "stay roughly flat"
    rmse = result_dict.get('rmse', 0) or 0
    pct = (change / last_value * 100) if last_value else 0
    avg = sum(forecasts) / len(forecasts) if forecasts else next_value
    return (
        f"- Direction: {outcome_name}{unit_clause} is expected to {direction} from {last_value:,.4f} "
        f"to {next_value:,.4f} next period ({pct:+.2f}%).\n"
        f"- Horizon: average forecast over {len(forecasts)} periods is {avg:,.4f}.\n"
        f"- Uncertainty: model RMSE is {rmse:,.4f}; treat the point forecast as a central estimate, "
        f"not a guarantee, especially further out."
    )


def _fallback_regression_interpretation(
    outcome_name, treatment_name, model_label, effect, pval,
    ci_lower, ci_upper, r_sq, n_obs, causal, unit_clause
):
    """Deterministic regression interpretation when the LLM is unavailable."""
    direction = "positive" if effect > 0 else "negative" if effect < 0 else "near-zero"
    sig = "statistically significant" if pval < 0.05 else "not statistically significant"
    relationship = "causal effect" if causal else "statistical relationship"
    crosses_zero = (ci_lower or 0) <= 0 <= (ci_upper or 0)
    confidence_phrase = (
        "the 95% confidence interval excludes zero, so the sign is well-determined"
        if not crosses_zero else
        "the 95% confidence interval crosses zero, so we can't rule out 'no effect'"
    )
    return (
        f"- Estimate: {model_label} finds a {direction} {relationship} of {treatment_name} on "
        f"{outcome_name}{unit_clause}, magnitude {effect:,.4f}.\n"
        f"- Significance: {sig} at the 5% level (p={pval:.4f}); {confidence_phrase} "
        f"(95% CI [{ci_lower:,.4f}, {ci_upper:,.4f}]).\n"
        f"- Fit: R² = {r_sq:.4f} on {n_obs} observations."
    )


# ---------------------------------------------------------------------------
# Diagnostic summary formatter (used in CLI output)
# ---------------------------------------------------------------------------

def interpret_diagnostics(diagnostics_result):
    """Format a diagnostics dict as a human-readable string for CLI display."""
    if 'error' in diagnostics_result:
        return f"Diagnostic Error: {diagnostics_result['error']}"

    lines = [
        f"PRE-ANALYSIS DIAGNOSTICS ({diagnostics_result.get('model', 'Unknown')})",
        "=" * 60,
    ]

    for check in diagnostics_result.get('checks', []):
        if 'error' in check:
            lines.append(f"   [WARN] {check.get('test', 'Test')}: {check['error']}")
        else:
            status = "[OK]  " if not check.get('is_violated') else "[FAIL]"
            lines.append(f"   {status} {check.get('interpretation', 'N/A')}")

    violations = diagnostics_result.get('violations', [])
    corrections = diagnostics_result.get('corrections', [])

    if violations:
        lines.append("\nVIOLATIONS DETECTED:")
        for v in violations:
            lines.append(f"   - {v}")
        lines.append("\nCORRECTIONS APPLIED:")
        for c in corrections:
            lines.append(f"   - {c}")
    else:
        lines.append("\n[OK] All diagnostic checks passed.")

    return "\n".join(lines)
