import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

from data_utils import get_year_columns, find_indicator_column


def detect_column_types(df: pd.DataFrame) -> Dict[str, str]:
    """
    Lightweight schema inference for tabular data.

    Returns a mapping of column name -> inferred logical type:
    - 'numeric'
    - 'categorical'
    - 'datetime'
    - 'id'
    - 'text'
    """
    types: Dict[str, str] = {}

    for col in df.columns:
        s = df[col]

        # Datetime-like
        if pd.api.types.is_datetime64_any_dtype(s):
            types[col] = "datetime"
            continue

        # Numeric
        if pd.api.types.is_numeric_dtype(s):
            # Low-cardinality integer columns often behave like IDs
            nunique = s.nunique(dropna=True)
            if pd.api.types.is_integer_dtype(s) and nunique == len(s):
                types[col] = "id"
            else:
                types[col] = "numeric"
            continue

        # Try parsing as datetime
        try:
            parsed = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
            if parsed.notna().mean() > 0.7:
                types[col] = "datetime"
                continue
        except Exception:
            pass

        # Heuristics on object columns
        nunique = s.nunique(dropna=True)
        if nunique == len(s) and len(s) > 20:
            types[col] = "id"
        elif nunique <= 50:
            types[col] = "categorical"
        else:
            types[col] = "text"

    return types


def infer_time_and_unit_columns(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer likely time and unit columns using simple heuristics.

    Time:
      - Prefer datetime-typed columns
      - Fallback to year-like numeric columns (via get_year_columns)
      - Fallback to names containing 'year', 'date', 'time'

    Unit:
      - Common entity names (country, region, state, id, firm, company, etc.)
      - Fallback to first categorical / id-like column that is not time.
    """
    col_types = detect_column_types(df)

    # Time column
    time_col: Optional[str] = None

    # 1) Any datetime typed column
    datetime_cols = [c for c, t in col_types.items() if t == "datetime"]
    if datetime_cols:
        time_col = datetime_cols[0]
    else:
        # 2) Explicit year-like columns
        year_candidates = get_year_columns(df)
        if len(year_candidates) == 1:
            time_col = year_candidates[0]
        else:
            # 3) Name-based heuristics
            for c in df.columns:
                lc = c.lower()
                if any(k in lc for k in ("year", "date", "time", "period")):
                    time_col = c
                    break

    # Unit column
    unit_col: Optional[str] = None
    common_unit_names = [
        "country",
        "region",
        "state",
        "province",
        "id",
        "unit",
        "entity",
        "firm",
        "company",
        "sector",
        "group",
        "location",
    ]

    for c in df.columns:
        lc = c.lower()
        if lc in common_unit_names or any(
            lc.endswith(suffix) for suffix in ("_id", "_code")
        ):
            unit_col = c
            break

    if unit_col is None:
        # Fallback: first categorical/id column that is not time and not indicator
        indicator_col = find_indicator_column(df)
        for c, t in col_types.items():
            if c == time_col or c == indicator_col:
                continue
            if t in ("categorical", "id"):
                unit_col = c
                break

    return time_col, unit_col


def summarize_dataframe(
    df: pd.DataFrame, max_sample_values: int = 5
) -> Dict[str, Any]:
    """
    Produce a JSON-friendly summary of the dataset:
    - shape
    - column types
    - missingness
    - basic statistics
    - example values
    - inferred time/unit/indicator structure
    """
    col_types = detect_column_types(df)
    time_col, unit_col = infer_time_and_unit_columns(df)
    indicator_col = find_indicator_column(df)

    columns: Dict[str, Any] = {}
    for col in df.columns:
        s = df[col]
        non_null = s.notna().sum()
        missing = len(s) - non_null
        missing_pct = float(missing) / len(s) if len(s) else 0.0

        summary: Dict[str, Any] = {
            "type": col_types.get(col, "unknown"),
            "non_null": int(non_null),
            "missing": int(missing),
            "missing_pct": missing_pct,
        }

        # Basic stats for numeric columns
        if col_types.get(col) == "numeric":
            desc = s.describe(percentiles=[0.25, 0.5, 0.75])
            summary["min"] = float(desc.get("min", float("nan")))
            summary["max"] = float(desc.get("max", float("nan")))
            summary["mean"] = float(desc.get("mean", float("nan")))
            summary["std"] = float(desc.get("std", float("nan")))
        else:
            # Example values
            unique_vals = s.dropna().astype(str).unique().tolist()
            summary["example_values"] = unique_vals[:max_sample_values]

        columns[col] = summary

    info: Dict[str, Any] = {
        "n_rows": int(len(df)),
        "n_columns": int(len(df.columns)),
        "columns": columns,
        "inferred_time_column": time_col,
        "inferred_unit_column": unit_col,
        "inferred_indicator_column": indicator_col,
        "year_like_columns": get_year_columns(df),
    }

    return info


def validate_panel_structure(
    df: pd.DataFrame,
    time_col: Optional[str],
    unit_col: Optional[str],
) -> Dict[str, Any]:
    """
    Run simple structural checks for panel / time-series data:
    - time sortedness
    - time gaps
    - balanced vs unbalanced panel
    """
    results: Dict[str, Any] = {
        "has_time_column": bool(time_col and time_col in df.columns),
        "has_unit_column": bool(unit_col and unit_col in df.columns),
        "is_panel": False,
        "is_balanced_panel": None,
        "time_gaps_detected": None,
        "notes": [],
    }

    if not time_col or time_col not in df.columns:
        results["notes"].append("No valid time column detected.")
        return results

    if unit_col and unit_col in df.columns:
        results["is_panel"] = True

    # Work on a copy with numeric time index if possible
    s_time = pd.to_numeric(df[time_col], errors="coerce")
    if s_time.isna().all():
        results["notes"].append("Time column is not numeric; skipping gap checks.")
        return results

    # Time gaps (overall)
    sorted_times = sorted(set(s_time.dropna().tolist()))
    if len(sorted_times) >= 2:
        diffs = [b - a for a, b in zip(sorted_times[:-1], sorted_times[1:])]
        min_step = min(diffs)
        if min_step <= 0:
            results["notes"].append("Non-increasing time values detected.")
        else:
            expected_times = list(range(sorted_times[0], sorted_times[-1] + min_step, min_step))
            missing_times = sorted(set(expected_times) - set(sorted_times))
            results["time_gaps_detected"] = bool(missing_times)
            if missing_times:
                results["notes"].append(
                    f"Missing {len(missing_times)} time points between "
                    f"{sorted_times[0]} and {sorted_times[-1]}."
                )

    if unit_col and unit_col in df.columns:
        # Balanced vs unbalanced: each unit should have same number of time observations
        counts = (
            df[[unit_col, time_col]]
            .dropna()
            .groupby(unit_col)[time_col]
            .nunique()
        )
        if not counts.empty:
            results["is_balanced_panel"] = counts.nunique() == 1
            if results["is_balanced_panel"]:
                results["notes"].append(
                    f"Balanced panel detected with {int(counts.iloc[0])} time periods per unit."
                )
            else:
                results["notes"].append(
                    "Unbalanced panel: units have differing numbers of time periods."
                )

    return results


def run_data_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """
    High-level entry point: returns both schema summary and structural checks.
    Intended to be called by the API / console to quickly describe a dataset.
    """
    summary = summarize_dataframe(df)
    time_col = summary.get("inferred_time_column")
    unit_col = summary.get("inferred_unit_column")
    structure = validate_panel_structure(df, time_col=time_col, unit_col=unit_col)

    return {
        "summary": summary,
        "structure": structure,
    }

