# This defines what each statistical model needs to work

MODEL_SPECS = {
    "diff_in_diff": {
        "question_type": "causal_effect",
        "required_fields": ["outcome", "treatment", "unit", "time"],
        "requires_panel": True,
        "requires_treatment_variation": True
    },
    "arima": {
        "question_type": "forecast",
        "required_fields": ["outcome", "time"],
        "requires_panel": False
    }
}

# This maps question types to possible models
QUESTION_MODEL_MAP = {
    "causal_effect": ["diff_in_diff"],
    "forecast": ["arima"]
}
