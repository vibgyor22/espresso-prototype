"""
LLM-based interpretation layer.
Takes statistical results and feeds them back to LLM for interpretation.
"""

from llm import query_gemini


def interpret_results(question, outcome_name, treatment_name, model_type, result_dict, diagnostics_dict=None, unit_name=None, unit_description=None):
    """
    Use LLM to interpret statistical results and answer the original question.
    
    Args:
        question: Original user question
        outcome_name: Name of outcome variable
        treatment_name: Name of treatment variable
        model_type: 'diff_in_diff' or 'arima'
        result_dict: Dictionary with model results
        diagnostics_dict: Dictionary with diagnostic results
        unit_name: Specific unit being analyzed (e.g., "Finland", "India")
        unit_description: Original description if different from unit_name (e.g., "most populous country")
    
    Returns:
        Interpretation string (bullet point format)
    """
    
    try:
        if model_type == 'diff_in_diff':
            effect = result_dict.get('treatment_effect', 0)
            se = result_dict.get('se', 0)
            pval = result_dict.get('pvalue', 1)
            r_sq = result_dict.get('r_squared', 0)
            n_obs = result_dict.get('n_obs', 'unknown')
            ci_lower = result_dict.get('ci_lower', effect - 1.96*se)
            ci_upper = result_dict.get('ci_upper', effect + 1.96*se)
            
            significance = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "not significant"
            
            diagnostics_text = ""
            corrections_text = ""
            if diagnostics_dict and 'violations' in diagnostics_dict:
                violations = diagnostics_dict.get('violations', [])
                corrections = diagnostics_dict.get('corrections', [])
                corrections_text = ", ".join(corrections) if corrections else "All assumptions met"
                if violations:
                    diagnostics_text = f"\n\nDIAGNOSTIC ISSUES:\n- Violations: {', '.join(violations)}\n- Corrections applied: {corrections_text}"
            
            # Build unit info with description if available
            if unit_name and unit_description and unit_description.lower() != unit_name.lower():
                unit_info = f"\n- Unit of analysis: {unit_name} (identified as '{unit_description}')"
            elif unit_name:
                unit_info = f"\n- Unit of analysis: {unit_name}"
            else:
                unit_info = ""
            
            prompt = f"""Answer the question directly using statistical analysis results.

QUESTION: "{question}"

ANALYSIS RESULTS:
- Outcome variable: {outcome_name}
- Treatment variable: {treatment_name}{unit_info}
- Treatment effect: {effect:,.2f}
- Standard error: {se:,.2f}
- P-value: {pval:.4f}
- Statistical significance: {"Yes (p < 0.05)" if pval < 0.05 else "No (p >= 0.05)"}
- R-squared: {r_sq:.4f} ({r_sq*100:.1f}% of variation explained)
- Sample size: {n_obs:,} observations{diagnostics_text}

WRITE YOUR INTERPRETATION:

1. DIRECT ANSWER (1-2 sentences):
Answer the question directly in plain English{f' for {unit_name}' if unit_name else ''}.{f' If the question used a description like "{unit_description}", clarify that you identified this as {unit_name}.' if unit_description and unit_name and unit_description.lower() != unit_name.lower() else ''} Say whether the relationship exists, is strong/weak, positive/negative.

2. WHAT THE NUMBERS MEAN (2-3 sentences):
Explain the effect size in practical terms{f' for {unit_name}' if unit_name else ''}. Is it large or small? What does it mean in the real world?
also mention the corrections applied and what they mean for the results.

3. STATISTICAL CONFIDENCE (1-2 sentences):
How confident are we in this result? Mention the p-value in simple terms (e.g., "we're 95% confident" or "the result could be due to chance").

4. KEY TAKEAWAY (1 sentence):
Bottom line - what should someone know about the relationship between {treatment_name} and {outcome_name}{f' in {unit_name}' if unit_name else ''}?

FORMATTING RULES:
- Start directly with your answer - NO introductory phrases like "Here is..." or "Based on..."
- Use simple bullet points (just hyphens)
- Write in natural, conversational language
- Be direct and honest about what the data shows
"""
            
            interpretation = query_gemini(prompt)
            return interpretation if interpretation else "Unable to generate interpretation"
            
        elif model_type == 'arima':
            # Get forecast values
            forecasts = result_dict.get('forecasts', [])
            forecast_times = result_dict.get('forecast_times', [])
            forecast = forecasts[0] if forecasts else result_dict.get('forecast_next_period', 0)
            ar_coef = result_dict.get('ar1_coef', 0)
            last_value = result_dict.get('last_value')
            rmse = result_dict.get('rmse', 0)
            
            # Handle None values safely
            if forecast is None:
                forecast = 0
            if last_value is None:
                last_value = 0
            
            change = forecast - last_value if last_value else 0
            pct_change = (change / last_value * 100) if last_value and last_value != 0 else 0
            
            # Format values safely
            last_value_str = f"{last_value:,.2f}" if last_value else "N/A"
            forecast_str = f"{forecast:,.2f}" if forecast else "N/A"
            change_str = f"{change:,.2f}" if change else "0.00"
            pct_str = f"{pct_change:+.2f}%" if pct_change else "0.00%"
            
            # Get forecast list for better interpretation
            forecast_periods = len(forecasts)
            avg_forecast = sum(forecasts) / len(forecasts) if forecasts else forecast
            
            # Build unit info with description if available
            if unit_name and unit_description and unit_description.lower() != unit_name.lower():
                unit_info = f" for {unit_name} (identified as '{unit_description}')"
            elif unit_name:
                unit_info = f" for {unit_name}"
            else:
                unit_info = ""
            
            prompt = f"""Answer the forecasting question directly using the analysis results.

QUESTION: "{question}"

FORECAST RESULTS:
- Variable being forecasted: {outcome_name}{unit_info}
- Current value: {last_value_str}
- Next period forecast: {forecast_str}
- Forecast for next {forecast_periods} periods: {avg_forecast:,.2f} (average)
- Expected change: {change_str} ({pct_str})
- Model quality (RMSE): {rmse:,.2f}
- Trend strength (AR coefficient): {ar_coef:.3f}
- Forecast stability: {"Stable and reliable" if abs(ar_coef) < 0.7 else "Moderate persistence" if abs(ar_coef) < 1 else "High persistence / potentially explosive"}

WRITE YOUR INTERPRETATION:

1. DIRECT ANSWER (1-2 sentences):
Answer the question directly{unit_info}. What will happen to {outcome_name}? Will it go up, down, or stay the same? ALWAYS mention {unit_name if unit_name else 'the unit'} in your answer.{f' Since the question referred to "{unit_description}", make it clear you identified this as {unit_name}.' if unit_description and unit_name and unit_description.lower() != unit_name.lower() else ''}

2. THE FORECAST (2-3 sentences):
Explain what the numbers show{unit_info}. From {last_value_str} to {forecast_str} - is this a big change? What's the trend over the next {forecast_periods} periods? Provide context and deeper insight into what drives this trend.

3. CONFIDENCE IN THE FORECAST (1-2 sentences):
How reliable is this prediction? Mention the model quality and what it means for accuracy. If persistence is high, note that long-run projections can be sensitive to shocks.

4. KEY TAKEAWAY (1 sentence):
Bottom line - what's the main message about the future of {outcome_name}{unit_info}?

FORMATTING RULES:
- Start directly with your answer - NO introductory phrases like "Here is..." or "Based on..."
- Use simple bullet points (just hyphens)
- Write naturally, like explaining to a colleague
- Be direct and clear
"""
            
            interpretation = query_gemini(prompt)
            return interpretation if interpretation else "Unable to generate interpretation"
    
    except Exception as e:
        return f"Interpretation error: {str(e)}"


def interpret_diagnostics(diagnostics_result):
    """
    Generate a summary of diagnostic checks for presentation.
    
    Args:
        diagnostics_result: Dictionary from diagnostics module
    
    Returns:
        Formatted string summarizing checks
    """
    
    summary = []
    
    if 'error' in diagnostics_result:
        return f"Diagnostic Error: {diagnostics_result['error']}"
    
    summary.append(f"PRE-ANALYSIS DIAGNOSTICS ({diagnostics_result.get('model', 'Unknown')})")
    summary.append("=" * 60)
    
    checks = diagnostics_result.get('checks', [])
    violations = diagnostics_result.get('violations', [])
    corrections = diagnostics_result.get('corrections', [])
    
    for check in checks:
        if 'error' in check:
            summary.append(f"   [WARNING] {check.get('test', 'Test')}: {check['error']}")
        else:
            status = "[OK]" if not check.get('is_violated', False) else "[FAIL]"
            summary.append(f"   {status} {check.get('interpretation', 'N/A')}")
    
    if violations:
        summary.append("\nVIOLATIONS DETECTED:")
        for v in violations:
            summary.append(f"   - {v}")
    
    if corrections:
        summary.append("\nCORRECTIONS APPLIED:")
        for c in corrections:
            summary.append(f"   - {c}")
    
    if not violations:
        summary.append("\n[OK] All diagnostic checks passed!")
    
    return "\n".join(summary)
