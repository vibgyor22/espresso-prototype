"""Espresso visualization layer: terminal (default) and HTML (on demand)."""

from .terminal import (
    console,
    render_profile,
    render_diagnostics,
    render_forecast,
    render_regression,
    render_interpretation,
    render_tool_call,
    render_header,
    render_followups,
)
from .html_report import create_html_report

__all__ = [
    "console",
    "render_profile",
    "render_diagnostics",
    "render_forecast",
    "render_regression",
    "render_interpretation",
    "render_tool_call",
    "render_header",
    "render_followups",
    "create_html_report",
]
