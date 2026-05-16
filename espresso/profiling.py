"""
Automatic data profiling.

Produces a structured summary the agent and the user can both read:
  - per-column: dtype, semantic type, n_unique, missing, basic stats
  - dataset-level: shape, panel/cross-section/time-series classification,
    candidate unit / time / outcome columns

The profile is injected into the LLM context so column mapping is grounded in
dtypes and ranges, not just a handful of sample values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import numpy as np
import pandas as pd


# Semantic types used downstream for model selection and clarification prompts.
SEM_NUMERIC = "numeric"
SEM_INTEGER = "integer"
SEM_CATEGORICAL = "categorical"
SEM_BOOLEAN = "boolean"
SEM_DATETIME = "datetime"
SEM_IDENTIFIER = "identifier"
SEM_TEXT = "text"
SEM_YEAR = "year"


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    semantic_type: str
    n_unique: int
    n_missing: int
    missing_pct: float
    sample_values: list = field(default_factory=list)
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    top_values: list = field(default_factory=list)   # categorical
    inferred_unit: Optional[str] = None              # "USD", "%", "year", ...

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DataProfile:
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    structure: str                       # "panel" | "time_series" | "cross_section" | "wide_indicator"
    candidate_unit_cols: list[str]
    candidate_time_cols: list[str]
    candidate_outcome_cols: list[str]
    candidate_treatment_cols: list[str]
    indicator_column: Optional[str] = None
    year_columns: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["columns"] = [c.to_dict() if isinstance(c, ColumnProfile) else c for c in self.columns]
        return d

    def column(self, name: str) -> Optional[ColumnProfile]:
        for c in self.columns:
            if c.name == name:
                return c
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YEAR_MIN, _YEAR_MAX = 1800, 2100


def _is_year_value(v: Any) -> bool:
    try:
        f = float(v)
        if not math.isfinite(f):
            return False
        i = int(f)
        return i == f and _YEAR_MIN <= i <= _YEAR_MAX
    except Exception:
        return False


def _is_year_label(label: Any) -> bool:
    try:
        i = int(str(label).strip())
        return _YEAR_MIN <= i <= _YEAR_MAX
    except Exception:
        return False


def _looks_identifier(series: pd.Series) -> bool:
    n_unique = series.nunique(dropna=True)
    n = len(series.dropna())
    if n == 0:
        return False
    return n_unique == n and n > 5


def _infer_unit_hint(name: str, series: pd.Series) -> Optional[str]:
    lower = name.lower()
    hints = {
        "year": "year", "yr": "year", "date": "date",
        "usd": "USD", "gdp": "currency",
        "pct": "%", "percent": "%", "rate": "%",
        "count": "count", "n_": "count",
    }
    for k, v in hints.items():
        if k in lower:
            return v
    return None


def _is_numpy_dtype(dtype, kind) -> bool:
    """Safe wrapper around np.issubdtype that tolerates pandas extension dtypes."""
    try:
        return np.issubdtype(dtype, kind)
    except (TypeError, ValueError):
        return False


def _looks_like_date_string(series: pd.Series) -> bool:
    """Check if a string column contains ISO-format dates (YYYY-MM-DD etc.)."""
    try:
        sample = series.dropna().astype(str).head(10)
        if sample.empty:
            return False
        parsed = pd.to_datetime(sample, errors="coerce")
        return parsed.notna().mean() >= 0.8
    except Exception:
        return False


def _semantic_type(name: str, series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return SEM_TEXT

    # datetime (numpy datetime or pandas extension)
    if pd.api.types.is_datetime64_any_dtype(series):
        return SEM_DATETIME

    # date-like strings: try parsing before treating as identifier/text
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        if _looks_like_date_string(series):
            return SEM_DATETIME

    # boolean
    uniques = set(map(str, s.unique()[:10]))
    if uniques.issubset({"True", "False", "true", "false", "0", "1", "0.0", "1.0"}) and s.nunique() <= 2:
        return SEM_BOOLEAN

    # year column (label or values look like years and few unique)
    if _is_year_label(name) or (s.apply(_is_year_value).all() and s.nunique() <= 200):
        return SEM_YEAR

    # numeric (use pandas API so extension dtypes work)
    if pd.api.types.is_numeric_dtype(series):
        if pd.api.types.is_integer_dtype(series) and s.nunique() <= 30:
            return SEM_CATEGORICAL  # encoded categorical
        if pd.api.types.is_integer_dtype(series):
            return SEM_INTEGER
        return SEM_NUMERIC

    # categorical / id / text by cardinality
    n_unique = s.nunique()
    if _looks_identifier(series):
        return SEM_IDENTIFIER
    if n_unique <= max(50, int(0.05 * len(series))):
        return SEM_CATEGORICAL
    return SEM_TEXT


def _column_profile(name: str, series: pd.Series, sample_n: int = 5) -> ColumnProfile:
    n_missing = int(series.isna().sum())
    n = len(series)
    n_unique = int(series.nunique(dropna=True))
    sample = series.dropna().astype(str).unique().tolist()[:sample_n]

    cp = ColumnProfile(
        name=str(name),
        dtype=str(series.dtype),
        semantic_type=_semantic_type(name, series),
        n_unique=n_unique,
        n_missing=n_missing,
        missing_pct=(n_missing / n * 100.0) if n else 0.0,
        sample_values=sample,
        inferred_unit=_infer_unit_hint(str(name), series),
    )

    if cp.semantic_type in (SEM_NUMERIC, SEM_INTEGER, SEM_YEAR):
        s_num = pd.to_numeric(series, errors="coerce").dropna()
        if not s_num.empty:
            cp.min = float(s_num.min())
            cp.max = float(s_num.max())
            cp.mean = float(s_num.mean())
            cp.std = float(s_num.std()) if len(s_num) > 1 else 0.0

    if cp.semantic_type in (SEM_CATEGORICAL, SEM_BOOLEAN):
        vc = series.dropna().astype(str).value_counts().head(5)
        cp.top_values = [{"value": k, "count": int(v)} for k, v in vc.items()]

    return cp


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def profile(df: pd.DataFrame) -> DataProfile:
    """Build a DataProfile for the given dataframe."""
    columns = [_column_profile(name, df[name]) for name in df.columns]

    candidate_time_cols: list[str] = []
    candidate_unit_cols: list[str] = []
    candidate_outcome_cols: list[str] = []
    candidate_treatment_cols: list[str] = []
    year_columns: list[str] = []
    indicator_column: Optional[str] = None
    notes: list[str] = []

    for c in columns:
        if c.semantic_type in (SEM_DATETIME, SEM_YEAR):
            candidate_time_cols.append(c.name)
        if c.semantic_type == SEM_YEAR and _is_year_label(c.name):
            year_columns.append(c.name)
        if c.semantic_type in (SEM_CATEGORICAL, SEM_IDENTIFIER) and c.n_unique > 1:
            candidate_unit_cols.append(c.name)
        if c.semantic_type in (SEM_NUMERIC, SEM_INTEGER) and c.missing_pct < 50:
            # outcome candidates: continuous numeric, varies
            if c.std and c.std > 0:
                candidate_outcome_cols.append(c.name)
            # treatment candidates: numeric or binary
            candidate_treatment_cols.append(c.name)
        if c.semantic_type == SEM_BOOLEAN:
            candidate_treatment_cols.append(c.name)

    # Detect indicator-style wide datasets
    if year_columns:
        for c in columns:
            if c.semantic_type in (SEM_CATEGORICAL, SEM_TEXT, SEM_IDENTIFIER):
                lower = c.name.lower()
                if any(tok in lower for tok in ("indicator", "series", "metric", "name")):
                    indicator_column = c.name
                    break
        notes.append(
            f"Wide-format with {len(year_columns)} year columns; "
            "will need a pivot to long format before analysis."
        )

    # Classify structure
    has_time = bool(candidate_time_cols) or bool(year_columns)
    has_unit = bool(candidate_unit_cols)
    if year_columns and indicator_column:
        structure = "wide_indicator"
    elif has_time and has_unit:
        structure = "panel"
    elif has_time and not has_unit:
        structure = "time_series"
    else:
        structure = "cross_section"

    if df.shape[0] < 20:
        notes.append("Small sample (<20 rows) — statistical power will be limited.")

    return DataProfile(
        n_rows=int(df.shape[0]),
        n_cols=int(df.shape[1]),
        columns=columns,
        structure=structure,
        candidate_unit_cols=candidate_unit_cols,
        candidate_time_cols=candidate_time_cols,
        candidate_outcome_cols=candidate_outcome_cols,
        candidate_treatment_cols=candidate_treatment_cols,
        indicator_column=indicator_column,
        year_columns=year_columns,
        notes=notes,
    )


def summary_for_llm(p: DataProfile, max_cols: int = 50) -> str:
    """Compact, LLM-friendly textual summary of the profile."""
    lines = [
        f"Dataset: {p.n_rows:,} rows × {p.n_cols} columns",
        f"Structure: {p.structure}",
    ]
    if p.indicator_column:
        lines.append(f"Indicator column: {p.indicator_column}")
    if p.year_columns:
        lines.append(f"Year columns: {len(p.year_columns)} ({p.year_columns[:3]} ... )")
    if p.candidate_unit_cols:
        lines.append(f"Candidate unit columns: {p.candidate_unit_cols[:8]}")
    if p.candidate_time_cols:
        lines.append(f"Candidate time columns: {p.candidate_time_cols[:8]}")
    if p.candidate_outcome_cols:
        lines.append(f"Candidate numeric outcomes: {p.candidate_outcome_cols[:10]}")

    lines.append("Columns:")
    for c in p.columns[:max_cols]:
        bits = [f"{c.name}({c.semantic_type})"]
        if c.min is not None and c.max is not None:
            bits.append(f"range=[{c.min:.4g},{c.max:.4g}]")
        if c.missing_pct > 0:
            bits.append(f"missing={c.missing_pct:.1f}%")
        if c.sample_values:
            bits.append(f"e.g. {c.sample_values[:3]}")
        lines.append("  - " + " ".join(bits))
    if p.notes:
        lines.append("Notes: " + "; ".join(p.notes))
    return "\n".join(lines)
