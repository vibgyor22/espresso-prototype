"""
Tests for espresso.ingest: format detection, CSV/TSV/XLSX/Parquet round-trip,
Excel sheet picking.
"""

from __future__ import annotations

import os
import tempfile

import pandas as pd

from espresso.ingest import load, detect_format, IngestResult


def _fixture_df():
    return pd.DataFrame({
        "country": ["USA", "UK", "DE", "USA", "UK", "DE"],
        "year":    [2020, 2020, 2020, 2021, 2021, 2021],
        "value":   [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    })


def test_detect_format():
    assert detect_format("a.csv") == "csv"
    assert detect_format("a.tsv") == "tsv"
    assert detect_format("a.xlsx") == "excel"
    assert detect_format("a.parquet") == "parquet"
    assert detect_format("a.json") == "unknown"


def test_load_missing_file():
    res = load("/no/such/file.csv")
    assert isinstance(res, IngestResult)
    assert not res.ok()
    assert "not found" in (res.error or "").lower()


def test_load_csv_roundtrip():
    df = _fixture_df()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.csv")
        df.to_csv(p, index=False)
        res = load(p)
        assert res.ok()
        assert res.format == "csv"
        assert len(res.df) == len(df)
        assert list(res.df.columns) == list(df.columns)


def test_load_tsv_roundtrip():
    df = _fixture_df()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.tsv")
        df.to_csv(p, index=False, sep="\t")
        res = load(p)
        assert res.ok()
        assert res.format == "tsv"
        assert len(res.df) == len(df)


def test_load_xlsx_single_sheet():
    df = _fixture_df()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.xlsx")
        df.to_excel(p, index=False, sheet_name="only")
        res = load(p)
        assert res.ok()
        assert res.format == "excel"
        assert res.sheet == "only"
        assert len(res.df) == len(df)


def test_load_xlsx_multi_sheet_needs_choice():
    df = _fixture_df()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.xlsx")
        with pd.ExcelWriter(p) as w:
            df.to_excel(w, sheet_name="A", index=False)
            df.iloc[:3].to_excel(w, sheet_name="B", index=False)
        res = load(p)
        assert res.needs_sheet_choice is True
        assert set(res.available_sheets) == {"A", "B"}
        # And we can pick one
        res2 = load(p, sheet="B")
        assert res2.ok()
        assert len(res2.df) == 3
        assert res2.sheet == "B"


def test_load_unsupported_extension():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.json")
        with open(p, "w") as f:
            f.write("{}")
        res = load(p)
        assert not res.ok()
        assert "unsupported" in (res.error or "").lower()
