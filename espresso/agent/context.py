"""
Qualitative, context-aware interpretation.

Wraps a single LLM call that returns five sub-blocks (domain, past trends,
news context, literature benchmark, sanity check). Never asks the LLM to
compute numbers — only to *narrate around* numbers we computed.

When the LLM is unavailable, the local fallbacks are computed from the actual
numbers and column metadata so the output is still substantive — not "no
context available" placeholders.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Optional

import pandas as pd

from llm import query_gemini
from .prompts import (CONTEXT_INTERPRET_PROMPT, WHY_COLUMNS_PROMPT, WHY_MODEL_PROMPT,
                      FOLLOWUP_PROMPT, VERDICT_PROMPT, STAT_PLAIN_ENGLISH_PROMPT,
                      DEEP_ANALYSIS_PROMPT, WEB_RESEARCH_PROMPT)

# Color tokens shared with terminal.py palette
_PC = {"brand": "#D4A85A", "warning": "#F39C12", "world": "#3498DB", "success": "#6AB08A"}
P_BRAND   = _PC["brand"]
P_WARNING = _PC["warning"]
P_WORLD   = _PC["world"]


# ---------------------------------------------------------------------------
# Domain inference from column names (no LLM)
# ---------------------------------------------------------------------------

_DOMAIN_HINTS = [
    (("gdp", "inflation", "interest_rate", "unemployment", "monetary"),    "macroeconomics"),
    (("wage", "income", "employment", "labor", "labour", "minimum_wage"),  "labor economics"),
    (("school", "education", "test_score", "literacy", "enrollment"),      "education"),
    (("health", "mortality", "infant", "obesity", "diabetes", "hospital"), "public health"),
    (("calorie", "nutrition", "food", "diet", "bmi"),                      "nutrition / food"),
    (("price", "stock", "return", "volatility", "yield", "spread"),        "finance"),
    (("co2", "emission", "carbon", "temperature", "climate", "pollution"), "climate / environment"),
    (("trade", "export", "import", "tariff"),                              "international trade"),
    (("crime", "arrest", "incarceration", "policing"),                     "crime"),
    (("poverty", "inequality", "gini"),                                    "inequality"),
    (("housing", "rent", "mortgage", "real_estate"),                       "housing"),
]


def _infer_domain(outcome: str, treatment: Optional[str]) -> Optional[str]:
    text = " ".join(filter(None, [outcome or "", treatment or ""])).lower()
    for keys, label in _DOMAIN_HINTS:
        if any(k in text for k in keys):
            return label
    return None


# ---------------------------------------------------------------------------
# Local helpers — past trends, sanity, magnitudes
# ---------------------------------------------------------------------------

def _trend_summary(df, outcome: Optional[str], time: Optional[str]) -> str:
    if df is None or outcome is None or outcome not in df.columns:
        return ""
    try:
        y = pd.to_numeric(df[outcome], errors="coerce").dropna()
        if y.empty:
            return ""
        n = len(y)
        mean = float(y.mean()); std = float(y.std()) if n > 1 else 0.0
        lo, hi = float(y.min()), float(y.max())

        # direction over time if a time column is present
        direction_txt = ""
        if time and time in df.columns and n >= 3:
            try:
                sub = df[[time, outcome]].dropna()
                sub[time] = pd.to_numeric(sub[time], errors="coerce")
                sub = sub.dropna().sort_values(time)
                if len(sub) >= 3:
                    early = float(pd.to_numeric(sub[outcome], errors="coerce").iloc[: max(1, len(sub) // 4)].mean())
                    late = float(pd.to_numeric(sub[outcome], errors="coerce").iloc[-max(1, len(sub) // 4):].mean())
                    change = late - early
                    pct = (change / early * 100) if early else 0.0
                    arrow = "rose" if change > 0 else "fell" if change < 0 else "stayed flat"
                    direction_txt = (
                        f" Over the observed period, `{outcome}` {arrow} from "
                        f"~{early:.4g} to ~{late:.4g} ({pct:+.1f}%)."
                    )
            except Exception:
                pass

        vol = (std / abs(mean)) if mean else 0
        vol_txt = (
            "low volatility relative to its mean" if vol < 0.1 else
            "moderate volatility relative to its mean" if vol < 0.4 else
            "high volatility relative to its mean"
        )
        lines = [f"Range {lo:.4g}–{hi:.4g}  ·  mean {mean:.4g}  ·  std {std:.4g}  ·  {vol_txt}"]
        if direction_txt:
            lines.append(direction_txt.strip(". "))
        return "\n".join(f"- {l}" for l in lines)
    except Exception:
        return ""


def _sanity_check(outcome: str, treatment: Optional[str], result: dict, df, model: str) -> str:
    """Local plausibility check on sign, magnitude, and sample size."""
    notes = []
    eff = (
        result.get("treatment_effect")
        or result.get("slope")
        or result.get("effect")
        or 0
    )
    pval = result.get("pvalue", result.get("p_value", 1)) or 1
    ci_lo_raw = result.get("ci_lower"); ci_hi_raw = result.get("ci_upper")
    try:
        ci_lo = float(ci_lo_raw) if ci_lo_raw is not None else None
        ci_hi = float(ci_hi_raw) if ci_hi_raw is not None else None
    except Exception:
        ci_lo = ci_hi = None
    n = result.get("n_obs", 0) or 0
    r2 = result.get("r_squared", 0) or 0

    # Magnitude relative to outcome scale
    try:
        if df is not None and outcome in df.columns:
            y = pd.to_numeric(df[outcome], errors="coerce").dropna()
            if not y.empty and abs(y.mean()) > 0:
                rel = abs(eff) / abs(y.mean())
                if rel > 1.0 and abs(eff) > 0:
                    notes.append(
                        f"Effect size ({eff:g}) is as large as the mean `{outcome}` "
                        f"({y.mean():.4g}) — unusually large; check units and reverse causality."
                    )
                elif rel < 0.001 and abs(eff) > 0:
                    notes.append(
                        f"Effect ({eff:g}) is tiny vs mean `{outcome}` ({y.mean():.4g})"
                        " — statistically detectable but economically negligible."
                    )
    except Exception:
        pass

    # Sample size
    if n and n < 30:
        notes.append(
            f"Sample size is small ({n} observations); standard errors are wide and the "
            "estimate could swing if you added more data."
        )

    # Confidence
    if ci_lo is not None and ci_hi is not None and ci_lo <= 0 <= ci_hi:
        notes.append("The 95% confidence interval crosses zero — we can't rule out no effect.")

    if pval > 0.1:
        notes.append(f"p-value of {pval:.3f} is weak evidence — treat the sign as suggestive at best.")

    # Fit
    if r2 is not None and r2 < 0.05 and "forecast" not in model.lower():
        notes.append(
            f"R² is only {r2:.3f}, so this predictor alone explains very little of the "
            f"variation in `{outcome}` — there are likely other important drivers."
        )

    if not notes:
        notes.append(
            f"Sign and magnitude are plausible. Usual caveat: omitted variables "
            f"correlated with both `{treatment}` and `{outcome}` could still bias the estimate."
        )
    return "\n".join(f"- {n}" for n in notes)


def _domain_block(outcome: str, treatment: Optional[str], unit: Optional[str],
                  time_range: str, df, profile) -> str:
    domain = _infer_domain(outcome, treatment)
    lines = []
    if domain:
        lines.append(f"{domain} domain")
    lines.append(f"Outcome: {outcome}" + (f"  ·  Predictor: {treatment}" if treatment else ""))
    if profile is not None:
        col = profile.column(outcome) if hasattr(profile, "column") else None
        if col and col.min is not None and col.max is not None:
            scale = f"[{col.min:.4g}, {col.max:.4g}]" + (f" {col.inferred_unit}" if col.inferred_unit else "")
            lines.append(f"Range: {scale}" + (f"  across {time_range}" if time_range else ""))
    return "\n".join(f"- {l}" for l in lines if l)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _safe_loads(text: str, fallback: Any) -> Any:
    if not text:
        return fallback
    try:
        s = text.strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s.lower().startswith("json"):
                s = s[4:].strip()
        if "{" in s and "}" in s and not s.lstrip().startswith("["):
            s = s[s.index("{"): s.rindex("}") + 1]
        elif "[" in s and "]" in s and s.lstrip().startswith("["):
            s = s[s.index("["): s.rindex("]") + 1]
        return json.loads(s)
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# Public — context_interpret with strong local fallbacks
# ---------------------------------------------------------------------------

def _local_blocks(*, outcome, treatment, unit, time_range, model, result, df, profile, time_col):
    """Compute the five blocks entirely locally — used as fallback per-key."""
    return {
        "domain": _domain_block(outcome, treatment, unit, time_range, df, profile),
        "past_trends": _trend_summary(df, outcome, time_col) or "",
        "literature": "",
        "sanity_check": _sanity_check(outcome, treatment, result, df, model),
    }


def context_interpret(
    *,
    question: str,
    outcome: str,
    treatment: str | None,
    unit: str | None,
    time_range: str,
    model: str,
    result: dict,
    historical_summary: str = "",
    df=None,
    profile=None,
    time_col: str | None = None,
) -> dict[str, str]:
    """Return the five qualitative sub-blocks, with substantive local fallbacks."""
    local = _local_blocks(
        outcome=outcome, treatment=treatment, unit=unit, time_range=time_range,
        model=model, result=result, df=df, profile=profile, time_col=time_col,
    )

    estimate = (
        result.get("treatment_effect")
        or result.get("slope")
        or result.get("effect")
        or (result.get("forecasts", [None])[0] if result.get("forecasts") else None)
    )
    repl = {
        "__OUTCOME__": str(outcome),
        "__TREATMENT__": str(treatment or "(none)"),
        "__UNIT__": str(unit or "(none)"),
        "__TIME_RANGE__": str(time_range or "(unknown)"),
        "__QUESTION__": str(question),
        "__MODEL__": str(model),
        "__ESTIMATE__": f"{estimate:.4f}" if isinstance(estimate, (int, float)) else str(estimate),
        "__SE__": f"{(result.get('se') or 0):.4f}",
        "__CI_LO__": f"{result.get('ci_lower', 0):.4f}" if result.get("ci_lower") is not None else "?",
        "__CI_HI__": f"{result.get('ci_upper', 0):.4f}" if result.get("ci_upper") is not None else "?",
        "__PVAL__": f"{(result.get('pvalue', result.get('p_value', 1)) or 1):.4f}",
        "__HISTORICAL_SUMMARY__": str(historical_summary or "(not provided)"),
    }
    prompt = CONTEXT_INTERPRET_PROMPT
    for k, v in repl.items():
        prompt = prompt.replace(k, v)
    raw = query_gemini(prompt)
    parsed = _safe_loads(raw, {})

    out = dict(local)  # start from substantive local prose
    if isinstance(parsed, dict):
        for k in ("domain", "past_trends", "literature", "sanity_check"):
            v = parsed.get(k)
            if isinstance(v, str) and v.strip() and len(v.strip()) > 12:
                out[k] = v.strip()
    return out


# ---------------------------------------------------------------------------
# why_columns / why_model with substantive local fallbacks
# ---------------------------------------------------------------------------

def why_columns(*, question: str, outcome: str, treatment, unit, time, columns_summary: str) -> str:
    prompt = WHY_COLUMNS_PROMPT.format(
        question=question,
        outcome=outcome or "(none)",
        treatment=treatment or "(none)",
        unit=unit or "(none)",
        time=time or "(none)",
        columns=columns_summary,
    )
    text = query_gemini(prompt)
    if text and text.strip():
        return text.strip()

    parts = []
    if outcome:
        parts.append(
            f"I picked **`{outcome}`** as the outcome because it's the variable your question "
            "is really asking about — what we want to explain or predict."
        )
    if treatment:
        parts.append(
            f"I'm using **`{treatment}`** as the predictor — the thing whose relationship "
            f"with `{outcome}` we're measuring."
        )
    if unit and time:
        parts.append(
            f"The data is organized by **`{unit}`** across **`{time}`**, which lets us "
            f"separate the effect we care about from things that vary across {unit}s or over time."
        )
    elif unit:
        parts.append(f"Each row is a distinct **`{unit}`**.")
    elif time:
        parts.append(f"The data is a single series indexed by **`{time}`**.")
    return " ".join(parts) if parts else "No column mapping was produced."


def why_model(*, question: str, model_display: str, structure: str,
              outcome: str, treatment, unit, time) -> str:
    prompt = WHY_MODEL_PROMPT.format(
        question=question,
        model_display=model_display,
        structure=structure,
        outcome=outcome or "(none)",
        treatment=treatment or "(none)",
        unit=unit or "(none)",
        time=time or "(none)",
    )
    text = query_gemini(prompt)
    if text and text.strip():
        return text.strip()

    # Substantive local fallback per model family
    name = (model_display or "").lower()
    if "difference-in-differences" in name or "twfe" in name:
        return (
            f"**Difference-in-Differences** compares the *change* in `{outcome}` over time for "
            f"units that received the treatment versus units that didn't. The 'treatment effect' "
            f"below is the extra change attributable to the treatment itself — under the "
            f"assumption that, without it, both groups would have moved in parallel. "
            f"This fits because your data tracks the same {unit or 'units'} over multiple "
            f"{time or 'periods'}, with treatment turning on for some but not all."
        )
    if "panel ols" in name or "two-way fe" in name:
        return (
            f"**Panel OLS with two-way fixed effects** absorbs everything that's constant "
            f"per `{unit}` and everything that's a common shock per `{time}`, so the "
            f"coefficient below reflects within-{unit} variation only. That's the standard "
            f"workhorse for panel data when you want association rather than a causal claim."
        )
    if "arima" in name:
        return (
            f"**ARIMA** captures how `{outcome}` depends on its own past values and past "
            f"forecast errors, automatically picking the order (p,d,q) that best fits the "
            f"data. It's the standard forecasting model for a single time series like this one."
        )
    if "linear trend" in name:
        return (
            f"**Linear trend** fits a straight line of `{outcome}` against time. It's a "
            "transparent baseline — useful for stable series, but it won't capture cycles or shocks."
        )
    if "exponential smoothing" in name:
        return (
            f"**Exponential smoothing** weights recent observations of `{outcome}` more heavily "
            "than older ones. Good for noisy or short series with no strong seasonal pattern."
        )
    if "log-log" in name:
        return (
            f"**Log-log regression** estimates the elasticity of `{outcome}` with respect to "
            f"`{treatment}` — a 1% change in `{treatment}` is associated with the coefficient% "
            "change in `{outcome}`. Both variables must be strictly positive."
        )
    if "log-linear" in name:
        return (
            f"**Log-linear regression** estimates the semi-elasticity: a 1-unit change in "
            f"`{treatment}` is associated with the coefficient × 100 percent change in `{outcome}`."
        )
    if "ols" in name:
        return (
            f"**OLS** fits a straight line of `{outcome}` on `{treatment}`. With "
            f"heteroscedasticity-robust standard errors, it's the right baseline for a "
            f"{structure} dataset without panel structure. The slope below is the estimated "
            f"change in `{outcome}` for a one-unit change in `{treatment}`."
        )
    return (
        f"**{model_display}** is the recommended approach given your data's {structure} "
        f"structure. The coefficient below summarizes the estimated relationship between "
        f"`{treatment or 'the predictor'}` and `{outcome}`, with a standard error indicating precision."
    )


# ---------------------------------------------------------------------------
# Deep analysis (paragraph-level narrative)
# ---------------------------------------------------------------------------

def deep_analysis(*, question: str, outcome: str, treatment: str, domain: str,
                  model: str, estimate: float, se: float, pvalue: float,
                  ci_lo: float, ci_hi: float, r2: float, n_obs: int,
                  time_range: str, hist_summary: str, web_context: str) -> str:
    """4-paragraph narrative analysis. Always returns substantive prose."""
    prompt = DEEP_ANALYSIS_PROMPT.format(
        question=question, outcome=outcome, treatment=treatment or "(none)",
        domain=domain or "economics", model=model,
        estimate=f"{estimate:+.4f}", se=f"{se:.4f}", pvalue=f"{pvalue:.4f}",
        ci_lo=f"{ci_lo:.3f}", ci_hi=f"{ci_hi:.3f}",
        r2=f"{r2:.3f}", n_obs=n_obs,
        time_range=time_range or "unknown", hist_summary=hist_summary or "N/A",
        web_context=web_context or "No web context available.",
    )
    try:
        raw = (query_gemini(prompt, system="You are a senior economist. Write prose paragraphs only.") or "").strip()
        if raw and len(raw) > 100:
            return raw
    except Exception:
        pass
    return _fallback_deep_analysis(outcome, treatment, estimate, pvalue, ci_lo, ci_hi, r2, n_obs, domain)


def _fallback_deep_analysis(outcome: str, treatment: str, estimate: float, pvalue: float,
                              ci_lo: float, ci_hi: float, r2: float, n_obs: int, domain: str) -> str:
    direction = "rise" if estimate > 0 else "fall"
    ci_dir = "rules out zero" if (ci_lo > 0 or ci_hi < 0) else "spans zero"
    certainty = "high" if pvalue < 0.05 else ("moderate" if pvalue < 0.10 else "low")

    return (
        f"**Magnitude**\n"
        f"- Estimate {estimate:+.3f} → {outcome} {direction} of {abs(estimate):.3g} per unit {treatment}.\n"
        f"- CI [{ci_lo:.2f}, {ci_hi:.2f}] {ci_dir}; certainty is {certainty} (p={pvalue:.3f}).\n"
        f"\n"
        f"**Mechanism**\n"
        f"- In {domain}, {treatment} typically affects {outcome} via demand/supply channels.\n"
        f"- Plausible confounders: macro cycles, institutional factors, measurement timing.\n"
        f"\n"
        f"**What you didn't ask**\n"
        f"- Average effect may mask heterogeneity — try splitting by subgroup or era.\n"
        f"- Model captures only {r2*100:.1f}% of variation; other drivers likely matter more.\n"
        f"\n"
        f"**Threats to validity**\n"
        f"- Reverse causality: {outcome} may itself influence {treatment}, biasing the estimate.\n"
        f"- IV, natural experiment, or richer controls would help resolve this.\n"
    )


# ---------------------------------------------------------------------------
# Web research context (LLM knowledge as research briefing)
# ---------------------------------------------------------------------------

def web_research_context(*, outcome: str, treatment: str, domain: str,
                          time_range: str, question: str) -> str:
    """Ask the LLM to surface its empirical knowledge as a research briefing."""
    # Infer geography hint from column names / domain
    geography = "international" if any(k in (outcome + treatment).lower()
                                       for k in ("oecd", "world", "global", "country")) else "economy"
    prompt = WEB_RESEARCH_PROMPT.format(
        question=question, domain=domain or "economics",
        outcome=outcome, treatment=treatment or "(unspecified)",
        time_range=time_range or "recent decades", geography=geography,
    )
    try:
        raw = (query_gemini(prompt, system="You are an economics research assistant. Be specific and cite real findings.") or "").strip()
        if raw and len(raw) > 50:
            return raw
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Proactive insights (pure pandas — no LLM, no failure mode)
# ---------------------------------------------------------------------------

def compute_proactive_insights(df: pd.DataFrame, result: dict, intent: dict,
                                known_law: Optional[dict] = None) -> list:
    """
    Data-driven observations the user didn't ask for.
    Returns list of {icon, color, heading, body} dicts.
    """
    insights = []
    outcome  = intent.get("outcome", "")
    treatment = intent.get("treatment", "")
    unit     = intent.get("unit", "")
    time_col = intent.get("time", "")
    eff      = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    n        = result.get("n_obs", 0) or len(df)

    try:
        # 1) Known economic law match
        if known_law:
            bench = known_law.get("benchmark", "")
            insights.append({
                "icon": "◈", "color": P_WORLD,
                "heading": known_law["name"],
                "body": f"{known_law['description']} Benchmark: {bench}",
            })

        # 2) Outlier observations (residual > 2σ from mean residual)
        if outcome in df.columns and treatment in df.columns:
            try:
                o_num = pd.to_numeric(df[outcome], errors="coerce")
                x_num = pd.to_numeric(df[treatment], errors="coerce")
                both  = pd.concat([o_num, x_num], axis=1).dropna()
                if len(both) >= 6:
                    xv = both.iloc[:, 0].values
                    yv = both.iloc[:, 1].values
                    mean_x, mean_y = xv.mean(), yv.mean()
                    fitted = mean_y + eff * (xv - mean_x)
                    resids = yv - fitted
                    r_std  = resids.std() or 1.0
                    outlier_idx = [i for i, r in enumerate(resids) if abs(r) > 2.0 * r_std]
                    if outlier_idx:
                        # Try to identify the unit/time label for these rows
                        labels = []
                        for i in outlier_idx[:3]:
                            row = df.dropna(subset=[outcome, treatment]).iloc[i]
                            parts = []
                            if unit and unit in df.columns:
                                parts.append(str(row.get(unit, "")))
                            if time_col and time_col in df.columns:
                                parts.append(str(row.get(time_col, "")))
                            labels.append(" ".join(filter(None, parts)) or str(i))
                        insights.append({
                            "icon": "⚡", "color": P_WARNING,
                            "heading": f"{len(outlier_idx)} outlier observation(s): {', '.join(labels[:3])}",
                            "body": (f"These observations deviate >2σ from the model's prediction. "
                                     "They may be influential — re-running without them tests robustness."),
                        })
            except Exception:
                pass

        # 3) Outlier units (unit-level means, threshold 1.5σ for small panels)
        if unit and unit in df.columns and outcome in df.columns:
            try:
                sub = df[[unit, outcome]].copy()
                sub[outcome] = pd.to_numeric(sub[outcome], errors="coerce")
                grp = sub.groupby(unit)[outcome].mean().dropna()
                if len(grp) >= 3:
                    mean_g, std_g = grp.mean(), grp.std()
                    thresh = 1.5 * std_g  # 1.5σ more sensitive than 2.0
                    outliers = grp[abs(grp - mean_g) > thresh]
                    if not outliers.empty and len(outliers) < len(grp):  # not all are outliers
                        names = ", ".join(str(k) for k in outliers.index[:3])
                        vals  = ", ".join(f"{v:.3g}" for v in outliers.values[:3])
                        insights.append({
                            "icon": "⚡", "color": P_WARNING,
                            "heading": f"Unusual units: {names}",
                            "body": (f"{names} has average {outcome} ({vals}) "
                                     f"that's unusually high/low relative to others. "
                                     "This unit may dominate the result — test robustness without it."),
                        })
            except Exception:
                pass

        # 4) Strongest unexpected correlation — include time col, exclude only exact pair
        numeric_cols = [c for c in df.columns
                        if pd.api.types.is_numeric_dtype(df[c])
                        and c != outcome and c != treatment and c != unit
                        and df[c].nunique() > 2][:8]
        if outcome in df.columns and numeric_cols:
            oc = pd.to_numeric(df[outcome], errors="coerce")
            best_r, best_col = 0.0, ""
            for col in numeric_cols:
                try:
                    xc = pd.to_numeric(df[col], errors="coerce")
                    paired = pd.concat([oc, xc], axis=1).dropna()
                    if len(paired) < 5:
                        continue
                    r = paired.corr().iloc[0, 1]
                    if abs(r) > abs(best_r) and abs(r) > 0.4:
                        best_r, best_col = r, col
                except Exception:
                    pass
            if best_col:
                dir_str = "positively" if best_r > 0 else "negatively"
                insights.append({
                    "icon": "◈", "color": P_BRAND,
                    "heading": f"Stronger signal: {best_col} (r={best_r:+.2f})",
                    "body": (f"{best_col} is {dir_str} correlated with {outcome} more strongly "
                             f"than {treatment} (r={best_r:.2f}). "
                             "Consider including it as a control or running a separate analysis."),
                })

        # 5) Non-linearity hint (compare linear R² vs quadratic R²)
        if treatment and outcome and treatment in df.columns and outcome in df.columns:
            try:
                x = pd.to_numeric(df[treatment], errors="coerce")
                y = pd.to_numeric(df[outcome],   errors="coerce")
                valid = pd.concat([x, y], axis=1).dropna()
                if len(valid) >= 10:
                    xv = valid.iloc[:, 0].values
                    yv = valid.iloc[:, 1].values
                    # Linear R²
                    xm = xv.mean()
                    lin_pred = xm + (eff * (xv - xm))
                    ss_res_lin = ((yv - lin_pred) ** 2).sum()
                    ss_tot = ((yv - yv.mean()) ** 2).sum() or 1
                    r2_lin = 1 - ss_res_lin / ss_tot
                    # Quadratic R² (simple, no numpy poly needed)
                    x2 = (xv - xm) ** 2
                    x2m = x2.mean()
                    import numpy as _np
                    X = _np.column_stack([xv - xm, x2 - x2m])
                    try:
                        coef = _np.linalg.lstsq(
                            _np.column_stack([_np.ones(len(X)), X]), yv, rcond=None
                        )[0]
                        quad_pred = coef[0] + coef[1] * (xv - xm) + coef[2] * (x2 - x2m)
                        ss_res_quad = ((yv - quad_pred) ** 2).sum()
                        r2_quad = 1 - ss_res_quad / ss_tot
                        if r2_quad - r2_lin > 0.05 and n >= 15:
                            insights.append({
                                "icon": "⚡", "color": P_WARNING,
                                "heading": "Non-linear relationship detected",
                                "body": (f"A quadratic fit explains {r2_quad*100:.1f}% vs linear {r2_lin*100:.1f}% "
                                         f"of {outcome} variation. The relationship between "
                                         f"{treatment} and {outcome} may have diminishing returns "
                                         "or a threshold. Try log-log or polynomial regression."),
                            })
                    except Exception:
                        pass
            except Exception:
                pass

        # 6) Low treatment variation warning
        if treatment and treatment in df.columns:
            try:
                tv = pd.to_numeric(df[treatment], errors="coerce").dropna()
                cv = tv.std() / abs(tv.mean()) if abs(tv.mean()) > 0.001 else 0
                if 0 < cv < 0.05 and len(tv) > 5:
                    insights.append({
                        "icon": "⚠", "color": P_WARNING,
                        "heading": f"Low variation in {treatment} (CV={cv:.1%})",
                        "body": ("The predictor barely varies across observations. "
                                 "This reduces statistical power and makes the estimate unreliable. "
                                 "Consider whether a different sample or time window has more variation."),
                    })
            except Exception:
                pass

    except Exception:
        pass

    return insights[:5]  # cap at 5 insights


# ---------------------------------------------------------------------------
# Verdict generation
# ---------------------------------------------------------------------------

def generate_verdict(*, outcome: str, treatment: str, estimate: float, pvalue: float,
                     ci_lo: float, ci_hi: float, model: str, is_causal: bool = False) -> str:
    """Generate a one-sentence plain-English verdict for the analysis."""
    prompt = VERDICT_PROMPT.format(
        outcome=outcome, treatment=treatment or "(none)",
        estimate=f"{estimate:+.4f}", pvalue=f"{pvalue:.4f}",
        ci_lo=f"{ci_lo:.3f}", ci_hi=f"{ci_hi:.3f}",
        model=model, is_causal=str(is_causal),
    )
    try:
        raw = (query_gemini(prompt) or "").strip()
        if raw and len(raw) > 20:
            # Strip JSON if accidentally returned
            raw = re.sub(r'^[\[\{"\']+|[\]\}"\']+$', "", raw).strip()
            return raw[:300]
    except Exception:
        pass
    return _fallback_verdict(outcome, treatment, estimate, pvalue, ci_lo, ci_hi)


def _fallback_verdict(outcome: str, treatment: str, estimate: float, pvalue: float,
                      ci_lo: float, ci_hi: float) -> str:
    direction = "rises" if estimate > 0 else "falls"
    mag = abs(estimate)
    t_str = treatment or "the predictor"
    o_str = outcome or "the outcome"
    if pvalue < 0.05:
        ci_sign = (ci_lo > 0) or (ci_hi < 0)
        if ci_sign:
            return (
                f"A 1-unit increase in {t_str} is associated with a **{direction} of {mag:.3g}** "
                f"in {o_str} — the evidence supports this direction."
            )
        return (
            f"A 1-unit increase in {t_str} is associated with a **{direction} of {mag:.3g}** "
            f"in {o_str} (p={pvalue:.3f})."
        )
    return (
        f"No clear evidence that {t_str} affects {o_str} in this dataset "
        f"— the estimated change of {estimate:+.3g} could easily be chance (p={pvalue:.3f})."
    )


# ---------------------------------------------------------------------------
# Plain-English stats translation
# ---------------------------------------------------------------------------

def plain_english_stats(*, estimate: float, pvalue: float, ci_lo: float, ci_hi: float,
                         r2: float, n_obs: int, units: str = "") -> str:
    """Translate statistical numbers into plain English bullet points."""
    prompt = STAT_PLAIN_ENGLISH_PROMPT.format(
        estimate=f"{estimate:+.4f}", units=units,
        pvalue=f"{pvalue:.4f}",
        ci_lo=f"{ci_lo:.3f}", ci_hi=f"{ci_hi:.3f}",
        r2=f"{r2:.3f}", n_obs=n_obs,
    )
    try:
        raw = (query_gemini(prompt) or "").strip()
        if raw and len(raw) > 20:
            return raw
    except Exception:
        pass
    return _fallback_plain_english(estimate, pvalue, ci_lo, ci_hi, r2, n_obs)


def _fallback_plain_english(estimate: float, pvalue: float, ci_lo: float, ci_hi: float,
                              r2: float, n_obs: int) -> str:
    chance_pct = min(99, int(pvalue * 100))
    confidence_pct = 100 - chance_pct
    mag = abs(estimate)
    direction = "increase" if estimate > 0 else "decrease"

    line1 = f"- On average, a 1-unit change is associated with a {direction} of roughly {mag:.3g}."

    if pvalue < 0.05:
        line2 = (f"- We're about {confidence_pct}% confident this isn't just random noise "
                 f"({chance_pct}% chance it's coincidence).")
    else:
        line2 = (f"- There's a {chance_pct}% chance a gap this large would appear even if "
                 f"there were truly no relationship — so we can't confirm it.")

    ci_crosses_zero = ci_lo < 0 < ci_hi
    if ci_crosses_zero:
        line2 += " The range of plausible values spans both directions."

    line3 = f"- This relationship accounts for {r2*100:.1f}% of the variation in the outcome"
    if r2 < 0.10:
        line3 += " — other factors matter much more."
    elif r2 < 0.30:
        line3 += " — a modest but partial explanation."
    else:
        line3 += " — a substantial portion of what drives the outcome."

    return f"{line1}\n{line2}\n{line3}"


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

def suggest_followups(*, question: str, outcome: str, treatment, model: str, result_summary: str) -> list[str]:
    prompt = FOLLOWUP_PROMPT.format(
        question=question,
        outcome=outcome,
        treatment=treatment or "(none)",
        model=model,
        result_summary=result_summary,
    )
    text = query_gemini(prompt)
    parsed = _safe_loads(text, [])
    if isinstance(parsed, list) and parsed:
        return [str(s).strip() for s in parsed if str(s).strip()][:5]
    # Substantive local fallback follow-ups, tailored to the model family
    name = (model or "").lower()
    if "difference-in-differences" in name:
        return [
            f"Re-run with a first-difference estimator as a robustness check on {outcome}.",
            f"Drop the most influential unit and see if the effect on {outcome} survives.",
            f"Restrict to a narrower time window around the treatment and re-estimate.",
            f"Add a placebo test using a fake treatment period before the real one.",
        ]
    if "panel ols" in name or "two-way fe" in name:
        return [
            f"Try the same regression with only unit fixed effects (no time FE).",
            f"Re-run on a subset of years to check stability over time.",
            f"What if {treatment or 'the predictor'} increased by 10% across all units?",
            f"Compare the effect across distinct subgroups of {outcome}.",
        ]
    if "arima" in name or "forecast" in name or "trend" in name or "smoothing" in name:
        return [
            f"Forecast {outcome} over a longer horizon (e.g. 20 periods).",
            f"What if {outcome} took a -1 SD shock next period?",
            f"Compare ARIMA against a random-walk baseline.",
            f"Add a structural break around a known event and re-forecast.",
        ]
    return [
        f"Robustness check: try a different model for {outcome}.",
        f"Subset the data (year range, unit) and re-run.",
        f"What if {treatment or 'the predictor'} changed by 10%?",
        f"Add a control variable to absorb confounders.",
    ]
