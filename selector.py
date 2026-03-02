from model_specs import MODEL_SPECS, QUESTION_MODEL_MAP
from data_utils import is_panel_data, treatment_varies

def select_admissible_models(intent, data):
    """
    This is the brain of Espresso. It decides which statistical
    models are valid for your question and data.
    
    Returns:
    - valid: list of models that can be used
    - rejected: dictionary of models that can't be used and why
    """
    
    # Get the type of question (causal or forecast)
    question_type = intent.get("question_type")
    if question_type not in QUESTION_MODEL_MAP:
        return [], {"error": "Unknown question type"}
    
    # Get all models that could work for this type of question
    candidates = QUESTION_MODEL_MAP[question_type]
    valid = []
    rejected = {}

    # Check each candidate model
    for model in candidates:
        spec = MODEL_SPECS[model]
        
        # Check 1: Does the question have all required information?
        missing_fields = []
        for field in spec["required_fields"]:
            if intent.get(field) is None:
                missing_fields.append(field)
        
        if missing_fields:
            rejected[model] = f"Missing: {', '.join(missing_fields)}"
            continue
        
        # Check 2: Is the data structure correct?
        if spec.get("requires_panel"):
            if not is_panel_data(data, intent.get("unit"), intent.get("time")):
                rejected[model] = "Need panel data (units over time)"
                continue
        
        # Check 3: Does treatment vary? (for causal questions)
        if spec.get("requires_treatment_variation"):
            if not treatment_varies(data, intent.get("treatment"), intent.get("unit")):
                rejected[model] = "Treatment doesn't vary - can't measure effect"
                continue
        
        # If we got here, this model is valid!
        valid.append(model)
    
    return valid, rejected
