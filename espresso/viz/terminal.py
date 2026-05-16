"""
Rich terminal renderer — Espresso Protocol V3.

V3 upgrades:
  - Cinematic session header with rule dividers
  - ConsoleLog: timestamped tagged log lines (INIT/DATA/MODEL/KEY/DONE)
  - Live equation bar that assembles as pipeline steps complete
  - Key Number Panel after regression result
  - Significance Meter (Unicode block bars)
  - Sparklines in the data profile table
  - ASCII correlation heatmap with named-law callouts
  - Outcome distribution histogram
  - 3-act interpretation narrative (WHAT WE FOUND / WHY / WHAT COULD GO WRONG)
  - Confidence Score composite metric
  - Espresso Verdict panel
  - World events + era breakdown renderers
"""

from __future__ import annotations

import math
import sys
import time
from contextlib import contextmanager
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.progress import Progress, BarColumn, TextColumn
from rich import box

import pandas as pd

console = Console()

# ◈ — Espresso's pixel-diamond mascot.  Inline symbol throughout.
MASCOT = "◈"

# Welcome mascot — abstract geometric block, 3 lines × 7 wide. No face.
MASCOT_ART = """\
  [bold #6F4E37]▄█████▄[/bold #6F4E37]
  [bold #6F4E37]█[/bold #6F4E37] [bold #D4A85A]◆[/bold #D4A85A] [bold #D4A85A]◆[/bold #D4A85A] [bold #6F4E37]█[/bold #6F4E37]
  [bold #6F4E37]▀█████▀[/bold #6F4E37]\
"""

_SPINNER_FRAMES = ["◈", "◉", "◎", "◉"]


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

P = {
    "brand":     "#D4A85A",   # gold — brand, key numbers
    "primary":   "#6F4E37",   # coffee brown — borders, headers
    "accent":    "#C4A882",   # latte — secondary
    "success":   "#6AB08A",   # green — passing, significant
    "warning":   "#F39C12",   # amber — borderline
    "danger":    "#E74C3C",   # red — violated, failed
    "neutral":   "#95A5A6",   # grey — dim
    "world":     "#3498DB",   # blue — world events, historical
    "plain":     "#8A5228",   # walnut — plain English prose
}


# ---------------------------------------------------------------------------
# Equation templates (model key → token list)
# ---------------------------------------------------------------------------

EQUATION_TEMPLATES: dict[str, list[str]] = {
    "diff_in_diff":      ["ŷ_it", "=", "α_i", "+", "β·D_it", "+", "γ·X_it", "+", "δ_t", "+", "ε_it"],
    "panel_ols":         ["ŷ_it", "=", "α_i", "+", "β·X_it", "+", "δ_t",   "+", "ε_it"],
    "entity_fe":         ["ŷ_it", "=", "α_i", "+", "β·X_it", "+", "ε_it"],
    "time_fe":           ["ŷ_it", "=", "β·X_it", "+", "δ_t",  "+", "ε_it"],
    "first_difference":  ["Δŷ_it","=", "α",   "+", "β·ΔX_it","+", "ε_it"],
    "pooled_ols":        ["ŷ_it", "=", "α",   "+", "β·X_it", "+", "ε_it"],
    "ols":               ["ŷ_i",  "=", "α",   "+", "β·X_i",  "+", "ε_i"],
    "log_linear":        ["log(ŷ_i)","=","α",  "+", "β·X_i",  "+", "ε_i"],
    "log_log":           ["log(ŷ_i)","=","α",  "+", "β·log(X_i)","+","ε_i"],
    "polynomial_ols":    ["ŷ_i",  "=", "α",   "+", "β₁·X_i", "+", "β₂·X_i²","+","ε_i"],
    "median_quantile":   ["Q₀.₅(ŷ_i)","=","α","+","β·X_i",  "+", "ε_i"],
    "arima":             ["ŷ_t",  "=", "φ₁·y_(t-1)", "+", "…", "+", "θ_q·ε_(t-q)", "+", "ε_t"],
    "linear_trend":      ["ŷ_t",  "=", "α",   "+", "β·t",    "+", "ε_t"],
    "exp_smoothing":     ["ŷ_t",  "=", "α·y_(t-1)", "+", "(1-α)·ŷ_(t-1)"],
    "random_walk":       ["ŷ_t",  "=", "y_(t-1)", "+", "ε_t"],
}


# ---------------------------------------------------------------------------
# UTF-8 safe plot writer
# ---------------------------------------------------------------------------

def _write_plot(chart_str: str) -> None:
    if not chart_str:
        return
    try:
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(chart_str.encode("utf-8", errors="replace"))
            buf.write(b"\n")
            buf.flush()
        else:
            sys.stdout.write(chart_str + "\n")
            sys.stdout.flush()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Spinner / thinking indicator
# ---------------------------------------------------------------------------

@contextmanager
def thinking(label: str = "thinking…"):
    spinner_text = Text.assemble(
        (f"{MASCOT} ", f"bold {P['brand']}"),
        (label, f"dim italic {P['accent']}"),
    )
    with Live(spinner_text, console=console, transient=True, refresh_per_second=4):
        yield


# ---------------------------------------------------------------------------
# ConsoleLog — timestamped tagged pipeline log
# ---------------------------------------------------------------------------

_TAG_STYLES: dict[str, str] = {
    "INIT":  f"bold {P['brand']}",
    "DATA":  f"bold {P['success']}",
    "XFORM": f"bold {P['success']}",
    "DIAG":  "bold #80A0D0",
    "MODEL": "bold #80A0D0",
    "COEFF": f"bold {P['brand']}",
    "HAC":   f"bold {P['accent']}",
    "KEY":   f"bold white on {P['primary']}",
    "FIT":   f"dim {P['accent']}",
    "DONE":  f"bold {P['success']}",
    "WARN":  f"bold {P['warning']}",
    "ERR":   f"bold {P['danger']}",
    "STEP":  f"dim {P['accent']}",
}


class ConsoleLog:
    """Streams tagged, timestamped computation log lines to the terminal."""

    def __init__(self):
        self._t0 = time.monotonic()

    def emit(self, tag: str, text: str, *, note: str = "") -> None:
        elapsed = time.monotonic() - self._t0
        ts = f"+{elapsed:.2f}s"
        style = _TAG_STYLES.get(tag, "dim")
        tag_markup = f"[{style}][{tag}][/{style}]"
        ts_markup = f"[dim]{ts:>8}[/dim]"

        if tag == "KEY":
            console.print(Rule(style=f"dim {P['primary']}"))
            console.print(f"  {ts_markup}  {tag_markup}  [bold {P['brand']}]{text}[/bold {P['brand']}]")
            console.print(Rule(style=f"dim {P['primary']}"))
        else:
            console.print(f"  {ts_markup}  {tag_markup}  {text}")

        if note:
            console.print(f"             [dim italic {P['plain']}]  ↳ {note}[/dim italic {P['plain']}]")


# ---------------------------------------------------------------------------
# Legacy tool-call renderer (kept for backward compat, now delegates to ConsoleLog)
# ---------------------------------------------------------------------------

TOOL_ICONS = {
    "profile_data": "📊",
    "parse_question": "🧭",
    "map_columns": "🔗",
    "prepare_data": "🧹",
    "select_model": "🎯",
    "switch_model": "♻️",
    "run_diagnostics": "🧪",
    "run_model": "🔬",
    "interpret_columns": "📝",
    "interpret_model_choice": "📝",
    "context_interpret": "🌍",
    "suggest_followups": "🪄",
    "clarify": "❓",
    "whatif": "🧮",
    "reframe_question": "↻",
}

_TOOL_TAG_MAP = {
    "profile_data":        "DATA",
    "parse_question":      "INIT",
    "map_columns":         "STEP",
    "prepare_data":        "XFORM",
    "select_model":        "MODEL",
    "switch_model":        "WARN",
    "run_diagnostics":     "DIAG",
    "run_model":           "COEFF",
    "interpret_columns":   "STEP",
    "interpret_model_choice": "STEP",
    "context_interpret":   "STEP",
    "suggest_followups":   "STEP",
    "clarify":             "STEP",
    "reframe_question":    "WARN",
}

_shared_log = ConsoleLog()


def _icon(tool: str) -> str:
    return TOOL_ICONS.get(tool, "🔧")


def _status_tag(status: str) -> str:
    if status == "error":
        return f"[bold {P['danger']}]error[/bold {P['danger']}]"
    if status == "skipped":
        return f"[{P['warning']}]skipped[/{P['warning']}]"
    return f"[{P['success']}]done[/{P['success']}]"


def render_tool_call(step) -> None:
    """Render a step as a tagged console log line."""
    tool = step.tool or "(thought)"
    tag = _TOOL_TAG_MAP.get(tool, "STEP")
    preview = _short(step.result_preview or "", 80)
    note = _short(step.justification or "", 100) if getattr(step, "justification", "") else ""
    status = getattr(step, "status", "ok")
    if status == "error":
        tag = "ERR"
    _shared_log.emit(tag, f"[bold]{tool}[/bold]  [dim]{preview}[/dim]", note=note)


# ---------------------------------------------------------------------------
# Session header (cinematic)
# ---------------------------------------------------------------------------

def render_header(*, question: str, source: str, structure: str) -> None:
    """Cinematic analysis header with brown rule borders."""
    console.print()
    console.print(Rule(style=f"{P['primary']}"))
    console.print(
        f"  [{P['brand']}]{MASCOT}[/{P['brand']}]  "
        f"[bold {P['brand']}]ESPRESSO[/bold {P['brand']}]  "
        f"[dim {P['accent']}]Inference Engine  ·  v3[/dim {P['accent']}]"
    )
    console.print(Rule(style=f"dim {P['primary']}"))
    _label_row("Question", f"[bold]{question}[/bold]")
    src_name = source.split("\\")[-1].split("/")[-1] if source else "(in-memory)"
    _label_row("Dataset ", f"[{P['accent']}]{src_name}[/{P['accent']}]  [dim]·  {structure}[/dim]")
    _label_row("Engine  ", f"[dim {P['accent']}]selecting…[/dim {P['accent']}]")
    console.print(Rule(style=f"dim {P['primary']}"))
    console.print()
    _shared_log.__init__()  # reset timer for this run


def _label_row(label: str, value: str) -> None:
    console.print(f"  [dim {P['accent']}]{label}[/dim {P['accent']}]   {value}")


def render_engine_line(model_display: str) -> None:
    """Print the engine line once the model is known."""
    _label_row("Engine  ", f"[bold {P['brand']}]{model_display}[/bold {P['brand']}]")


def render_equation(model_key: str, outcome: str = "", treatment: str = "", *, step: int = 999) -> None:
    """Print the equation bar, showing tokens revealed up to `step`."""
    tokens = list(EQUATION_TEMPLATES.get(model_key, []))
    if not tokens:
        return
    # Substitute actual column names
    tokens = [t.replace("X_it", f"{treatment}_it").replace("X_i", f"{treatment}_i")
               .replace("X_i²", f"{treatment}_i²").replace("ΔX_it", f"Δ{treatment}_it")
               .replace("log(X_i)", f"log({treatment}_i)")
              if treatment else t for t in tokens]
    tokens = [t.replace("ŷ_it", f"{outcome}_it").replace("ŷ_i", f"{outcome}_i")
               .replace("ŷ_t", f"{outcome}_t").replace("log(ŷ_i)", f"log({outcome}_i)")
              if outcome else t for t in tokens]

    revealed = tokens[:step]
    hidden = tokens[step:]
    parts = []
    for t in revealed:
        if t in ("=", "+", "−"):
            parts.append(f"[dim {P['accent']}] {t} [/dim {P['accent']}]")
        elif t == revealed[-1] and hidden:
            parts.append(f"[bold {P['brand']}]{t}[/bold {P['brand']}]")
        else:
            parts.append(f"[dim]{t}[/dim]")
    if hidden:
        parts.append(f"[dim {P['accent']}] …[/dim {P['accent']}]")

    eq_line = "".join(parts)
    console.print(f"  [dim {P['accent']}]Equation[/dim {P['accent']}]  {eq_line}")


# ---------------------------------------------------------------------------
# Data profile (with sparklines)
# ---------------------------------------------------------------------------

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(series, width: int = 24) -> str:
    try:
        vals = pd.to_numeric(series, errors="coerce").dropna()
        if len(vals) < 2:
            return "─" * width
        lo, hi = float(vals.min()), float(vals.max())
        scale = (hi - lo) if hi > lo else 1.0
        buckets = [int((float(v) - lo) / scale * 7) for v in vals]
        step = max(1, len(buckets) // width)
        sampled = buckets[::step][:width]
        return "".join(SPARK_BLOCKS[min(7, max(0, b))] for b in sampled)
    except Exception:
        return "─" * width


def _short(value, max_len: int = 48) -> str:
    s = str(value).replace("\n", " ").strip()
    return s if len(s) <= max_len else s[: max_len - 1].rstrip() + "…"


def render_profile(profile, *, max_rows: int = 18, df: "Optional[pd.DataFrame]" = None) -> None:
    if profile is None:
        return

    interesting = [c for c in profile.columns if c.missing_pct < 100 and c.n_unique > 1]
    role_priority = {n: 0 for n in (
        profile.candidate_outcome_cols + profile.candidate_unit_cols
        + profile.candidate_time_cols + profile.candidate_treatment_cols
    )}
    interesting.sort(key=lambda c: (role_priority.get(c.name, 1), c.missing_pct))
    shown = interesting[:max_rows]
    hidden = len(profile.columns) - len(shown)

    t = Table(
        title=f"Data  ·  {profile.n_rows:,} rows × {profile.n_cols} cols  ·  {profile.structure}",
        title_style="bold", box=box.SIMPLE, header_style=f"bold {P['primary']}", show_lines=False,
    )
    t.add_column("Column", style="bold", overflow="fold", max_width=22)
    t.add_column("Type", style="dim")
    t.add_column("Unique", justify="right")
    t.add_column("Missing", justify="right")
    t.add_column("Trend", overflow="fold", max_width=26, style=f"dim {P['accent']}")
    t.add_column("Range / sample", overflow="fold", max_width=38)

    for c in shown:
        if c.min is not None and c.max is not None:
            range_str = f"{c.min:.4g} … {c.max:.4g}"
        elif c.top_values:
            range_str = ", ".join(_short(tv["value"], 16) for tv in c.top_values[:3])
        elif c.sample_values:
            range_str = ", ".join(_short(v, 16) for v in c.sample_values[:3])
        else:
            range_str = ""
        miss = f"{c.missing_pct:.0f}%" if c.missing_pct else "—"
        # Sparkline for numeric columns when raw df is available
        spark = ""
        if c.semantic_type in ("numeric", "integer", "year") and df is not None and c.name in df.columns:
            try:
                spark = _sparkline(df[c.name])
            except Exception:
                pass
        t.add_row(_short(c.name, 22), c.semantic_type, f"{c.n_unique:,}", miss, spark, _short(range_str, 38))
    if hidden > 0:
        t.add_row(f"[dim]+ {hidden} more columns[/dim]", "", "", "", "", "")
    console.print(t)

    cand_bits = []
    if profile.candidate_outcome_cols:
        cand_bits.append(f"outcomes [bold]{', '.join(profile.candidate_outcome_cols[:6])}[/bold]")
    if profile.candidate_unit_cols:
        cand_bits.append(f"units [bold]{', '.join(profile.candidate_unit_cols[:4])}[/bold]")
    if profile.candidate_time_cols:
        cand_bits.append(f"time [bold]{', '.join(profile.candidate_time_cols[:3])}[/bold]")
    if cand_bits:
        console.print("[dim]  " + "   ·   ".join(cand_bits) + "[/dim]")
    for note in profile.notes:
        console.print(f"  [yellow]ⓘ[/yellow] [dim]{note}[/dim]")


# ---------------------------------------------------------------------------
# Correlation heatmap
# ---------------------------------------------------------------------------

_KNOWN_LAWS = [
    ({"gdp", "gdp_growth"}, {"unemployment"}, "Okun's Law"),
    ({"inflation", "cpi", "price_level"}, {"unemployment"}, "Phillips Curve"),
    ({"money_supply", "m2"}, {"inflation", "cpi"}, "Quantity Theory"),
    ({"interest_rate", "rate"}, {"inflation", "cpi"}, "Fisher Effect"),
    ({"interest_rate", "ffr", "rate"}, {"gdp", "output"}, "IS Curve"),
]


def _check_known_law(col_a: str, col_b: str) -> Optional[str]:
    a_low = col_a.lower()
    b_low = col_b.lower()
    for set_a, set_b, name in _KNOWN_LAWS:
        match_a = any(k in a_low for k in set_a)
        match_b = any(k in b_low for k in set_b)
        match_ba = any(k in b_low for k in set_a)
        match_ab = any(k in a_low for k in set_b)
        if (match_a and match_b) or (match_ba and match_ab):
            return name
    return None


def render_correlation_heatmap(df: pd.DataFrame, *, max_cols: int = 6) -> None:
    """ASCII correlation matrix for numeric columns."""
    try:
        num_cols = [c for c in df.columns
                    if pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 3][:max_cols]
        if len(num_cols) < 2:
            return
        corr = df[num_cols].corr()

        t = Table(box=box.SIMPLE, header_style=f"bold {P['primary']}", show_lines=False,
                  title="Correlations", title_style="bold")
        t.add_column("", style="dim", max_width=18)
        for c in num_cols:
            t.add_column(_short(c, 10), justify="right", max_width=10)

        for row_c in num_cols:
            vals = []
            for col_c in num_cols:
                r = corr.loc[row_c, col_c]
                if abs(r) > 0.7:
                    color = P["success"] if r > 0 else P["danger"]
                    vals.append(f"[bold {color}]{r:+.2f}[/bold {color}]")
                elif abs(r) > 0.4:
                    vals.append(f"[{P['warning']}]{r:+.2f}[/{P['warning']}]")
                else:
                    vals.append(f"[dim]{r:+.2f}[/dim]")
            t.add_row(_short(row_c, 18), *vals)
        console.print(t)

        # Named law callouts
        strongest = ("", "", 0.0)
        for i, ca in enumerate(num_cols):
            for cb in num_cols[i + 1:]:
                r = abs(corr.loc[ca, cb])
                if r > abs(strongest[2]):
                    strongest = (ca, cb, corr.loc[ca, cb])
        if abs(strongest[2]) >= 0.4:
            law = _check_known_law(strongest[0], strongest[1])
            law_note = f"  — [bold]{law}[/bold] pattern" if law else ""
            console.print(
                f"  [bold {P['world']}]⚡[/bold {P['world']}]  "
                f"[dim]{strongest[0]} ↔ {strongest[1]}: r={strongest[2]:+.2f}{law_note}[/dim]"
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Outcome histogram
# ---------------------------------------------------------------------------

def render_histogram(series, col_name: str = "", *, bins: int = 6) -> None:
    """Simple ASCII histogram for a numeric series."""
    try:
        vals = pd.to_numeric(series, errors="coerce").dropna()
        if len(vals) < 5:
            return
        lo, hi = float(vals.min()), float(vals.max())
        if lo == hi:
            return
        step = (hi - lo) / bins
        counts = [0] * bins
        for v in vals:
            b = min(bins - 1, int((float(v) - lo) / step))
            counts[b] += 1
        max_count = max(counts) or 1
        bar_width = 30

        t = Table(
            title=f"Distribution · {_short(col_name, 28)}  (N={len(vals):,})",
            title_style="bold", box=box.SIMPLE,
            header_style=f"bold {P['primary']}", show_lines=False,
        )
        t.add_column("Range", style="dim", min_width=14)
        t.add_column("Count", justify="right", style=f"dim {P['accent']}")
        t.add_column("", min_width=bar_width)
        for i in range(bins):
            lo_b = lo + i * step
            hi_b = lo_b + step
            filled = int(counts[i] / max_count * bar_width)
            bar = f"[{P['brand']}]{'█' * filled}[/{P['brand']}][dim]{'░' * (bar_width - filled)}[/dim]"
            t.add_row(f"{lo_b:.3g}–{hi_b:.3g}", str(counts[i]), bar)
        console.print(t)

        mean_v = float(vals.mean())
        med_v = float(vals.median())
        try:
            skew_v = float(vals.skew())
            skew_label = "right-skewed" if skew_v > 0.5 else "left-skewed" if skew_v < -0.5 else "approx. normal"
            console.print(f"  [dim]Mean {mean_v:.4g}  ·  Median {med_v:.4g}  ·  Skew {skew_v:+.2f} ({skew_label})[/dim]")
        except Exception:
            console.print(f"  [dim]Mean {mean_v:.4g}  ·  Median {med_v:.4g}[/dim]")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def render_diagnostics(diag: dict, *, model_display: str = "") -> None:
    if not isinstance(diag, dict):
        return
    if "error" in diag:
        console.print(Panel(diag["error"], title="Diagnostics error", border_style=P["danger"]))
        return

    title = "Pre-analysis diagnostics" + (f"  ·  {model_display}" if model_display else "")
    t = Table(title=title, box=box.SIMPLE, header_style=f"bold {P['primary']}",
              title_style="bold", show_lines=False)
    t.add_column("", width=2)
    t.add_column("Check", style="bold")
    t.add_column("Result", overflow="fold", style="dim")
    for check in diag.get("checks", []):
        if "error" in check:
            t.add_row(f"[{P['warning']}]![/{P['warning']}]", check.get("test", "?"), check["error"])
        else:
            ok = not check.get("is_violated")
            mark = f"[{P['success']}]✓[/{P['success']}]" if ok else f"[{P['danger']}]✗[/{P['danger']}]"
            t.add_row(mark, check.get("test", ""), check.get("interpretation", ""))
    console.print(t)
    if diag.get("violations"):
        console.print(f"  [{P['danger']}]●[/{P['danger']}] [dim]Violations: {'; '.join(diag['violations'])}[/dim]")
    if diag.get("corrections"):
        console.print(f"  [cyan]●[/cyan] [dim]Corrections: {'; '.join(diag['corrections'])}[/dim]")


# ---------------------------------------------------------------------------
# Confidence score
# ---------------------------------------------------------------------------

def compute_confidence_score(result: dict, diagnostics: dict, n_obs: int,
                              era_effects: Optional[list] = None) -> dict:
    """Returns dict with score (0-100), components, and label."""
    pval = result.get("pvalue", result.get("p_value", 1.0)) or 1.0
    sig = max(0.0, 40.0 * (1.0 - 8.0 * min(1.0, pval)))

    checks = diagnostics.get("checks", []) if isinstance(diagnostics, dict) else []
    passed = sum(1 for c in checks if not c.get("is_violated", True))
    total = len(checks) or 1
    diag_score = 25.0 * (passed / total)

    samp = 20.0 * min(1.0, math.log(max(1, n_obs)) / math.log(1000))

    era_score = 7.5
    if era_effects and len(era_effects) >= 2:
        estimates = [e.get("estimate", 0.0) for e in era_effects]
        signs = set(1 if v >= 0 else -1 for v in estimates)
        if len(signs) == 1:
            era_score = 15.0
        else:
            max_e = max(abs(v) for v in estimates)
            min_e = min(abs(v) for v in estimates)
            if min_e > 0 and (max_e / min_e) > 3:
                era_score = 0.0

    total_score = round(sig + diag_score + samp + era_score)
    if total_score >= 70:
        label, color, bullet = "High confidence", P["success"], "🟢"
    elif total_score >= 45:
        label, color, bullet = "Moderate confidence", P["warning"], "🟡"
    else:
        label, color, bullet = "Low confidence", P["danger"], "🔴"

    return {
        "score": total_score,
        "sig": round(sig),
        "diag": round(diag_score),
        "samp": round(samp),
        "era": round(era_score),
        "label": label,
        "color": color,
        "bullet": bullet,
    }


def _block_bar(filled: int, total: int = 30, color: str = "") -> str:
    f = min(total, max(0, filled))
    col = color or P["brand"]
    return f"[{col}]{'█' * f}[/{col}][dim]{'░' * (total - f)}[/dim]"


# ---------------------------------------------------------------------------
# Big Key Number Panel
# ---------------------------------------------------------------------------

def render_key_number_panel(result: dict, intent: dict, score: dict) -> None:
    eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    se = result.get("se", 0) or 0
    pval = result.get("pvalue", result.get("p_value", 1)) or 1
    ci_lo = result.get("ci_lower", eff - 1.96 * se)
    ci_hi = result.get("ci_upper", eff + 1.96 * se)
    n = result.get("n_obs", 0)
    outcome = intent.get("outcome", "outcome")
    treatment = intent.get("treatment", "predictor")

    sig_star = "★★★" if pval < 0.001 else "★★" if pval < 0.01 else "★" if pval < 0.05 else "n.s."
    border_col = P["success"] if pval < 0.05 else (P["warning"] if pval < 0.10 else P["neutral"])

    number_line = f"[bold {P['brand']}]{eff:+.4f}[/bold {P['brand']}]"
    ci_line = f"[dim]95% CI  [{ci_lo:.3f},  {ci_hi:.3f}][/dim]"
    p_line = f"[dim]p = {pval:.4f}  {sig_star}   ·   N = {n:,}[/dim]"
    rel_line = f"[dim {P['accent']}]{treatment}  →  {outcome}[/dim {P['accent']}]"
    score_line = (
        f"[{score['color']}]{score['bullet']} {score['label']}  "
        f"{score['score']}/100[/{score['color']}]"
    )

    body = Text.from_markup(
        f"\n   {number_line}\n   {rel_line}\n\n"
        f"   {ci_line}\n   {p_line}\n\n"
        f"   {score_line}\n"
    )
    console.print(Panel(body, border_style=border_col, padding=(0, 2)))


# ---------------------------------------------------------------------------
# Significance Meter
# ---------------------------------------------------------------------------

def render_significance_meter(result: dict, score: dict) -> None:
    eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    se = result.get("se", 0) or 0
    pval = result.get("pvalue", result.get("p_value", 1)) or 1
    ci_lo = result.get("ci_lower", eff - 1.96 * se)
    ci_hi = result.get("ci_upper", eff + 1.96 * se)
    r2 = result.get("r_squared", 0) or 0

    # Effect size label (rough Cohen's d equivalent)
    if abs(eff) == 0:
        strength = "none"
    elif abs(eff) < 0.2 * (abs(ci_hi - ci_lo) / 4 + 0.001):
        strength = "small"
    elif abs(eff) < 0.8 * (abs(ci_hi - ci_lo) / 4 + 0.001):
        strength = "medium"
    else:
        strength = "large"

    # p-value position on 0→1 bar (inverted: low p → high fill)
    p_fill = max(0, int((1.0 - min(1.0, pval)) * 30))
    # CI width fill (wider = less certain)
    ci_width = abs(ci_hi - ci_lo)
    max_ci = max(ci_width, abs(eff) * 2 + 0.001)
    ci_fill = int((1 - ci_width / (max_ci * 2 + 0.001)) * 30)
    # Confidence score fill
    cs_fill = int(score["score"] / 100 * 30)
    # R² fill
    r2_fill = int(r2 * 30)

    p_color = P["success"] if pval < 0.05 else (P["warning"] if pval < 0.10 else P["danger"])

    console.print()
    console.print(f"  [dim {P['accent']}]Significance meter[/dim {P['accent']}]")
    console.print(f"  [dim]Evidence strength  [/dim]{_block_bar(p_fill, 30, p_color)}  [dim]p={pval:.3f}[/dim]")
    console.print(f"  [dim]CI precision       [/dim]{_block_bar(max(0, ci_fill), 30)}  [dim]CI width={ci_width:.3g}[/dim]")
    console.print(f"  [dim]Variance explained [/dim]{_block_bar(r2_fill, 30)}  [dim]R²={r2:.3f}[/dim]")
    console.print(f"  [dim]Confidence score   [/dim]{_block_bar(cs_fill, 30, score['color'])}  [{score['color']}]{score['score']}/100[/{score['color']}]")
    console.print()


# ---------------------------------------------------------------------------
# Forecast renderer
# ---------------------------------------------------------------------------

def render_forecast(model_key: str, result: dict, intent: dict) -> None:
    forecasts = result.get("forecasts", []) or []
    times = result.get("forecast_times", []) or list(range(1, len(forecasts) + 1))
    hist_vals = result.get("historical_values", []) or []
    hist_times = result.get("historical_times", []) or list(range(len(hist_vals)))

    t = Table(title=f"{result.get('model', model_key)} forecast",
              box=box.SIMPLE_HEAVY, header_style="bold", title_style="bold")
    t.add_column("Period", justify="right")
    t.add_column("Forecast", justify="right")
    t.add_column("95% CI", justify="right")
    lo = result.get("ci_lower", []) or []
    hi = result.get("ci_upper", []) or []
    for i, (tt, f) in enumerate(zip(times, forecasts)):
        ci = f"[{lo[i]:.3f}, {hi[i]:.3f}]" if i < len(lo) and i < len(hi) else "—"
        t.add_row(str(tt), f"{f:.4f}", ci)
    console.print(t)

    info = (
        f"AIC={result.get('aic', '—')} · RMSE={result.get('rmse', 0):.4f} · "
        f"n={result.get('n_obs', 0)} · engine={result.get('engine', '—')}"
    )
    console.print(f"[dim]{info}[/dim]")
    _plotext_forecast(hist_times, hist_vals, times, forecasts, lo, hi,
                      ylabel=intent.get("outcome", "value"))


def _plt_transparent(plt) -> None:
    try:
        plt.canvas_color("default")
        plt.axes_color("default")
        plt.ticks_color("default")
    except Exception:
        pass


def _plotext_forecast(hist_t, hist_y, fc_t, fc_y, lo, hi, *, ylabel: str = "") -> None:
    try:
        import plotext as plt
        if not hist_y and not fc_y:
            return
        plt.clear_figure()
        w = min(console.size.width - 4, 100)
        plt.plot_size(w, 16)
        if hist_y:
            plt.plot(list(map(_to_num, hist_t)), list(map(float, hist_y)),
                     label="history", color="cyan")
        if fc_y:
            xs = list(map(_to_num, fc_t))
            plt.plot(xs, list(map(float, fc_y)), label="forecast", color="orange")
            if lo and hi and len(lo) == len(fc_y):
                plt.fill_between(xs, list(map(float, lo)), list(map(float, hi)),
                                 label="95% CI", color="orange+")
        plt.title(f"{'─'*4}  {_short(ylabel, 28)} — history + forecast  {'─'*4}")
        plt.xlabel("time")
        plt.ylabel(_short(ylabel, 16))
        _plt_transparent(plt)
        console.file.flush()
        _write_plot(plt.build())
    except Exception:
        pass


def _to_num(x):
    try:
        return float(x)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Regression result renderer (enhanced)
# ---------------------------------------------------------------------------

def render_regression(model_key: str, result: dict, intent: dict,
                      diagnostics: Optional[dict] = None,
                      df: "Optional[pd.DataFrame]" = None) -> None:
    eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    se = result.get("se", 0) or 0
    pval = result.get("pvalue", result.get("p_value", 1)) or 1
    ci_lo = result.get("ci_lower", eff - 1.96 * se)
    ci_hi = result.get("ci_upper", eff + 1.96 * se)
    r2 = result.get("r_squared", 0) or 0
    n = result.get("n_obs", 0)
    fe = result.get("fe_type", "")
    se_t = result.get("se_type", "")

    sig_star = "★★★" if pval < 0.001 else "★★" if pval < 0.01 else "★" if pval < 0.05 else "n.s."
    p_color = P["success"] if pval < 0.05 else (P["warning"] if pval < 0.10 else P["neutral"])

    # Log KEY result to the console log
    _shared_log.emit("KEY",
        f"β̂ = {eff:+.4f}  ·  CI [{ci_lo:.3f}, {ci_hi:.3f}]  ·  p = {pval:.4f}  {sig_star}")
    _shared_log.emit("FIT",
        f"R² = {r2:.4f}  ·  N = {n:,}" + (f"  ·  FE = {fe}" if fe else ""))

    t = Table(box=box.SIMPLE, header_style=f"bold {P['primary']}", show_lines=False,
              title=f"  {result.get('model', model_key)}", title_style="bold", title_justify="left")
    t.add_column("", style="dim")
    t.add_column("", style="bold")
    t.add_row("coef", f"{eff:+,.4f}")
    t.add_row("95% CI", f"[{ci_lo:,.3f},  {ci_hi:,.3f}]")
    t.add_row("p-value", f"[{p_color}]{pval:.4f}  {sig_star}[/{p_color}]")
    t.add_row("R²", f"{r2:.4f}  [dim]({r2*100:.1f}% variance explained)[/dim]")
    t.add_row("N", f"{n:,}")
    if fe:
        t.add_row("FE", fe)
    if se_t:
        t.add_row("SE", se_t)
    console.print(t)

    # Confidence score + big number panel
    diag = diagnostics or {}
    score = compute_confidence_score(result, diag, n)
    render_key_number_panel(result, intent, score)
    render_significance_meter(result, score)

    # Classic effect bar (kept for continuity)
    _effect_bar(eff, ci_lo, ci_hi)

    # Chart 1: outcome over time — multi-line by unit when panel data
    ts_vals  = result.get("_ts_values") or []
    ts_times = result.get("_ts_times")  or []
    _plotext_timeseries(
        ts_vals, ts_times,
        ylabel=intent.get("outcome", "outcome"),
        df=df,
        unit_col=intent.get("unit", ""),
        outcome_col=intent.get("outcome", ""),
    )

    # Chart 2: scatter + regression fit + CI band, colored by unit
    _plotext_scatter(result, intent)


_UNIT_COLORS = [
    "cyan+", "orange", "green+", "red+", "blue+", "magenta+",
    "yellow+", "cyan", "orange+", "green",
]


def _plotext_scatter(result: dict, intent: dict) -> None:
    """Scatter plot, colored by unit when panel data available."""
    try:
        import plotext as plt
        xs = result.get("_x_values")
        ys = result.get("_y_values")
        units = result.get("_unit_labels")  # V3: per-observation unit labels
        if not xs or not ys or len(xs) < 5:
            return

        xs_f = [float(v) for v in xs]
        ys_f = [float(v) for v in ys]

        xlabel = _short(intent.get("treatment") or "predictor", 28)
        ylabel = _short(intent.get("outcome") or "outcome", 20)
        w = min(console.size.width - 4, 92)

        slope  = result.get("slope", result.get("treatment_effect", result.get("effect", 0))) or 0
        mean_x = sum(xs_f) / len(xs_f)
        mean_y = sum(ys_f) / len(ys_f)
        x_min, x_max = min(xs_f), max(xs_f)
        fit_y0 = mean_y + slope * (x_min - mean_x)
        fit_y1 = mean_y + slope * (x_max - mean_x)

        plt.clear_figure()
        plt.plot_size(w, 18)

        if units and len(units) == len(xs_f):
            # Panel data: one scatter series per unit, each with a distinct color
            unique_units = list(dict.fromkeys(units))[:10]  # preserve order, cap at 10
            for i, u in enumerate(unique_units):
                ux = [x for x, ul in zip(xs_f, units) if ul == u]
                uy = [y for y, ul in zip(ys_f, units) if ul == u]
                color = _UNIT_COLORS[i % len(_UNIT_COLORS)]
                label = _short(str(u), 14)
                plt.scatter(ux, uy, label=label, color=color, marker="dot")
        else:
            # Cross-sectional: single series, deduplicated
            seen: set = set()
            xs_d, ys_d = [], []
            for x, y in zip(xs_f, ys_f):
                key = (round(x, 4), round(y, 2))
                if key not in seen:
                    seen.add(key)
                    xs_d.append(x)
                    ys_d.append(y)
            plt.scatter(xs_d, ys_d, label=f"obs (n={len(xs_d):,})", color="cyan+", marker="dot")

        # Regression fit line — drawn through centroid with CI band
        plt.plot([x_min, x_max], [fit_y0, fit_y1], label="OLS fit", color="orange")

        # Confidence band (±1.96·SE propagated from centroid)
        se = result.get("se", 0) or 0
        n  = len(xs_f) or 1
        x_std = (sum((x - mean_x) ** 2 for x in xs_f) / n) ** 0.5 or 1
        if se > 0:
            steps = 20
            band_x = [x_min + (x_max - x_min) * i / steps for i in range(steps + 1)]
            band_lo = [mean_y + slope * (x - mean_x) - 1.96 * se * abs(x - mean_x) / (x_std + 0.001)
                       for x in band_x]
            band_hi = [mean_y + slope * (x - mean_x) + 1.96 * se * abs(x - mean_x) / (x_std + 0.001)
                       for x in band_x]
            plt.fill_between(band_x, band_lo, band_hi, label="95% CI", color="orange+")

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(f"{'─'*3}  {ylabel}  vs  {xlabel}  ·  {slope:+.3f} per unit  {'─'*3}")
        _plt_transparent(plt)
        console.file.flush()
        _write_plot(plt.build())
    except Exception:
        pass


def _plotext_timeseries(ts_vals: list, ts_times: list, *, ylabel: str = "",
                         title: str = "", df: "Optional[pd.DataFrame]" = None,
                         unit_col: str = "", outcome_col: str = "") -> None:
    """Time-series plot. When panel data with df, draws one line per unit."""
    try:
        import plotext as plt
        w = min(console.size.width - 4, 92)
        plt.clear_figure()
        plt.plot_size(w, 14)

        plotted = False
        if df is not None and unit_col and outcome_col and unit_col in df.columns and outcome_col in df.columns:
            # Find a time column
            time_col = None
            for col in df.columns:
                if col != unit_col and col != outcome_col:
                    try:
                        vals = pd.to_numeric(df[col], errors="coerce").dropna()
                        if len(vals) > 0 and 1800 <= vals.mean() <= 2100 and vals.std() < 50:
                            time_col = col; break
                    except Exception:
                        pass

            if time_col:
                sub = df[[time_col, unit_col, outcome_col]].copy()
                sub[time_col]   = pd.to_numeric(sub[time_col],   errors="coerce")
                sub[outcome_col] = pd.to_numeric(sub[outcome_col], errors="coerce")
                sub = sub.dropna()
                unique_units = sub[unit_col].unique()[:8]
                for i, u in enumerate(unique_units):
                    u_data = sub[sub[unit_col] == u].sort_values(time_col)
                    if len(u_data) < 2:
                        continue
                    color = _UNIT_COLORS[i % len(_UNIT_COLORS)]
                    plt.plot(u_data[time_col].tolist(), u_data[outcome_col].tolist(),
                             label=_short(str(u), 12), color=color)
                    plotted = True

        if not plotted and ts_vals and len(ts_vals) >= 4:
            ts_f = [float(v) for v in ts_vals]
            tt_f = [_to_num(t) for t in ts_times]
            if any(t for t in tt_f):
                plt.plot(tt_f, ts_f, color="cyan", label=_short(ylabel, 24))
                plotted = True

        if not plotted:
            return

        plt.title(title or f"{'─'*3}  {_short(ylabel or outcome_col, 30)} over time  {'─'*3}")
        plt.xlabel("time")
        plt.ylabel(_short(ylabel or outcome_col, 16))
        _plt_transparent(plt)
        console.file.flush()
        _write_plot(plt.build())
    except Exception:
        pass


def _effect_bar(eff: float, lo: float, hi: float) -> None:
    width = max(40, min(console.size.width - 10, 70))
    lo_v, hi_v = min(lo, eff, 0.0), max(hi, eff, 0.0)
    span = hi_v - lo_v if hi_v > lo_v else 1.0

    def col(v):
        return int((v - lo_v) / span * (width - 1))

    bar = [" "] * width
    z = col(0.0)
    if 0 <= z < width:
        bar[z] = "│"
    a, b = col(lo), col(hi)
    for i in range(min(a, b), max(a, b) + 1):
        if bar[i] == " ":
            bar[i] = "─"
    e = col(eff)
    if 0 <= e < width:
        bar[e] = "●"
    line = "".join(bar)
    console.print(f"  [dim]{lo:>10.3g}[/dim]  {line}  [dim]{hi:<10.3g}[/dim]")
    console.print(f"  [dim]{'0' if lo < 0 < hi else '':>10}[/dim]  [dim]coefficient with 95% CI (● = estimate, │ = zero)[/dim]")


# ---------------------------------------------------------------------------
# Residual plot
# ---------------------------------------------------------------------------

def render_marginal_effects(result: dict, intent: dict, df: "Optional[pd.DataFrame]" = None) -> None:
    """
    Marginal effects plot: predicted Y across the observed range of X,
    with 95% CI band. Shows the regression finding as a meaningful curve.
    """
    try:
        import plotext as plt
        slope  = result.get("slope", result.get("treatment_effect", result.get("effect", 0))) or 0
        se     = result.get("se", 0) or 0
        xs     = result.get("_x_values")
        ys     = result.get("_y_values")
        if not xs or not ys or len(xs) < 3:
            return

        xs_f = [float(v) for v in xs]
        ys_f = [float(v) for v in ys]
        mean_x = sum(xs_f) / len(xs_f)
        mean_y = sum(ys_f) / len(ys_f)
        x_min, x_max = min(xs_f), max(xs_f)
        n = len(xs_f)
        x_std = (sum((x - mean_x) ** 2 for x in xs_f) / max(1, n)) ** 0.5 or 1.0

        steps = 40
        band_x  = [x_min + (x_max - x_min) * i / steps for i in range(steps + 1)]
        pred_y  = [mean_y + slope * (x - mean_x) for x in band_x]

        # CI widens away from centroid
        band_lo = [py - 1.96 * se * (1/n**0.5 + abs(x - mean_x)/x_std)**0.5
                   for x, py in zip(band_x, pred_y)]
        band_hi = [py + 1.96 * se * (1/n**0.5 + abs(x - mean_x)/x_std)**0.5
                   for x, py in zip(band_x, pred_y)]

        xlabel = _short(intent.get("treatment") or "X", 28)
        ylabel = _short(intent.get("outcome") or "Y", 20)
        w = min(console.size.width - 4, 92)

        plt.clear_figure()
        plt.plot_size(w, 14)

        # Confidence band first (background)
        plt.fill_between(band_x, band_lo, band_hi, label="95% CI", color="orange+")
        # Prediction line
        plt.plot(band_x, pred_y, label=f"predicted {ylabel}", color="orange")
        # Actual observations (faint)
        plt.scatter(xs_f, ys_f, label="observed", color="cyan", marker="dot")

        # Mark centroid
        plt.scatter([mean_x], [mean_y], label="mean", color="red+", marker="cross")

        direction = "↑" if slope > 0 else "↓"
        plt.title(
            f"{'─'*3}  Marginal effect: {ylabel} as {xlabel} varies  "
            f"({direction}{abs(slope):.3f} per unit)  {'─'*3}"
        )
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        _plt_transparent(plt)
        console.file.flush()
        _write_plot(plt.build())
    except Exception:
        pass


def render_residual_plot(result: dict) -> None:
    """ASCII scatter of residuals vs fitted values."""
    try:
        ys = result.get("_y_values")
        xs = result.get("_x_values")
        if not ys or not xs or len(ys) < 8:
            return
        eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
        se = result.get("se", 0) or 0
        intercept = result.get("intercept", 0.0) or 0.0

        xs_f = [float(v) for v in xs]
        ys_f = [float(v) for v in ys]
        mean_x = sum(xs_f) / len(xs_f)
        mean_y = sum(ys_f) / len(ys_f)
        fitted = [mean_y + eff * (x - mean_x) for x in xs_f]
        resids = [y - yh for y, yh in zip(ys_f, fitted)]

        import plotext as plt
        plt.clear_figure()
        w = min(console.size.width - 4, 80)
        plt.plot_size(w, 10)
        plt.scatter(fitted, resids, color="cyan", marker="dot")
        plt.plot([min(fitted), max(fitted)], [0, 0], color="orange")
        plt.title("─── Residuals vs Fitted ───")
        plt.xlabel("fitted")
        plt.ylabel("residual")
        _plt_transparent(plt)
        console.file.flush()
        _write_plot(plt.build())

        # Pattern check: simple correlation of |resid| with fitted
        abs_r = [abs(r) for r in resids]
        n = len(abs_r)
        cov = sum((f - mean_y) * (a - sum(abs_r) / n)
                  for f, a in zip(fitted, abs_r)) / max(1, n)
        if abs(cov) > 0.3 * (max(abs_r) - min(abs_r)) * (max(fitted) - min(fitted)) / n:
            console.print(f"  [{P['warning']}]⚡[/{P['warning']}]  [dim]Possible heteroscedasticity — residuals vary with fitted values.[/dim]")
        else:
            console.print(f"  [{P['success']}]✓[/{P['success']}]  [dim]Residuals appear random — no obvious pattern.[/dim]")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# World events renderer
# ---------------------------------------------------------------------------

def render_world_events(events: list, *, outcome_col: str = "") -> None:
    """Render world events with data-driven annotations."""
    if not events:
        return
    console.print()
    console.print(Rule("World Context", style=f"dim {P['world']}"))
    console.print(f"  [dim {P['accent']}]Events that shaped this data[/dim {P['accent']}]")
    console.print()
    for ev in events:
        year = ev.get("year", "")
        event = ev.get("event", "")
        effect = ev.get("effect", "")
        data_note = ev.get("data_note", "")
        console.print(
            f"  [{P['world']}]{year}[/{P['world']}]  [bold]{event}[/bold]"
        )
        if effect:
            console.print(f"       [dim]{effect}[/dim]")
        if data_note:
            console.print(f"       [{P['brand']}]→[/{P['brand']}] [dim italic]{data_note}[/dim italic]")
    console.print()
    console.print(
        f"  [{P['warning']}]⚠[/{P['warning']}]  [dim]These events may confound your result. "
        "Do they fall inside your treatment window?[/dim]"
    )


# ---------------------------------------------------------------------------
# Era breakdown renderer
# ---------------------------------------------------------------------------

def render_era_breakdown(eras: list) -> None:
    """Render sub-period effect table."""
    if not eras:
        return
    console.print()
    console.print(Rule("Effect across historical eras", style=f"dim {P['primary']}"))

    t = Table(box=box.SIMPLE, header_style=f"bold {P['primary']}", show_lines=False)
    t.add_column("Era", style="bold", min_width=18)
    t.add_column("Period", style="dim", min_width=11)
    t.add_column("Effect", justify="right")
    t.add_column("p", justify="right")
    t.add_column("Sig", justify="center")
    t.add_column("", min_width=20)

    estimates = [e.get("estimate", 0.0) for e in eras]
    max_abs = max((abs(v) for v in estimates), default=1.0) or 1.0

    for era in eras:
        est = era.get("estimate", 0.0)
        p = era.get("pvalue", 1.0)
        period = era.get("period", "")
        label = era.get("label", "")
        consistent = era.get("consistent", "")
        sig_star = "★★★" if p < 0.001 else "★★" if p < 0.01 else "★" if p < 0.05 else "n.s."
        p_color = P["success"] if p < 0.05 else (P["warning"] if p < 0.10 else P["neutral"])
        bar_len = int(abs(est) / max_abs * 16)
        bar = f"[{P['brand']}]{'█' * bar_len}[/{P['brand']}][dim]{'░' * (16 - bar_len)}[/dim]"
        t.add_row(label, period, f"{est:+.3f}", f"[{p_color}]{p:.3f}[/{p_color}]",
                  f"[{p_color}]{sig_star}[/{p_color}]", bar + f"  [dim]{consistent}[/dim]")
    console.print(t)

    # Structural break warning
    if len(estimates) >= 2:
        max_e = max(abs(v) for v in estimates)
        min_e = min(abs(v) for v in estimates)
        signs = set(1 if v >= 0 else -1 for v in estimates)
        if max_e > 0 and min_e > 0 and (max_e / min_e) > 2.5:
            console.print(
                f"  [{P['warning']}]⚡[/{P['warning']}]  [dim]Structural break detected: "
                f"effect varies {max_e/max(min_e,0.001):.1f}× across eras. Consider a Chow test.[/dim]"
            )
        if len(signs) > 1:
            console.print(
                f"  [{P['danger']}]⚡[/{P['danger']}]  [dim]Sign reversal across eras — "
                "interpret the main estimate with caution.[/dim]"
            )


# ---------------------------------------------------------------------------
# Espresso Verdict
# ---------------------------------------------------------------------------

def render_verdict(verdict_text: str, score: dict, caveat: str = "") -> None:
    body = (
        f"\n  [bold]{verdict_text}[/bold]\n\n"
        + (f"  [{P['warning']}]Watch out for[/{P['warning']}]  [dim]{caveat}[/dim]\n\n" if caveat else "")
        + f"  [{score['color']}]{score['bullet']} {score['label']}  {score['score']}/100[/{score['color']}]\n"
    )
    console.print(Panel(
        Text.from_markup(body),
        title=f"[bold {P['brand']}]  {MASCOT}  ESPRESSO VERDICT  [/bold {P['brand']}]",
        border_style=f"bold {P['primary']}",
        padding=(0, 1),
    ))


# ---------------------------------------------------------------------------
# Interpretation — 3-act narrative
# ---------------------------------------------------------------------------

_BLOCK_TITLES = [
    ("why_columns",  "Variables",          P["accent"]),
    ("why_model",    "Model choice",       P["accent"]),
    ("statistical",  "Result",             P["primary"]),
    ("domain",       "About this data",    "dim green"),
    ("past_trends",  "Historical pattern", "dim green"),
    ("literature",   "Research benchmark", "dim green"),
    ("sanity_check", "Sanity check",       "dim yellow"),
]


def _bullets(text: str, max_bullets: int = 4) -> str:
    import re
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bullets = []
    for line in lines:
        clean = re.sub(r"^[\-\*•·#]+\s*", "", line).strip()
        clean = re.sub(r"^\d+\.\s+", "", clean).strip()
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", clean)
        clean = re.sub(r"#+\s*", "", clean).strip()
        if clean and len(clean) > 4:
            bullets.append(clean)
    bullets = bullets[:max_bullets]
    return "\n".join(f"  [dim]·[/dim] {b}" for b in bullets)


def _paragraphs(text: str) -> str:
    """Preserve prose paragraphs — wrap long lines, keep blank-line breaks."""
    import re, textwrap
    # Strip leading markdown cruft but keep sentence structure
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.+?)\*",   r"\1", text)       # italic
    text = re.sub(r"^#+\s*",      "",    text, flags=re.MULTILINE)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    parts = []
    tw = max(60, min(console.size.width - 6, 90))
    for para in paras:
        wrapped = textwrap.fill(para, width=tw)
        parts.append(f"  {wrapped}")
    return "\n\n".join(parts)


_SECTION_ICONS = {
    "magnitude":            ("◈", P["brand"]),
    "mechanism":            ("◌", P["world"]),
    "what you didn't ask":  ("⚡", P["warning"]),
    "what you didnt ask":   ("⚡", P["warning"]),
    "didn't ask":           ("⚡", P["warning"]),
    "threats to validity":  ("△", P["danger"]),
    "threats":              ("△", P["danger"]),
    "validity":             ("△", P["danger"]),
}


def _section_meta(header: str) -> tuple[str, str]:
    """Map a section header to (icon, color)."""
    key = header.lower().strip()
    for k, (icon, color) in _SECTION_ICONS.items():
        if k in key:
            return icon, color
    return "◈", P["primary"]


def _render_deep_sections(text: str) -> None:
    """
    Parse `**Header**\\n- bullet\\n- bullet` blocks from LLM output.
    Renders each section in a compact 2-column layout:
      [icon] HEADER
              · bullet 1
              · bullet 2
    With colored vertical accent bars on the left for visual hierarchy.
    Falls back to plain bullets if no headers detected.
    """
    import re
    # Match **Header** at start or after newline (lookahead avoids consuming the newline)
    blocks_raw = re.split(r"\s*\*\*([^*\n]+)\*\*\s*\n?", text.strip())
    if len(blocks_raw) < 3:
        console.print(_bullets(text, 8))
        console.print()
        return

    pairs = list(zip(blocks_raw[1::2], blocks_raw[2::2]))
    for header, body in pairs:
        icon, color = _section_meta(header)
        header_clean = header.strip().upper()
        console.print(
            f"  [{color}]▎[/{color}] [bold {color}]{icon}[/bold {color}]  "
            f"[bold]{header_clean}[/bold]"
        )

        lines = [l.strip() for l in body.splitlines() if l.strip()]
        bullets_clean = []
        for line in lines:
            clean = re.sub(r"^[\-\*•·]+\s*", "", line).strip()
            clean = re.sub(r"^\d+\.\s+", "", clean).strip()
            clean = re.sub(r"\*\*(.+?)\*\*", lambda m: f"[bold]{m.group(1)}[/bold]", clean)
            if clean and len(clean) > 4:
                bullets_clean.append(clean)

        for b in bullets_clean[:4]:
            console.print(f"  [{color}]▎[/{color}]   [dim]·[/dim] {b}")
        console.print()


def render_deep_block(title: str, text: str) -> None:
    """Render a prose analysis block (not bullet-mashed)."""
    if not text or len(text) < 20:
        return
    console.print()
    console.print(f"  [bold {P['primary']}]{title}[/bold {P['primary']}]")
    console.print(f"  [dim {P['primary']}]{'─' * min(50, console.size.width - 6)}[/dim {P['primary']}]")
    console.print(_paragraphs(text))


def render_proactive_insights(insights: list) -> None:
    """Render data-driven 'you didn't ask but…' observations."""
    if not insights:
        return
    console.print()
    console.print(Rule(f"[bold {P['brand']}]◈  WHAT YOU DIDN'T ASK (BUT SHOULD KNOW)[/bold {P['brand']}]",
                       style=f"dim {P['primary']}"))
    console.print()
    for item in insights:
        icon = item.get("icon", "◈")
        color = item.get("color", P["brand"])
        heading = item.get("heading", "")
        body = item.get("body", "")
        console.print(f"  [{color}]{icon}[/{color}]  [bold]{heading}[/bold]")
        if body:
            console.print(f"     [dim]{body}[/dim]")
    console.print()


def render_interpretation(blocks: dict, *, expertise: str = "beginner",
                          web_context: str = "", deep_text: str = "") -> None:
    console.print()

    # ── ACT 1: WHAT WE FOUND ──
    console.print(Rule(
        f"[{P['brand']}]◈[/{P['brand']}]  [bold {P['primary']}]WHAT WE FOUND[/bold {P['primary']}]  [{P['brand']}]◈[/{P['brand']}]",
        style=f"{P['primary']}",
    ))
    console.print()

    # Plain-English stats translation (compact, color-accented)
    stat_text = (blocks.get("plain_english") or blocks.get("statistical") or "").strip()
    if stat_text:
        console.print(
            f"  [{P['brand']}]▎[/{P['brand']}] [bold {P['brand']}]◉[/bold {P['brand']}]  "
            f"[bold]IN PLAIN ENGLISH[/bold]"
        )
        import re as _re
        for line in stat_text.splitlines():
            clean = _re.sub(r"^[\-\*•·]+\s*", "", line.strip())
            clean = _re.sub(r"\*\*(.+?)\*\*", lambda m: f"[bold]{m.group(1)}[/bold]", clean)
            if clean and len(clean) > 4:
                console.print(f"  [{P['brand']}]▎[/{P['brand']}]   [dim]·[/dim] {clean}")
        console.print()

    # Deep analysis rendered as section bullets with icons + accent bars
    if deep_text and len(deep_text) > 50:
        _render_deep_sections(deep_text)

    if expertise != "expert":
        why_cols = (blocks.get("why_columns") or "").strip()
        if why_cols:
            console.print(
                f"  [{P['accent']}]▎[/{P['accent']}] [bold {P['accent']}]◇[/bold {P['accent']}]  "
                f"[bold]WHY THESE VARIABLES[/bold]"
            )
            import re as _re2
            for line in why_cols.splitlines()[:3]:
                clean = _re2.sub(r"^[\-\*•·]+\s*", "", line.strip())
                if clean and len(clean) > 4:
                    console.print(f"  [{P['accent']}]▎[/{P['accent']}]   [dim]·[/dim] {clean}")
            console.print()

    # ── ACT 2: WHAT THE WORLD KNOWS ──
    has_context = any(blocks.get(k, "").strip()
                      for k in ("domain", "past_trends", "literature"))
    if has_context or web_context:
        console.print()
        console.print(Rule(
            f"[{P['world']}]◌[/{P['world']}]  [bold {P['primary']}]WHAT THE WORLD KNOWS[/bold {P['primary']}]  [{P['world']}]◌[/{P['world']}]",
            style=f"{P['primary']}",
        ))
        console.print()

        # Web research context (kept as prose — it's a briefing)
        if web_context and len(web_context) > 30:
            console.print(
                f"  [{P['world']}]▎[/{P['world']}] [bold {P['world']}]◔[/bold {P['world']}]  "
                f"[bold]RESEARCH BRIEFING[/bold]"
            )
            wrap = _paragraphs(web_context)
            for line in wrap.splitlines():
                if line.strip():
                    console.print(f"  [{P['world']}]▎[/{P['world']}] {line.lstrip()}")
            console.print()

        import re as _re3
        for key, title, icon in [
            ("past_trends", "HISTORICAL PATTERN",  "↔"),
            ("literature",  "WHAT RESEARCHERS FIND", "◐"),
        ]:
            raw = (blocks.get(key) or "").strip()
            if raw and len(raw) >= 12:
                console.print(
                    f"  [{P['success']}]▎[/{P['success']}] [bold {P['success']}]{icon}[/bold {P['success']}]  "
                    f"[bold]{title}[/bold]"
                )
                for line in raw.splitlines()[:3]:
                    clean = _re3.sub(r"^[\-\*•·]+\s*", "", line.strip())
                    if clean and len(clean) > 4:
                        console.print(f"  [{P['success']}]▎[/{P['success']}]   [dim]·[/dim] {clean}")
                console.print()

        why_model_raw = (blocks.get("why_model") or "").strip()
        if why_model_raw and expertise != "expert":
            console.print(
                f"  [{P['accent']}]▎[/{P['accent']}] [bold {P['accent']}]◆[/bold {P['accent']}]  "
                f"[bold]WHY THIS MODEL[/bold]"
            )
            for line in why_model_raw.splitlines()[:3]:
                clean = _re3.sub(r"^[\-\*•·]+\s*", "", line.strip())
                if clean and len(clean) > 4:
                    console.print(f"  [{P['accent']}]▎[/{P['accent']}]   [dim]·[/dim] {clean}")
            console.print()

    # ── ACT 3: WHAT COULD MAKE US WRONG ──
    sanity_raw = (blocks.get("sanity_check") or "").strip()
    if sanity_raw:
        console.print()
        console.print(Rule(
            f"[{P['danger']}]△[/{P['danger']}]  [bold {P['primary']}]WHAT COULD MAKE US WRONG[/bold {P['primary']}]  [{P['danger']}]△[/{P['danger']}]",
            style=f"{P['primary']}",
        ))
        console.print()
        import re as _re4
        for line in sanity_raw.splitlines()[:5]:
            clean = _re4.sub(r"^[\-\*•·]+\s*", "", line.strip())
            if clean and len(clean) > 4:
                console.print(f"  [{P['danger']}]▎[/{P['danger']}]   [dim]·[/dim] {clean}")
        console.print()


def render_animated_result(result: dict, score: dict, intent: dict) -> None:
    """
    3-beat animated result reveal:
      Beat 1 — coefficient + CI bar fills left-to-right
      Beat 2 — confidence score components tick up
      Beat 3 — verdict-ready indicator
    Total: ~1.2 seconds. Falls back silently if terminal doesn't support it.
    """
    try:
        eff    = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
        se     = result.get("se", 0) or 0
        pval   = result.get("pvalue", result.get("p_value", 1)) or 1
        ci_lo  = result.get("ci_lower", eff - 1.96 * se)
        ci_hi  = result.get("ci_upper", eff + 1.96 * se)
        n      = result.get("n_obs", 0)
        outcome   = _short(intent.get("outcome",   "Y"), 18)
        treatment = _short(intent.get("treatment", "X"), 18)

        sig_star = "★★★" if pval < 0.001 else "★★" if pval < 0.01 else "★" if pval < 0.05 else "n.s."
        p_color  = P["success"] if pval < 0.05 else (P["warning"] if pval < 0.10 else P["neutral"])
        s_color  = score.get("color", P["neutral"])
        ci_width = abs(ci_hi - ci_lo)
        max_range = max(ci_width, abs(eff) * 2, 0.001)

        BAR = 36
        ci_fill = max(1, int((1 - ci_width / (max_range * 2 + 0.001)) * BAR))

        # Beat 1: animate the CI bar filling
        console.print()
        with Live(console=console, transient=True, refresh_per_second=20) as live:
            for step in range(BAR + 1):
                filled = min(step, ci_fill)
                bar = (f"[{P['brand']}]{'█' * filled}[/{P['brand']}]"
                       f"[dim]{'░' * (BAR - filled)}[/dim]")
                live.update(Text.from_markup(
                    f"  [{P['brand']}]β̂[/{P['brand']}] = [{P['brand']}]{eff:+.4f}[/{P['brand']}]"
                    f"  [{p_color}]{sig_star}[/{p_color}]"
                    f"  {bar}"
                    f"  [{P['accent']}][{ci_lo:.3f}, {ci_hi:.3f}][/{P['accent']}]"
                ))
                time.sleep(0.025)

        # Beat 2: print settled result line
        bar_final = (f"[{P['brand']}]{'█' * ci_fill}[/{P['brand']}]"
                     f"[dim]{'░' * (BAR - ci_fill)}[/dim]")
        console.print(
            f"  [{P['brand']}]β̂[/{P['brand']}] = [{P['brand']}]{eff:+.4f}[/{P['brand']}]"
            f"  [{p_color}]{sig_star}[/{p_color}]"
            f"  {bar_final}"
            f"  [{P['accent']}][{ci_lo:.3f}, {ci_hi:.3f}][/{P['accent']}]"
            f"  [dim]p={pval:.4f}  N={n:,}[/dim]"
        )

        # Beat 3: confidence score rolls up
        target = score.get("score", 0)
        with Live(console=console, transient=True, refresh_per_second=25) as live:
            for v in range(0, target + 1, max(1, target // 20)):
                live.update(Text.from_markup(
                    f"  [{s_color}]{MASCOT} Confidence  {v}/100[/{s_color}]  "
                    f"[dim]calculating…[/dim]"
                ))
                time.sleep(0.018)

        console.print(
            f"  [{s_color}]{MASCOT} {score.get('label', '')}  "
            f"{score.get('score', 0)}/100[/{s_color}]  "
            f"[dim]sig={score.get('sig',0)}/40  "
            f"diag={score.get('diag',0)}/25  "
            f"sample={score.get('samp',0)}/20  "
            f"era={score.get('era',0)}/15[/dim]"
        )
        console.print()

    except Exception:
        pass  # Fall back silently — standard panels still render below


def render_qq_plot(result: dict) -> None:
    """Quantile-Quantile plot of residuals vs normal distribution."""
    try:
        import plotext as plt
        import math as _math
        xs = result.get("_x_values")
        ys = result.get("_y_values")
        if not xs or not ys or len(ys) < 8:
            return
        eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
        xs_f = [float(v) for v in xs]
        ys_f = [float(v) for v in ys]
        mean_x = sum(xs_f) / len(xs_f)
        mean_y = sum(ys_f) / len(ys_f)
        resids = sorted([y - (mean_y + eff * (x - mean_x)) for x, y in zip(xs_f, ys_f)])
        n = len(resids)
        r_mean = sum(resids) / n
        r_std  = (_math.sqrt(sum((r - r_mean) ** 2 for r in resids) / max(1, n - 1))) or 1.0
        z_resids = [(r - r_mean) / r_std for r in resids]

        # Theoretical normal quantiles (Blom approximation)
        def _norm_ppf(p):
            # Rational approximation
            if p <= 0: return -4.0
            if p >= 1: return  4.0
            c = [-3.969683028665376e1, 2.209460984245205e2,
                 -2.759285104469687e2, 1.383577518672690e2,
                 -3.066479806614716e1, 2.506628277459239]
            d = [-5.447609879822406e1, 1.615858368580409e2,
                 -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1]
            p_lo = 0.02425; p_hi = 1 - p_lo
            if p < p_lo:
                q = _math.sqrt(-2 * _math.log(p))
                return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                       ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+d[4]+1)
            elif p <= p_hi:
                q = p - 0.5; r = q*q
                return ((((((-3.969683028665376e1*r+8.157415791047381e1)*r
                            -1.225447096821738e2)*r+7.700932670503960e1)*r
                           -1.671927108170951e1)*r+8.600745475767093e-1)*q) / \
                       ((((((-5.447609879822406e1*r+1.615858368580409e2)*r
                            -1.556989798598866e2)*r+6.680131188771972e1)*r
                           -1.328068155288572e1)*r+1)*1)
            else:
                q = _math.sqrt(-2 * _math.log(1 - p))
                return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                        ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+d[4]+1)

        theoretical = [_norm_ppf((i + 0.5) / n) for i in range(n)]

        w = min(console.size.width - 4, 80)
        plt.clear_figure()
        plt.plot_size(w, 10)
        plt.scatter(theoretical, z_resids, color="cyan", marker="dot")
        plt.plot([min(theoretical), max(theoretical)],
                 [min(theoretical), max(theoretical)], color="orange", label="ideal")
        plt.title("─── Q-Q Plot: residuals vs Normal  (deviations = non-normality) ───")
        plt.xlabel("theoretical quantile")
        plt.ylabel("sample quantile")
        _plt_transparent(plt)
        console.file.flush()
        _write_plot(plt.build())
    except Exception:
        pass


def render_followups(followups: list, *, countdown: bool = False,
                     countdown_secs: int = 8) -> Optional[int]:
    """
    Render follow-up suggestions.

    When countdown=True (REPL mode), shows a live countdown and auto-selects
    follow-up #1 when the timer expires. Returns the selected index (1-based)
    or 0 if the user skipped/pressed Enter.

    This is the UX differentiator: the tool anticipates the next step.
    """
    if not followups:
        return None
    console.print()
    console.print(Rule("What next?", style=f"dim {P['primary']}"))
    for i, q in enumerate(followups, 1):
        console.print(f"  [{P['brand']}]{i}[/{P['brand']}]  [dim]{q}[/dim]")
    console.print(
        f"\n  [dim {P['accent']}]or try:[/dim {P['accent']}]  "
        f"[{P['accent']}]eras[/{P['accent']}]  [dim]·[/dim]  "
        f"[{P['accent']}]robustness[/{P['accent']}]  [dim]·[/dim]  "
        f"[{P['accent']}]export table[/{P['accent']}]  [dim]·[/dim]  "
        f"[{P['accent']}]what if x = …[/{P['accent']}]  [dim]·[/dim]  "
        f"[{P['accent']}]export[/{P['accent']}]"
    )

    if countdown:
        return _followup_countdown(len(followups), countdown_secs)

    console.print(f"\n  [{P['brand']}]{MASCOT}[/{P['brand']}]  [{P['primary']}]ready  ›[/{P['primary']}]")
    return None


def _followup_countdown(n_choices: int, secs: int = 8) -> int:
    """
    Live countdown: auto-selects #1 after `secs` seconds.
    User can type 1-4 or Enter to skip before timer expires.
    Returns selected index (1-based) or 0 for skip.
    """
    import select as _select
    import threading

    console.print()
    chosen = [0]    # mutable container for thread communication
    done   = [False]

    def _timer_thread():
        for remaining in range(secs, 0, -1):
            if done[0]:
                return
            try:
                with Live(
                    Text.from_markup(
                        f"  [{P['brand']}]{MASCOT}[/{P['brand']}]  "
                        f"[{P['primary']}]auto-running #1 in {remaining}s[/{P['primary']}]  "
                        f"[dim](type 1-{n_choices} or Enter to skip)[/dim]"
                    ),
                    console=console, transient=True, refresh_per_second=2,
                ):
                    time.sleep(1.0)
                    if done[0]:
                        return
            except Exception:
                time.sleep(1.0)
                if done[0]:
                    return
        if not done[0]:
            done[0] = True
            chosen[0] = 1  # auto-select #1

    t = threading.Thread(target=_timer_thread, daemon=True)
    t.start()

    try:
        import sys as _sys
        raw = input()
        done[0] = True
        raw = raw.strip()
        if raw.isdigit() and 1 <= int(raw) <= n_choices:
            return int(raw)
        return 0
    except (EOFError, KeyboardInterrupt, Exception):
        done[0] = True
        return 0
    finally:
        t.join(timeout=0.5)

    return chosen[0]
