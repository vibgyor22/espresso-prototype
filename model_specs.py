# Espresso model registry
#
# Each entry defines what a model needs to run and what kind of question it
# answers.  The selector uses these specs to filter admissible models given
# the parsed intent and the loaded dataset.

MODEL_SPECS = {
    # ------------------------------------------------------------------
    # Causal inference
    # ------------------------------------------------------------------
    "diff_in_diff": {
        "question_type": "causal_effect",
        "display_name": "Difference-in-Differences (TWFE)",
        "description": (
            "Two-Way Fixed Effects estimator with unit and time fixed effects. "
            "Estimates average treatment effect with unit-clustered SEs."
        ),
        "required_fields": ["outcome", "treatment", "unit", "time"],
        "requires_panel": True,
        "requires_treatment_variation": True,
    },

    # ------------------------------------------------------------------
    # Forecasting
    # ------------------------------------------------------------------
    "arima": {
        "question_type": "forecast",
        "display_name": "ARIMA (auto-order)",
        "description": (
            "Auto-selected ARIMA(p,d,q) via AIC grid search using statsmodels. "
            "Falls back to AR(1) OLS when statsmodels is unavailable."
        ),
        "required_fields": ["outcome", "time"],
        "requires_panel": False,
    },
    "linear_trend": {
        "question_type": "forecast",
        "display_name": "Linear trend forecast",
        "description": (
            "OLS trend model y_t = alpha + beta*time with robust prediction "
            "intervals. Useful as a transparent forecasting baseline."
        ),
        "required_fields": ["outcome", "time"],
        "requires_panel": False,
    },
    "exp_smoothing": {
        "question_type": "forecast",
        "display_name": "Simple exponential smoothing",
        "description": (
            "Level-based exponential smoothing for short or noisy series. "
            "Uses statsmodels when available and a grid-search fallback otherwise."
        ),
        "required_fields": ["outcome", "time"],
        "requires_panel": False,
    },
    "random_walk": {
        "question_type": "forecast",
        "display_name": "Random walk / naive forecast",
        "description": (
            "Carries the last observed value forward, with uncertainty based on "
            "recent first differences. A strong baseline for persistent series."
        ),
        "required_fields": ["outcome", "time"],
        "requires_panel": False,
    },

    # ------------------------------------------------------------------
    # Association / regression (panel)
    # ------------------------------------------------------------------
    "panel_ols": {
        "question_type": "association",
        "display_name": "Panel OLS (Two-Way FE)",
        "description": (
            "Panel regression with unit and time fixed effects via iterative "
            "demeaning. Standard errors clustered at the unit level."
        ),
        "required_fields": ["outcome", "treatment", "unit", "time"],
        "requires_panel": True,
        "requires_treatment_variation": True,
    },
    "entity_fe": {
        "question_type": "association",
        "display_name": "Entity fixed effects",
        "description": (
            "Within-unit estimator that controls for time-invariant unit-level "
            "confounders, with unit-clustered standard errors."
        ),
        "required_fields": ["outcome", "treatment", "unit"],
        "requires_panel": False,
        "requires_treatment_variation": True,
    },
    "time_fe": {
        "question_type": "association",
        "display_name": "Time fixed effects",
        "description": (
            "Regression after absorbing common time shocks. Useful when units "
            "share period-specific macro shocks."
        ),
        "required_fields": ["outcome", "treatment", "time"],
        "requires_panel": False,
    },
    "first_difference": {
        "question_type": "association",
        "display_name": "First-difference regression",
        "description": (
            "Regresses within-unit changes in the outcome on within-unit changes "
            "in the predictor, removing unit-level fixed factors."
        ),
        "required_fields": ["outcome", "treatment", "unit", "time"],
        "requires_panel": True,
    },

    # ------------------------------------------------------------------
    # Association / regression (cross-section)
    # ------------------------------------------------------------------
    "ols": {
        "question_type": "association",
        "display_name": "OLS (cross-sectional)",
        "description": (
            "Simple bivariate OLS with HC1 heteroscedasticity-robust SEs. "
            "Used when the dataset has no panel structure."
        ),
        "required_fields": ["outcome", "treatment"],
        "requires_panel": False,
    },
    "pooled_ols": {
        "question_type": "association",
        "display_name": "Pooled OLS",
        "description": (
            "OLS over all rows with HC1 robust standard errors. Useful for "
            "panel data when fixed effects are not desired."
        ),
        "required_fields": ["outcome", "treatment"],
        "requires_panel": False,
    },
    "log_linear": {
        "question_type": "association",
        "display_name": "Log-linear regression",
        "description": (
            "Semi-elasticity model log(y) = alpha + beta*x. Requires a strictly "
            "positive outcome."
        ),
        "required_fields": ["outcome", "treatment"],
        "requires_panel": False,
        "requires_positive_outcome": True,
    },
    "log_log": {
        "question_type": "association",
        "display_name": "Log-log regression",
        "description": (
            "Elasticity model log(y) = alpha + beta*log(x). Requires strictly "
            "positive outcome and predictor values."
        ),
        "required_fields": ["outcome", "treatment"],
        "requires_panel": False,
        "requires_positive_outcome": True,
        "requires_positive_treatment": True,
    },
    "polynomial_ols": {
        "question_type": "association",
        "display_name": "Quadratic / polynomial OLS",
        "description": (
            "Quadratic regression y = alpha + beta*x + gamma*x^2 with HC1 robust "
            "standard errors and a marginal effect at the mean of x."
        ),
        "required_fields": ["outcome", "treatment"],
        "requires_panel": False,
    },
    "median_quantile": {
        "question_type": "association",
        "display_name": "Median quantile regression",
        "description": (
            "LAD/median regression that estimates the conditional median instead "
            "of the conditional mean. More robust to outcome outliers."
        ),
        "required_fields": ["outcome", "treatment"],
        "requires_panel": False,
    },
}

# Maps each question type to the ordered list of candidate models.
# Models listed first are preferred when multiple are admissible.
QUESTION_MODEL_MAP = {
    "causal_effect": ["diff_in_diff"],
    "forecast":      ["arima", "linear_trend", "exp_smoothing", "random_walk"],
    "association":   [
        "panel_ols",
        "entity_fe",
        "time_fe",
        "first_difference",
        "ols",
        "pooled_ols",
        "log_linear",
        "log_log",
        "polynomial_ols",
        "median_quantile",
    ],
}
