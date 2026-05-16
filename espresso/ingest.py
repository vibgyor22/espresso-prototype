"""
Multi-format data ingest.

Accepts .csv / .tsv / .xlsx / .xls / .parquet. For Excel files with multiple
sheets, returns a sentinel so the agent can ask the user which sheet to load.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


CSV_EXTS = {".csv"}
TSV_EXTS = {".tsv", ".tab"}
EXCEL_EXTS = {".xlsx", ".xls", ".xlsm"}
PARQUET_EXTS = {".parquet", ".pq"}


@dataclass
class IngestResult:
    """What `load()` returns."""

    df: Optional[pd.DataFrame] = None
    source_path: str = ""
    format: str = ""               # "csv" | "tsv" | "excel" | "parquet"
    sheet: Optional[str] = None    # Excel only
    available_sheets: list = field(default_factory=list)
    needs_sheet_choice: bool = False
    error: Optional[str] = None

    def ok(self) -> bool:
        return self.df is not None and self.error is None


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _parse_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Auto-convert string columns that look like dates to datetime dtype."""
    import re
    date_pattern = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}")
    for col in df.select_dtypes(include=["object", "string"]).columns:
        sample = df[col].dropna().astype(str).head(5)
        if sample.empty:
            continue
        if sample.str.match(date_pattern).mean() >= 0.8:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass
    return df


def detect_format(path: str) -> str:
    ext = _ext(path)
    if ext in CSV_EXTS:
        return "csv"
    if ext in TSV_EXTS:
        return "tsv"
    if ext in EXCEL_EXTS:
        return "excel"
    if ext in PARQUET_EXTS:
        return "parquet"
    return "unknown"


def list_excel_sheets(path: str) -> list[str]:
    """List sheet names; explicitly closes the file handle so callers can
    delete or overwrite the file immediately afterwards (Windows-friendly)."""
    xf = pd.ExcelFile(path)
    try:
        return list(xf.sheet_names)
    finally:
        try:
            xf.close()
        except Exception:
            pass


def load(path: str, sheet: Optional[str | int] = None, **read_kwargs: Any) -> IngestResult:
    """
    Load a file and return an IngestResult.

    For Excel files with multiple sheets and no `sheet` argument, the result
    sets `needs_sheet_choice=True` and lists `available_sheets` so the caller
    (the agent) can ask the user which sheet to use.
    """
    if not os.path.exists(path):
        return IngestResult(source_path=path, error=f"File not found: {path}")

    fmt = detect_format(path)
    if fmt == "unknown":
        return IngestResult(
            source_path=path,
            error=(
                f"Unsupported file type '{_ext(path)}'. "
                "Supported: .csv, .tsv, .xlsx, .xls, .parquet"
            ),
        )

    try:
        if fmt == "csv":
            df = pd.read_csv(path, **read_kwargs)
            df = _parse_date_columns(df)
            return IngestResult(df=df, source_path=path, format=fmt)

        if fmt == "tsv":
            df = pd.read_csv(path, sep="\t", **read_kwargs)
            df = _parse_date_columns(df)
            return IngestResult(df=df, source_path=path, format=fmt)

        if fmt == "parquet":
            df = pd.read_parquet(path, **read_kwargs)
            return IngestResult(df=df, source_path=path, format=fmt)

        # Excel
        sheets = list_excel_sheets(path)
        if sheet is None and len(sheets) > 1:
            return IngestResult(
                source_path=path,
                format=fmt,
                available_sheets=sheets,
                needs_sheet_choice=True,
            )
        chosen = sheet if sheet is not None else sheets[0]
        df = pd.read_excel(path, sheet_name=chosen, **read_kwargs)
        return IngestResult(
            df=df,
            source_path=path,
            format=fmt,
            sheet=str(chosen),
            available_sheets=sheets,
        )

    except Exception as e:
        return IngestResult(source_path=path, format=fmt, error=str(e))


# Convenience for `from espresso.ingest import load_data`
load_data = load
