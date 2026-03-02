from pathlib import Path
from typing import Dict, List, Any


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


# Curated bundled datasets for the prototype console and demos.
# These wrap the existing CSVs already in the repo.
BUNDLED_DATASETS: Dict[str, Dict[str, Any]] = {
    "policy_example": {
        "id": "policy_example",
        "name": "Policy Evaluation (DiD) Toy Dataset",
        "path": str(DATA_DIR / "test_causal.csv"),
        "description": "Small panel-style dataset suitable for difference-in-differences examples.",
        "recommended_question": "Did the treatment reduce the outcome?",
        "dataset_type": "panel_causal",
    },
    "panel_forecast_example": {
        "id": "panel_forecast_example",
        "name": "Panel Time Series Toy Dataset",
        "path": str(DATA_DIR / "test_panel.csv"),
        "description": "Toy panel time series dataset for simple AR(1) forecasts.",
        "recommended_question": "What will the outcome be over the next 10 years?",
        "dataset_type": "panel_forecast",
    },
    "imf_macro_example": {
        "id": "imf_macro_example",
        "name": "IMF Macroeconomic Dataset (Sample)",
        "path": str(
            DATA_DIR
            / "dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv"
        ),
        "description": "Richer macroeconomic panel data from IMF integration for more realistic demos.",
        "recommended_question": "What is the effect of raising interest rates on unemployment in the Eurozone?",
        "dataset_type": "macro_panel",
    },
}


def list_bundled_datasets() -> List[Dict[str, Any]]:
    """
    Return bundled datasets as a list of JSON-friendly metadata dicts.
    Intended for use by the API / console when listing available demo datasets.
    """
    return list(BUNDLED_DATASETS.values())


def get_dataset_metadata(dataset_id: str) -> Dict[str, Any]:
    """
    Get metadata for a given bundled dataset.
    Raises KeyError if not found.
    """
    return BUNDLED_DATASETS[dataset_id]


def get_dataset_path(dataset_id: str) -> str:
    """
    Get on-disk path for a given bundled dataset.
    Raises KeyError if not found.
    """
    return BUNDLED_DATASETS[dataset_id]["path"]


