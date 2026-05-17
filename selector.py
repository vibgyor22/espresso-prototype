"""
Model selector for Espresso.

Given a parsed intent and a loaded dataframe, returns:
  valid    : list of admissible model names, ordered by preference
  rejected : dict of {model_name: reason_string} for failed checks
"""

import pandas as pd

from data_utils import is_panel_data, treatment_varies
from model_specs import MODEL_SPECS, QUESTION_MODEL_MAP


def _scalar_intent(val):
    """Return primary element if val is a list (multi-predictor LLM response), else val."""
    if isinstance(val, list):
        return val[0] if val else None
    return val


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

        # Reject if required columns are missing from the data
        missing_fields = [field for field in spec["required_fields"] if intent.get(field) is None]
        if missing_fields:
            rejected[model] = f"Missing required fields: {', '.join(missing_fields)}"
            continue
        missing_cols = [
            f for f in ("outcome", "treatment", "unit", "time")
            if f in spec["required_fields"]
            and intent.get(f) is not None
            and _scalar_intent(intent[f]) not in data.columns
        ]
        if missing_cols:
            bad = {f: _scalar_intent(intent[f]) for f in missing_cols}
            rejected[model] = f"Columns not in data: {bad}"
            continue

        if spec.get("requires_panel"):
            if not is_panel_data(data, intent.get("unit"), intent.get("time")):
                rejected[model] = (
                    "Panel structure required but not found "
                    f"(need unit='{intent.get('unit')}' and time='{intent.get('time')}')"
                )
                continue

        if spec.get("requires_treatment_variation"):
            t_val = _scalar_intent(intent.get("treatment"))
            if not treatment_varies(data, t_val, intent.get("unit")):
                rejected[model] = (
                    f"Predictor '{t_val}' does not vary within units"
                )
                continue

        outcome = intent.get("outcome")
        treatment = _scalar_intent(intent.get("treatment"))
        if spec.get("requires_positive_outcome"):
            if outcome not in data.columns:
                rejected[model] = f"Outcome column '{outcome}' not found in data"
                continue
            y = pd.to_numeric(data[outcome], errors="coerce").dropna()
            if y.empty or (y <= 0).any():
                rejected[model] = f"Outcome '{outcome}' must be strictly positive"
                continue

        if spec.get("requires_positive_treatment"):
            if treatment not in data.columns:
                rejected[model] = f"Predictor column '{treatment}' not found in data"
                continue
            x = pd.to_numeric(data[treatment], errors="coerce").dropna()
            if x.empty or (x <= 0).any():
                rejected[model] = f"Predictor '{treatment}' must be strictly positive"
                continue

        valid.append(model)

    return valid, rejected
