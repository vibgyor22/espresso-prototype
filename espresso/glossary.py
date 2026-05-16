"""
Plain-English definitions for the econometric terms Espresso uses.

The REPL exposes these via `?<term>`. The terminal renderer also underlines any
glossary term that appears in result text so users know they can look it up.
"""

from __future__ import annotations

GLOSSARY: dict[str, str] = {
    "p-value": (
        "The probability of seeing a result this extreme just by chance if there "
        "were truly no effect. Smaller is stronger evidence. A common (but arbitrary) "
        "cutoff is 0.05 — i.e. less than a 5% chance."
    ),
    "confidence interval": (
        "A range that, with the stated probability (usually 95%), would contain "
        "the true value if we repeated this analysis many times on similar data. "
        "If the interval crosses zero, we can't rule out 'no effect'."
    ),
    "95% ci": (
        "See 'confidence interval' — the most common version."
    ),
    "standard error": (
        "How wobbly our estimate is — roughly, the typical size of the difference "
        "between this estimate and the true value if we re-ran the analysis on a "
        "fresh sample."
    ),
    "r-squared": (
        "Share of the variation in the outcome that the model explains. "
        "0 = nothing, 1 = perfectly. Useful for comparing fit, but a high value "
        "doesn't mean the result is causal."
    ),
    "fixed effects": (
        "A trick to absorb everything that's constant within a group (e.g. each "
        "country's permanent quirks, or each year's global shocks) so the "
        "estimate only reflects *within-group changes*."
    ),
    "twfe": (
        "Two-Way Fixed Effects — controls for both unit-level constants (each "
        "country) and time-level shocks (each year) at once."
    ),
    "stationarity": (
        "A time series is stationary if its mean and variance don't drift over "
        "time. Most forecasting and regression models assume stationarity; if a "
        "series isn't, we typically take first differences."
    ),
    "adf": (
        "Augmented Dickey-Fuller test — checks whether a time series has a unit "
        "root (i.e. is non-stationary). A small p-value means stationary."
    ),
    "elasticity": (
        "Percentage change in the outcome for a 1% change in the predictor. "
        "Comes from a log-log regression."
    ),
    "semi-elasticity": (
        "Percent change in the outcome for a 1-unit change in the predictor. "
        "Comes from a log-linear regression."
    ),
    "diff-in-diff": (
        "Compares the *change* in the outcome over time in a treated group to "
        "the *change* in an untreated comparison group. The difference of "
        "differences is the treatment effect — under the assumption that both "
        "groups would have moved in parallel without treatment."
    ),
    "parallel trends": (
        "The core assumption of diff-in-diff: treated and untreated groups would "
        "have trended the same way in the absence of treatment. We test it by "
        "looking at pre-treatment trends."
    ),
    "ols": (
        "Ordinary Least Squares — the standard linear regression that minimizes "
        "the sum of squared prediction errors."
    ),
    "arima": (
        "AutoRegressive Integrated Moving Average — a flexible time-series model "
        "for forecasting based on (p) past values, (d) differences taken to make "
        "the series stationary, and (q) past forecast errors."
    ),
    "heteroscedasticity": (
        "Unequal variance of errors across observations. Doesn't bias the "
        "estimate but does make standard errors wrong unless we use robust SEs."
    ),
    "autocorrelation": (
        "Errors that are correlated across time. Common in time series; if "
        "present, standard errors are too small unless corrected."
    ),
    "multicollinearity": (
        "Two or more predictors moving together so closely that the model can't "
        "separate their individual effects. Inflates standard errors."
    ),
    "clustered se": (
        "Standard errors that allow for correlation within groups (e.g. within a "
        "country across years). Wider but more honest than vanilla SEs in panel data."
    ),
    "robust se": (
        "Standard errors that don't assume constant variance. HC1 is the common "
        "small-sample-corrected variant."
    ),
    "treatment effect": (
        "The estimated change in the outcome that is *caused* by the treatment, "
        "averaged over the treated units."
    ),
    "panel data": (
        "Repeated observations of the same units (countries, firms, people) over "
        "time. Lets us control for unit-level constants."
    ),
}


# Aliases the renderer should also link.
_ALIASES = {
    "p-values": "p-value",
    "ci": "confidence interval",
    "fe": "fixed effects",
    "se": "standard error",
    "r²": "r-squared",
    "did": "diff-in-diff",
    "difference-in-differences": "diff-in-diff",
}


def define(term: str) -> str:
    """Return the definition for a term (case-insensitive), or a helpful miss."""
    key = term.lower().strip().lstrip("?").strip()
    if key in GLOSSARY:
        return GLOSSARY[key]
    if key in _ALIASES:
        return GLOSSARY[_ALIASES[key]]
    # try partial match
    for k in GLOSSARY:
        if key in k or k in key:
            return GLOSSARY[k]
    return f"No definition found for '{term}'. Try one of: {', '.join(sorted(GLOSSARY)[:8])}…"


def known_terms() -> list[str]:
    return sorted(set(list(GLOSSARY) + list(_ALIASES)))
