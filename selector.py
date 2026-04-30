"""
Model selector for Espresso.

Given a parsed intent and a loaded dataframe, returns:
  valid    : list of admissible model names, ordered by preference
  rejected : dict of {model_name: reason_string} for failed checks
"""

import pandas as pd

from data_utils import is_panel_data, treatment_varies
from model_specs import MODEL_SPECS, QUESTION_MODEL_MAP


def select_admissible_models(intent, data):
    """
    Filter candidate models for the given intent and dataset.

    Checks:
      1. Required intent fields are present.
      2. Panel structure exists when required.
      3. Treatment varies within units when required.
      4. Strict positivity holds for log models.

    Returns:
        valid: list[str] where the first entry is the recommended model.
        rejected: dict[str, str] explaining why a model could not run.
    """
    question_type = intent.get("question_type")
    if question_type not in QUESTION_MODEL_MAP:
        return [], {"error": f"Unknown question type: '{question_type}'"}

    candidates = QUESTION_MODEL_MAP[question_type]
    valid = []
    rejected = {}

    for model in candidates:
        spec = MODEL_SPECS[model]

        missing = [field for field in spec["required_fields"] if intent.get(field) is None]
        if missing:
            rejected[model] = f"Missing required fields: {', '.join(missing)}"
            continue

        if spec.get("requires_panel"):
            if not is_panel_data(data, intent.get("unit"), intent.get("time")):
                rejected[model] = (
                    "Panel structure required but not found "
                    f"(need unit='{intent.get('unit')}' and time='{intent.get('time')}')"
                )
                continue

        if spec.get("requires_treatment_variation"):
            if not treatment_varies(data, intent.get("treatment"), intent.get("unit")):
                rejected[model] = (
                    f"Predictor '{intent.get('treatment')}' does not vary within units"
                )
                continue

        outcome = intent.get("outcome")
        treatment = intent.get("treatment")
        if spec.get("requires_positive_outcome"):
            y = pd.to_numeric(data[outcome], errors="coerce").dropna()
            if y.empty or (y <= 0).any():
                rejected[model] = f"Outcome '{outcome}' must be strictly positive"
                continue

        if spec.get("requires_positive_treatment"):
            x = pd.to_numeric(data[treatment], errors="coerce").dropna()
            if x.empty or (x <= 0).any():
                rejected[model] = f"Predictor '{treatment}' must be strictly positive"
                continue

        valid.append(model)

    return valid, rejected
