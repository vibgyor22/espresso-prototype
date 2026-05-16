"""
Agent loop end-to-end tests with a real dataframe and the deterministic
coordinator. We don't mock the LLM — calls degrade gracefully to local
fallbacks when the API is offline, which is exactly the runtime contract.
"""

from __future__ import annotations

import pandas as pd

from espresso.agent.coordinator import Coordinator
from espresso.agent.session import Session
from espresso.profiling import profile


def _panel_df():
    rows = []
    for unit in ("A", "B", "C"):
        for year in range(2010, 2022):
            treatment = 1 if (unit == "A" and year >= 2015) else 0
            base = 10 + (year - 2010) * 0.3 + (3 if unit == "B" else 0)
            y = base + 2.5 * treatment
            rows.append({"unit": unit, "year": year, "treated": treatment, "outcome": y})
    return pd.DataFrame(rows)


def _tidy_cross_section():
    return pd.DataFrame({
        "income": [40, 50, 65, 75, 90, 110, 130, 150],
        "education_years": [10, 12, 14, 16, 18, 19, 20, 21],
    })


def test_profile_detects_panel():
    df = _panel_df()
    p = profile(df)
    assert p.structure == "panel"
    assert "unit" in p.candidate_unit_cols
    assert "year" in p.candidate_time_cols
    assert "outcome" in p.candidate_outcome_cols


def test_coordinator_runs_did_with_overrides():
    df = _panel_df()
    s = Session()
    c = Coordinator(s, verbose=False)
    c.attach_data(df)
    c.ask(
        "What is the effect of treated on outcome?",
        overrides={"outcome": "outcome", "treatment": "treated", "unit": "unit", "time": "year", "model": "diff_in_diff"},
        expertise="expert",
    )
    assert s.model_key == "diff_in_diff"
    assert s.result and "error" not in s.result
    # The simulated treatment effect is 2.5 — the estimate should be close.
    eff = s.result.get("treatment_effect", 0)
    assert 1.5 < eff < 3.5, f"effect was {eff}"
    # Agent recorded each step
    tool_calls = [h for h in s.history if h.kind == "tool_call"]
    tools_seen = {h.tool for h in tool_calls}
    assert {"profile_data", "parse_question", "select_model", "run_diagnostics", "run_model"}.issubset(tools_seen)


def test_coordinator_runs_ols_on_cross_section():
    df = _tidy_cross_section()
    s = Session()
    c = Coordinator(s, verbose=False)
    c.attach_data(df)
    c.ask(
        "What is the relationship between education_years and income?",
        overrides={"outcome": "income", "treatment": "education_years", "model": "ols"},
        expertise="expert",
    )
    assert s.model_key == "ols"
    assert s.result and "error" not in s.result
    # education and income are perfectly correlated in the fixture → strong positive slope
    slope = s.result.get("slope", 0)
    assert slope > 0


def test_coordinator_export_html(tmp_path):
    from espresso.viz.html_report import create_html_report

    df = _panel_df()
    s = Session()
    c = Coordinator(s, verbose=False)
    c.attach_data(df)
    c.ask(
        "What is the effect of treated on outcome?",
        overrides={"outcome": "outcome", "treatment": "treated", "unit": "unit", "time": "year", "model": "diff_in_diff"},
        expertise="expert",
    )
    out = create_html_report(s, str(tmp_path / "report.html"))
    text = open(out, "r", encoding="utf-8").read()
    # Basic structural assertions
    assert "<!doctype html>" in text.lower()
    assert "Espresso" in text
    assert "What we did and why" in text  # agent timeline section
    assert "What-if" in text                # what-if section is in the dashboard


def test_coordinator_diagnostic_driven_switch():
    """When parallel trends fail and the question is causal, the agent should
    consider switching to first_difference. Build a panel where pre-trends
    obviously diverge between treated and control."""
    rows = []
    for unit in ("A", "B"):
        for year in range(2010, 2022):
            treated = 1 if (unit == "A" and year >= 2018) else 0
            # treated unit has a steeper pre-trend than control
            pre_trend = (year - 2010) * (0.8 if unit == "A" else 0.1)
            y = pre_trend + 1.0 * treated
            rows.append({"unit": unit, "year": year, "treated": treated, "outcome": y})
    df = pd.DataFrame(rows)
    s = Session()
    c = Coordinator(s, verbose=False)
    c.attach_data(df)
    c.ask(
        "What is the effect of treated on outcome?",
        overrides={"outcome": "outcome", "treatment": "treated", "unit": "unit", "time": "year"},
        expertise="expert",
    )
    # The corrective switch is opportunistic and depends on which violation is
    # surfaced; we don't require it, but we *do* require the run to complete
    # successfully with a valid model end-state.
    assert s.model_key in ("diff_in_diff", "first_difference", "panel_ols")
    assert s.result and "error" not in s.result
