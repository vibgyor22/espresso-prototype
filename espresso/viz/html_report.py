"""
Espresso HTML export — V3 design.

Rebuilt from the ground up:
  - Results hero first (big effect number, stat tiles, confidence ring)
  - Chart.js scatter + time-series + forest plot
  - Tabbed interpretation panels
  - Interactive what-if slider with live chart
  - Diagnostics grid (compact)
  - Follow-up chips
  - Data profile collapsed at bottom (not dumped at the top)
  - espressov6 color/font language: Cormorant Garamond + IBM Plex Mono + Outfit
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

from ..whatif import html_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _h(text: Any) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _md(text: str) -> str:
    """Minimal markdown → HTML: bold, italic, bullet lines, newlines."""
    t = _h(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    # Bullet lines
    lines = t.split("\n")
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith("- ") or s.startswith("· "):
            out.append(f'<li>{s[2:]}</li>')
        elif s:
            out.append(f'<p>{s}</p>')
    return "\n".join(out)


def _scalar(v, fallback=0.0):
    if v is None:
        return fallback
    if isinstance(v, (list, tuple)):
        v = v[0] if v else fallback
    try:
        return float(v)
    except (TypeError, ValueError):
        return fallback


def _sig_stars(pval: float) -> str:
    if pval < 0.001:
        return "★★★"
    if pval < 0.01:
        return "★★"
    if pval < 0.05:
        return "★"
    return ""


def _sig_label(pval: float) -> str:
    if pval < 0.001:
        return "p &lt; 0.001"
    if pval < 0.01:
        return f"p = {pval:.4f}"
    if pval < 0.05:
        return f"p = {pval:.4f}"
    return f"p = {pval:.4f} (n.s.)"


def _pval_color(pval: float) -> str:
    if pval < 0.05:
        return "#2d6644"
    if pval < 0.10:
        return "#8a5228"
    return "#7a6050"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_html_report(session, output_path: str | None = None) -> str:
    if output_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        os.makedirs("outputs", exist_ok=True)
        output_path = f"outputs/espresso_report_{ts}.html"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    html = _build_html(session)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def _build_html(s) -> str:
    intent    = s.intent or {}
    result    = s.result or {}
    blocks    = s.interpretation_blocks or {}
    profile   = s.profile
    diag      = s.diagnostics or {}

    question      = _h(intent.get("question") or s.question or "Analysis")
    outcome       = _h(intent.get("outcome", ""))
    treatment     = _h(intent.get("treatment", ""))
    model_display = _h(s.model_display or "")
    model_key     = s.model_key or ""
    source        = _h(s.source_path or "")
    generated_at  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    _FORECAST_KEYS = {"arima", "linear_trend", "exp_smoothing", "random_walk"}
    is_forecast = model_key in _FORECAST_KEYS

    # --- numeric result values ---
    eff   = _scalar(result.get("treatment_effect", result.get("slope", result.get("effect", 0))))
    se    = _scalar(result.get("se"), 0.0)
    pval  = _scalar(result.get("pvalue", result.get("p_value", 1.0)), 1.0)
    ci_lo = _scalar(result.get("ci_lower"), eff - 1.96 * se)
    ci_hi = _scalar(result.get("ci_upper"), eff + 1.96 * se)
    r2    = _scalar(result.get("r_squared"), 0.0)
    n_obs = int(result.get("n_obs", 0) or 0)

    # confidence score
    cs      = getattr(s, "confidence_score", None) or {}
    score   = int(cs.get("score", 0))
    s_label = cs.get("label", "—")
    s_color = cs.get("color", "#95A5A6")

    verdict_text  = _h(getattr(s, "verdict_text", "") or "")
    world_events  = getattr(s, "world_events", []) or []
    era_effects   = getattr(s, "era_effects", []) or []
    followups     = s.followups or []

    # --- chart data ---
    x_vals  = result.get("_x_values", []) or []
    y_vals  = result.get("_y_values", []) or []
    ts_t    = result.get("_ts_times", []) or []
    ts_v    = result.get("_ts_values", []) or []
    u_lbl   = result.get("_unit_labels", []) or []

    # Scatter fit line (20-point range through centroid)
    fit_pts = []
    if x_vals and not is_forecast:
        xm = sum(x_vals) / len(x_vals)
        ym = sum(y_vals) / len(y_vals) if y_vals else 0
        xmin, xmax = min(x_vals), max(x_vals)
        span = xmax - xmin or 1
        for i in range(20):
            xp = xmin + span * i / 19
            yp = ym + eff * (xp - xm)
            fit_pts.append({"x": xp, "y": yp})

    # Forecast data
    fc_vals = result.get("forecasts", []) or []
    fc_t    = result.get("forecast_times", list(range(len(ts_t), len(ts_t) + len(fc_vals)))) or []
    fc_lo   = result.get("ci_lower", []) or []
    fc_hi   = result.get("ci_upper", []) or []
    hist_v  = result.get("historical_values", []) or []
    hist_t  = result.get("historical_times", []) or []

    # Payload for what-if
    payload = html_payload(result, model_key) if result else {"kind": "none"}

    # ---- build sections ----
    hero_html     = _hero_html(question, outcome, treatment, model_display, source, generated_at)
    stats_html    = _stats_html(eff, se, pval, ci_lo, ci_hi, r2, n_obs, score, s_label, s_color, is_forecast)
    verdict_html  = _verdict_html(verdict_text)
    interp_html   = _interp_html(blocks)
    world_html    = _world_html(world_events, outcome)
    era_html      = _era_html(era_effects)
    diag_html     = _diag_html(diag)
    followup_html = _followup_html(followups)
    profile_html  = _profile_html(profile)

    # chart JSON
    scatter_json = json.dumps({
        "pts": [{"x": x, "y": y} for x, y in zip(x_vals[:400], y_vals[:400])],
        "fit": fit_pts,
        "units": u_lbl[:400],
        "xLabel": str(intent.get("treatment", "")),
        "yLabel": str(intent.get("outcome", "")),
    })
    ts_json = json.dumps({
        "t": ts_t,
        "v": ts_v,
        "label": str(intent.get("outcome", "Outcome")),
    })
    forecast_json = json.dumps({
        "histT": [str(x) for x in hist_t],
        "histV": hist_v,
        "fcT":   [str(x) for x in fc_t],
        "fcV":   fc_vals,
        "fcLo":  [_scalar(v) for v in (fc_lo if isinstance(fc_lo, list) else [])],
        "fcHi":  [_scalar(v) for v in (fc_hi if isinstance(fc_hi, list) else [])],
        "label": str(intent.get("outcome", "Outcome")),
    })
    forest_json = json.dumps({
        "eff": eff, "lo": ci_lo, "hi": ci_hi,
        "label": str(intent.get("treatment", "Effect")),
    })
    whatif_payload_json = json.dumps(payload)

    # What-if section
    whatif_html = _whatif_html(payload, intent)

    return _PAGE.format(
        question=question,
        hero=hero_html,
        stats=stats_html,
        verdict=verdict_html,
        interp=interp_html,
        world=world_html,
        era=era_html,
        diag=diag_html,
        followups=followup_html,
        profile=profile_html,
        whatif=whatif_html,
        scatter_json=scatter_json,
        ts_json=ts_json,
        forecast_json=forecast_json,
        forest_json=forest_json,
        whatif_payload_json=whatif_payload_json,
        is_forecast="true" if is_forecast else "false",
        has_scatter="true" if x_vals else "false",
        has_ts="true" if ts_t else "false",
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _hero_html(question, outcome, treatment, model, source, gen_at) -> str:
    src_bit = f'<span class="hm-src">{source}</span>' if source else ""
    return f"""
<div class="hero-band">
  <div class="hb-brand">◈ ESPRESSO</div>
  <div class="hb-q">{question}</div>
  <div class="hb-meta">
    <span class="hm-pill">{model}</span>
    {f'<span class="hm-pill">{outcome} ← {treatment}</span>' if outcome and treatment else ""}
    {src_bit}
    <span class="hm-ts">{gen_at}</span>
  </div>
</div>"""


def _stats_html(eff, se, pval, ci_lo, ci_hi, r2, n_obs, score, s_label, s_color, is_forecast) -> str:
    # Confidence ring
    circ = 2 * math.pi * 34  # r=34
    dash = circ * (1 - score / 100)
    ring_col = "#2d6644" if score >= 70 else ("#8a5228" if score >= 45 else "#7a2828")
    p_col = _pval_color(pval)
    stars = _sig_stars(pval)
    sig_html = f'<span class="sig-stars">{stars}</span>' if stars else ""

    if is_forecast:
        # Forecast: show RMSE, AIC etc differently — handled elsewhere
        tiles = f"""
<div class="stat-tile">
  <div class="st-label">Confidence</div>
  <div class="st-val" style="color:{s_color}">{score}<span class="st-unit">/100</span></div>
  <div class="st-note">{s_label}</div>
</div>"""
    else:
        tiles = f"""
<div class="stat-tile st-main">
  <div class="st-label">Effect size</div>
  <div class="st-val">{eff:+.4f}</div>
  <div class="st-note">per unit {{}}</div>
</div>
<div class="stat-tile">
  <div class="st-label">p-value</div>
  <div class="st-val" style="color:{p_col}">{pval:.4f}{sig_html}</div>
  <div class="st-note">{'significant' if pval < 0.05 else 'not significant'}</div>
</div>
<div class="stat-tile">
  <div class="st-label">95% CI</div>
  <div class="st-val st-ci">[{ci_lo:.3f}, {ci_hi:.3f}]</div>
  <div class="st-note">{'excludes zero ✓' if (ci_lo > 0 or ci_hi < 0) else 'spans zero'}</div>
</div>
<div class="stat-tile">
  <div class="st-label">R²</div>
  <div class="st-val">{r2:.3f}</div>
  <div class="st-note">{r2*100:.1f}% variance explained</div>
</div>
<div class="stat-tile">
  <div class="st-label">N</div>
  <div class="st-val">{n_obs:,}</div>
  <div class="st-note">observations</div>
</div>"""

    return f"""
<div class="stats-row">
  <div class="stats-tiles">{tiles}</div>
  <div class="ring-wrap">
    <svg class="ring-svg" viewBox="0 0 80 80">
      <defs>
        <linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#8a5228"/>
          <stop offset="100%" stop-color="#d4a85a"/>
        </linearGradient>
      </defs>
      <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(26,14,6,.06)" stroke-width="5"/>
      <circle cx="40" cy="40" r="34" fill="none" stroke="url(#rg)" stroke-width="5"
        stroke-linecap="round"
        stroke-dasharray="{circ:.1f}"
        stroke-dashoffset="{circ:.1f}"
        style="transform:rotate(-90deg);transform-origin:center;
               transition:stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)"
        data-target="{dash:.1f}"
        id="ringCircle"/>
    </svg>
    <div class="ring-center">
      <div class="ring-score" style="color:{ring_col}">{score}</div>
      <div class="ring-sub">/ 100</div>
    </div>
    <div class="ring-label">{s_label}</div>
  </div>
</div>"""


def _verdict_html(verdict_text: str) -> str:
    if not verdict_text:
        return ""
    return f"""
<div class="verdict-band">
  <div class="vb-icon">◈</div>
  <div class="vb-text">{verdict_text}</div>
</div>"""


def _interp_html(blocks: dict) -> str:
    if not blocks:
        return ""
    tabs = [
        ("result",    "Result",      "statistical"),
        ("variables", "Variables",   "why_columns"),
        ("model",     "Model",       "why_model"),
        ("domain",    "Context",     "domain"),
        ("sanity",    "Sanity",      "sanity_check"),
        ("trends",    "Trends",      "past_trends"),
        ("lit",       "Literature",  "literature"),
    ]
    tab_buttons = []
    tab_panes = []
    first = True
    for tab_id, label, key in tabs:
        text = (blocks.get(key) or "").strip()
        if not text:
            continue
        active = "active" if first else ""
        tab_buttons.append(f'<button class="tab-btn {active}" data-tab="{tab_id}">{label}</button>')
        tab_panes.append(f'<div class="tab-pane {active}" id="tab-{tab_id}"><div class="prose">{_md(text)}</div></div>')
        first = False
    if not tab_buttons:
        return ""
    return f"""
<div class="interp-card">
  <div class="card-label">Analysis</div>
  <div class="tab-bar">{"".join(tab_buttons)}</div>
  <div class="tab-body">{"".join(tab_panes)}</div>
</div>"""


def _world_html(events: list, outcome: str) -> str:
    if not events:
        return ""
    rows = []
    for ev in events[:6]:
        year  = _h(str(ev.get("year", "")))
        event = _h(ev.get("event", ""))
        effect = _h(ev.get("effect", ""))
        note  = _h(ev.get("data_note", ""))
        note_html = f'<div class="we-note">{note}</div>' if note else ""
        rows.append(f"""
<div class="we-row">
  <div class="we-year">{year}</div>
  <div class="we-body">
    <div class="we-event">{event}</div>
    <div class="we-effect">{effect}</div>
    {note_html}
  </div>
</div>""")
    return f"""
<div class="section-card">
  <div class="card-label">Historical context · {_h(outcome)}</div>
  <div class="we-list">{"".join(rows)}</div>
</div>"""


def _era_html(era_effects: list) -> str:
    if not era_effects:
        return ""
    rows = []
    for era in era_effects[:6]:
        label = _h(era.get("label", ""))
        est   = era.get("estimate", 0) or 0
        pv    = era.get("pvalue", 1) or 1
        n_e   = era.get("n_obs", 0) or 0
        bar_w = min(100, int(abs(est) / (abs(est) + 0.001) * 60 + 30))
        bar_col = "#2d6644" if est >= 0 else "#7a2828"
        p_col  = _pval_color(pv)
        rows.append(f"""
<div class="era-row">
  <div class="era-label">{label}</div>
  <div class="era-bar-wrap"><div class="era-bar" style="width:{bar_w}%;background:{bar_col}"></div></div>
  <div class="era-est">{est:+.3f}</div>
  <div class="era-p" style="color:{p_col}">p={pv:.3f}</div>
  <div class="era-n">n={n_e:,}</div>
</div>""")
    return f"""
<div class="section-card">
  <div class="card-label">Era breakdown</div>
  <div class="era-grid">
    <div class="era-head">
      <span>Period</span><span></span><span>Effect</span><span>p-val</span><span>Obs</span>
    </div>
    {"".join(rows)}
  </div>
</div>"""


def _diag_html(diag: dict) -> str:
    if not diag or "error" in diag:
        return ""
    checks = diag.get("checks", [])
    if not checks:
        return ""
    rows = []
    for ch in checks:
        if "error" in ch:
            rows.append(f'<div class="dc-row dc-err"><span class="dc-icon">⚠</span><span class="dc-name">{_h(ch.get("test",""))}</span><span class="dc-interp">{_h(ch["error"])}</span></div>')
            continue
        ok  = not ch.get("is_violated", False)
        icon = "✓" if ok else "✗"
        cls  = "dc-ok" if ok else "dc-fail"
        rows.append(f'<div class="dc-row {cls}"><span class="dc-icon">{icon}</span><span class="dc-name">{_h(ch.get("test",""))}</span><span class="dc-interp">{_h(ch.get("interpretation",""))}</span></div>')

    violations = diag.get("violations", [])
    v_html = ""
    if violations:
        v_html = '<div class="dc-violations">' + " · ".join(_h(v) for v in violations) + "</div>"

    return f"""
<div class="section-card">
  <div class="card-label">Model diagnostics</div>
  <div class="diag-grid">{"".join(rows)}</div>
  {v_html}
</div>"""


def _followup_html(items: list) -> str:
    if not items:
        return ""
    chips = "".join(f'<div class="fu-chip">{_h(q)}</div>' for q in items)
    return f"""
<div class="section-card">
  <div class="card-label">Suggested next analyses</div>
  <div class="fu-grid">{chips}</div>
</div>"""


def _profile_html(profile) -> str:
    if profile is None:
        return ""
    struct = _h(profile.structure)
    n_rows = f"{profile.n_rows:,}" if profile.n_rows else "?"
    n_cols = profile.n_cols or "?"
    # Show only key numeric columns (first 12), hide the rest in collapsed
    cols = profile.columns or []
    rows_html = []
    for c in cols[:12]:
        if c.min is not None and c.max is not None:
            r = f"{c.min:.4g} – {c.max:.4g}"
        elif c.top_values:
            r = ", ".join(str(t["value"]) for t in c.top_values[:2])
        else:
            r = "—"
        rows_html.append(
            f'<tr><td class="pc-name">{_h(c.name)}</td>'
            f'<td class="pc-type">{_h(c.semantic_type)}</td>'
            f'<td class="pc-r">{_h(r)}</td>'
            f'<td class="pc-miss">{c.missing_pct:.0f}%</td></tr>'
        )
    more = len(cols) - 12
    more_html = f'<div class="pc-more">+ {more} more columns</div>' if more > 0 else ""
    return f"""
<details class="profile-accordion">
  <summary class="pa-summary">
    <span class="pa-icon">▸</span>
    <span class="pa-title">Data profile</span>
    <span class="pa-meta">{n_rows} rows · {n_cols} cols · {struct}</span>
  </summary>
  <div class="pa-body">
    <table class="pc-table">
      <thead><tr><th>Column</th><th>Type</th><th>Range / Top</th><th>Missing</th></tr></thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
    {more_html}
  </div>
</details>"""


def _whatif_html(payload: dict, intent: dict) -> str:
    if payload.get("kind") == "regression":
        label     = _h(intent.get("treatment", "predictor"))
        out_label = _h(intent.get("outcome", "outcome"))
        x0 = float(payload.get("x_mean") or 0)
        xlo = x0 - max(abs(x0) * 0.5, 10)
        xhi = x0 + max(abs(x0) * 0.5, 10)
        return f"""
<div class="section-card">
  <div class="card-label">What-if · scenario explorer</div>
  <div class="wi-body">
    <div class="wi-controls">
      <label class="wi-label">If <strong>{label}</strong> were:</label>
      <div class="wi-slider-row">
        <span class="wi-min">{xlo:.1f}</span>
        <input id="wiSlider" type="range" min="{xlo:.4f}" max="{xhi:.4f}" step="{(xhi-xlo)/200:.4f}" value="{x0:.4f}" class="wi-slider">
        <span class="wi-max">{xhi:.1f}</span>
      </div>
      <div class="wi-current">Current: <strong id="wiVal">{x0:.2f}</strong></div>
    </div>
    <div class="wi-readout">
      <div class="wi-tile">
        <div class="wit-label">Predicted {out_label}</div>
        <div class="wit-val" id="wiPred">—</div>
      </div>
      <div class="wi-tile">
        <div class="wit-label">95% CI</div>
        <div class="wit-val" id="wiCI">—</div>
      </div>
      <div class="wi-tile">
        <div class="wit-label">Δ from baseline</div>
        <div class="wit-val" id="wiDelta">—</div>
      </div>
    </div>
    <canvas id="wiChart" height="80"></canvas>
  </div>
</div>"""
    if payload.get("kind") == "forecast":
        return """
<div class="section-card">
  <div class="card-label">What-if · shock scenario</div>
  <div class="wi-body">
    <div class="wi-controls">
      <label class="wi-label">Apply a shock to next-period value:</label>
      <div class="wi-slider-row">
        <span class="wi-min">-10</span>
        <input id="wiSlider" type="range" min="-10" max="10" step="0.1" value="0" class="wi-slider">
        <span class="wi-max">+10</span>
      </div>
      <div class="wi-current">Shock: <strong id="wiVal">0.00</strong></div>
    </div>
    <div class="wi-readout">
      <div class="wi-tile"><div class="wit-label">Shifted forecast</div><div class="wit-val" id="wiPred">—</div></div>
      <div class="wi-tile"><div class="wit-label">Decay (AR1)</div><div class="wit-val" id="wiDelta">—</div></div>
    </div>
  </div>
</div>"""
    return ""


# ---------------------------------------------------------------------------
# Page template
# ---------------------------------------------------------------------------

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{question} · Espresso</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js" crossorigin="anonymous"></script>
<style>
:root{{
  --bg:#f6f1e9;--cream:#ede6d6;--linen:#ddd3c0;
  --ink:#1a0e06;--maho:#381808;--walnut:#5a3018;--cara:#8a5228;
  --gold:#b8863c;--goldL:#d4a85a;
  --green:#2d6644;--red:#7a2828;--mid:#7a6050;--faint:#a89080;
  --bm:rgba(26,14,6,.1);--bl:rgba(26,14,6,.05);
  --sh:0 2px 12px rgba(26,14,6,.07);--shM:0 6px 24px rgba(26,14,6,.1);
  --r:8px;
  --ui:'Outfit',sans-serif;
  --serif:'Cormorant Garamond',Georgia,serif;
  --mono:'IBM Plex Mono',monospace;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--ink);font-family:var(--ui);font-size:14px;line-height:1.6}}
::-webkit-scrollbar{{width:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--linen);border-radius:3px}}

/* ── Layout ── */
.page{{max-width:920px;margin:0 auto;padding:0 20px 80px}}

/* ── Hero band ── */
.hero-band{{
  background:linear-gradient(135deg,var(--maho) 0%,var(--walnut) 100%);
  color:#f5e6d3;padding:32px 36px 28px;
  border-radius:0 0 var(--r) var(--r);
  margin-bottom:28px;position:relative;overflow:hidden
}}
.hero-band::after{{
  content:'';position:absolute;right:-60px;top:-60px;
  width:260px;height:260px;border-radius:50%;
  background:radial-gradient(circle,rgba(184,134,60,.15) 0%,transparent 70%);
  pointer-events:none
}}
.hb-brand{{
  font-family:var(--mono);font-size:9px;letter-spacing:.26em;
  text-transform:uppercase;color:rgba(212,168,98,.5);margin-bottom:10px
}}
.hb-q{{
  font-family:var(--serif);font-style:italic;font-size:1.7rem;
  color:#f5e6d3;line-height:1.25;margin-bottom:14px;
  max-width:780px
}}
.hb-meta{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.hm-pill{{
  font-family:var(--mono);font-size:10px;
  background:rgba(184,134,60,.18);border:1px solid rgba(184,134,60,.3);
  color:rgba(212,168,98,.85);padding:3px 10px;border-radius:20px;
  letter-spacing:.04em
}}
.hm-src{{font-family:var(--mono);font-size:10px;color:rgba(212,168,98,.35)}}
.hm-ts{{font-family:var(--mono);font-size:10px;color:rgba(212,168,98,.25);margin-left:auto}}

/* ── Stats row ── */
.stats-row{{
  display:flex;gap:16px;align-items:flex-start;margin-bottom:24px
}}
.stats-tiles{{display:flex;flex-wrap:wrap;gap:12px;flex:1}}
.stat-tile{{
  background:rgba(255,255,255,.65);border:1px solid var(--bm);
  border-radius:var(--r);padding:14px 16px;min-width:120px;flex:1;
  box-shadow:var(--sh);transition:transform .2s,box-shadow .2s
}}
.stat-tile:hover{{transform:translateY(-2px);box-shadow:var(--shM)}}
.st-main{{border-color:rgba(184,134,60,.3);background:rgba(184,134,60,.04)}}
.st-label{{
  font-family:var(--mono);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin-bottom:6px
}}
.st-val{{
  font-family:var(--serif);font-size:1.5rem;font-weight:300;
  color:var(--maho);line-height:1;margin-bottom:4px;
  font-variant-numeric:tabular-nums
}}
.st-ci{{font-size:1rem;font-family:var(--mono);color:var(--mid)}}
.st-unit{{font-size:.8rem;color:var(--faint)}}
.st-note{{font-size:11px;color:var(--faint)}}
.sig-stars{{color:var(--gold);font-size:.9rem;margin-left:4px}}

/* ── Confidence ring ── */
.ring-wrap{{
  flex-shrink:0;width:96px;display:flex;flex-direction:column;
  align-items:center;gap:6px;padding-top:4px
}}
.ring-svg{{width:80px;height:80px}}
.ring-center{{
  position:relative;margin-top:-72px;width:80px;height:80px;
  display:flex;flex-direction:column;align-items:center;justify-content:center
}}
.ring-score{{
  font-family:var(--mono);font-size:18px;font-weight:500;
  color:var(--cara);line-height:1
}}
.ring-sub{{font-family:var(--mono);font-size:9px;color:var(--faint)}}
.ring-label{{
  font-family:var(--mono);font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);text-align:center;
  margin-top:8px
}}

/* ── Verdict ── */
.verdict-band{{
  background:linear-gradient(135deg,rgba(184,134,60,.08),rgba(255,255,255,.5));
  border:1.5px solid rgba(184,134,60,.25);border-radius:var(--r);
  padding:18px 22px;display:flex;gap:14px;align-items:flex-start;
  margin-bottom:24px;box-shadow:var(--sh)
}}
.vb-icon{{
  font-size:1.2rem;color:var(--gold);flex-shrink:0;
  font-family:var(--serif);line-height:1.4
}}
.vb-text{{
  font-family:var(--serif);font-size:1.05rem;color:var(--maho);
  line-height:1.55
}}

/* ── Charts ── */
.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
.charts-row.single{{grid-template-columns:1fr}}
.chart-card{{
  background:rgba(255,255,255,.65);border:1px solid var(--bm);
  border-radius:var(--r);padding:16px 18px;box-shadow:var(--sh)
}}
.chart-card.wide{{grid-column:1/-1}}
.cc-label{{
  font-family:var(--mono);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin-bottom:10px
}}
.chart-canvas-wrap{{position:relative;height:180px}}

/* ── Section cards ── */
.section-card{{
  background:rgba(255,255,255,.6);border:1px solid var(--bm);
  border-radius:var(--r);padding:20px 22px;margin-bottom:20px;
  box-shadow:var(--sh)
}}
.card-label{{
  font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--cara);margin-bottom:14px;
  display:flex;align-items:center;gap:8px
}}
.card-label::after{{content:'';flex:1;height:1px;background:var(--bm)}}

/* ── Tabs ── */
.interp-card{{
  background:rgba(255,255,255,.6);border:1px solid var(--bm);
  border-radius:var(--r);padding:20px 22px;margin-bottom:20px;
  box-shadow:var(--sh)
}}
.tab-bar{{
  display:flex;flex-wrap:wrap;gap:4px;margin-bottom:16px;
  border-bottom:1px solid var(--bl);padding-bottom:10px
}}
.tab-btn{{
  font-family:var(--mono);font-size:10px;letter-spacing:.06em;
  text-transform:uppercase;padding:5px 12px;border-radius:4px;
  border:1px solid transparent;background:transparent;
  color:var(--faint);cursor:pointer;transition:all .18s
}}
.tab-btn:hover{{background:rgba(184,134,60,.08);color:var(--cara)}}
.tab-btn.active{{
  background:rgba(184,134,60,.1);border-color:rgba(184,134,60,.25);
  color:var(--walnut)
}}
.tab-pane{{display:none}}.tab-pane.active{{display:block}}
.prose p{{color:var(--mid);font-size:13px;line-height:1.65;margin-bottom:8px}}
.prose li{{
  color:var(--mid);font-size:13px;line-height:1.65;
  padding:4px 0 4px 16px;position:relative;
  border-bottom:1px solid var(--bl)
}}
.prose li::before{{
  content:'·';position:absolute;left:4px;color:var(--gold)
}}
.prose strong{{color:var(--maho)}}
.prose em{{color:var(--cara);font-style:italic}}

/* ── World events ── */
.we-list{{display:flex;flex-direction:column;gap:10px}}
.we-row{{display:flex;gap:14px;align-items:flex-start}}
.we-year{{
  font-family:var(--serif);font-size:1.1rem;color:rgba(184,134,60,.5);
  min-width:46px;flex-shrink:0;padding-top:1px
}}
.we-event{{font-size:13px;font-weight:500;color:var(--maho);margin-bottom:2px}}
.we-effect{{font-size:12px;color:var(--mid)}}
.we-note{{
  font-family:var(--mono);font-size:10px;color:var(--faint);
  margin-top:3px;padding:4px 8px;background:rgba(26,14,6,.03);
  border-radius:4px;border-left:2px solid rgba(184,134,60,.2)
}}

/* ── Era breakdown ── */
.era-grid{{display:flex;flex-direction:column;gap:6px}}
.era-head{{
  display:grid;grid-template-columns:140px 1fr 70px 60px 60px;
  gap:8px;font-family:var(--mono);font-size:9px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--faint);padding:0 0 6px;
  border-bottom:1px solid var(--bl)
}}
.era-row{{
  display:grid;grid-template-columns:140px 1fr 70px 60px 60px;
  gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--bl)
}}
.era-label{{font-size:12px;color:var(--mid)}}
.era-bar-wrap{{background:rgba(26,14,6,.04);border-radius:10px;height:8px;overflow:hidden}}
.era-bar{{height:100%;border-radius:10px;transition:width .8s ease}}
.era-est{{font-family:var(--mono);font-size:12px;color:var(--ink);text-align:right}}
.era-p{{font-family:var(--mono);font-size:11px;text-align:right}}
.era-n{{font-family:var(--mono);font-size:11px;color:var(--faint);text-align:right}}

/* ── Diagnostics ── */
.diag-grid{{display:flex;flex-direction:column;gap:6px}}
.dc-row{{
  display:grid;grid-template-columns:24px 200px 1fr;
  gap:10px;align-items:flex-start;padding:8px 10px;
  border-radius:6px;border:1px solid transparent
}}
.dc-ok{{background:rgba(45,102,68,.04);border-color:rgba(45,102,68,.1)}}
.dc-fail{{background:rgba(122,40,40,.04);border-color:rgba(122,40,40,.12)}}
.dc-err{{background:rgba(184,134,60,.05);border-color:rgba(184,134,60,.15)}}
.dc-icon{{
  font-family:var(--mono);font-size:13px;
  color:var(--green);font-weight:600;padding-top:1px
}}
.dc-fail .dc-icon{{color:var(--red)}}
.dc-err .dc-icon{{color:var(--gold)}}
.dc-name{{font-family:var(--mono);font-size:11px;color:var(--ink)}}
.dc-interp{{font-size:12px;color:var(--mid);line-height:1.5}}
.dc-violations{{
  margin-top:10px;padding:8px 12px;
  background:rgba(122,40,40,.05);border:1px solid rgba(122,40,40,.15);
  border-radius:6px;font-size:12px;color:var(--red)
}}

/* ── Follow-ups ── */
.fu-grid{{display:flex;flex-direction:column;gap:8px}}
.fu-chip{{
  padding:12px 16px;border-radius:var(--r);
  background:rgba(255,255,255,.7);border:1px solid var(--bm);
  font-size:13px;color:var(--mid);cursor:pointer;
  transition:all .2s;line-height:1.4
}}
.fu-chip:hover{{
  border-color:rgba(184,134,60,.3);background:rgba(184,134,60,.05);
  color:var(--maho);transform:translateX(4px)
}}

/* ── What-if ── */
.wi-body{{display:flex;flex-direction:column;gap:16px}}
.wi-controls{{background:rgba(184,134,60,.04);border-radius:6px;padding:14px 16px}}
.wi-label{{font-size:13px;color:var(--mid);margin-bottom:10px;display:block}}
.wi-slider-row{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.wi-min,.wi-max{{font-family:var(--mono);font-size:10px;color:var(--faint)}}
.wi-slider{{
  flex:1;-webkit-appearance:none;height:4px;
  background:linear-gradient(90deg,var(--walnut),var(--goldL));
  border-radius:2px;cursor:pointer
}}
.wi-slider::-webkit-slider-thumb{{
  -webkit-appearance:none;width:16px;height:16px;
  border-radius:50%;background:var(--goldL);border:2px solid var(--walnut);
  cursor:pointer;transition:transform .15s
}}
.wi-slider::-webkit-slider-thumb:hover{{transform:scale(1.2)}}
.wi-current{{font-family:var(--mono);font-size:11px;color:var(--faint)}}
.wi-current strong{{color:var(--cara)}}
.wi-readout{{display:flex;gap:12px;flex-wrap:wrap}}
.wi-tile{{
  flex:1;min-width:120px;background:rgba(255,255,255,.7);
  border:1px solid var(--bm);border-radius:var(--r);
  padding:12px 14px;transition:box-shadow .2s
}}
.wi-tile:hover{{box-shadow:var(--sh)}}
.wit-label{{
  font-family:var(--mono);font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);margin-bottom:6px
}}
.wit-val{{
  font-family:var(--serif);font-size:1.3rem;color:var(--maho);
  font-variant-numeric:tabular-nums
}}

/* ── Profile accordion ── */
.profile-accordion{{
  background:rgba(255,255,255,.5);border:1px solid var(--bm);
  border-radius:var(--r);margin-bottom:20px;overflow:hidden
}}
.pa-summary{{
  display:flex;align-items:center;gap:10px;padding:14px 18px;
  cursor:pointer;list-style:none;transition:background .18s
}}
.pa-summary:hover{{background:rgba(184,134,60,.05)}}
.pa-icon{{
  font-family:var(--mono);font-size:11px;color:var(--gold);
  transition:transform .2s;flex-shrink:0
}}
details[open] .pa-icon{{transform:rotate(90deg)}}
.pa-title{{
  font-family:var(--mono);font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--cara)
}}
.pa-meta{{
  font-family:var(--mono);font-size:10px;color:var(--faint);margin-left:auto
}}
.pa-body{{padding:0 18px 16px}}
.pc-table{{width:100%;border-collapse:collapse;font-size:12px}}
.pc-table th{{
  font-family:var(--mono);font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);
  padding:6px 8px;border-bottom:1.5px solid var(--bm);text-align:left
}}
.pc-table td{{padding:5px 8px;border-bottom:1px solid var(--bl);color:var(--mid)}}
.pc-table tr:hover td{{background:rgba(255,255,255,.5)}}
.pc-name{{font-family:var(--mono);font-size:11px;color:var(--ink);font-weight:500}}
.pc-type{{font-family:var(--mono);font-size:10px;color:var(--cara)}}
.pc-r{{font-family:var(--mono);font-size:10px}}
.pc-miss{{font-family:var(--mono);font-size:10px;color:var(--faint)}}
.pc-more{{
  font-family:var(--mono);font-size:10px;color:var(--faint);
  padding:10px 8px;text-align:center
}}

/* ── Footer ── */
.page-footer{{
  text-align:center;padding:32px 0 20px;
  font-family:var(--mono);font-size:10px;
  color:var(--faint);border-top:1px solid var(--bl);margin-top:20px
}}
.pf-brand{{color:var(--gold);margin-bottom:6px}}
.pf-disc{{color:rgba(168,144,128,.5);max-width:600px;margin:0 auto;line-height:1.6}}

@media(max-width:640px){{
  .charts-row{{grid-template-columns:1fr}}
  .stats-tiles{{flex-direction:column}}
  .era-head,.era-row{{grid-template-columns:100px 1fr 60px}}
  .era-p,.era-n{{display:none}}
}}
</style>
</head>
<body>
<div class="page">

{hero}

{stats}

{verdict}

<!-- Charts -->
<div id="chartsZone"></div>

<!-- Interpretation -->
{interp}

<!-- World context -->
{world}

<!-- Era breakdown -->
{era}

<!-- Diagnostics -->
{diag}

<!-- What-if -->
{whatif}

<!-- Follow-ups -->
{followups}

<!-- Data profile (collapsed) -->
{profile}

<footer class="page-footer">
  <div class="pf-brand">◈ Espresso · Agentic Econometric Analyst</div>
  <div class="pf-disc">Generated {generated_at}. Statistical estimates are deterministic. Qualitative context is LLM-generated narrative and should not be cited verbatim.</div>
</footer>

</div><!-- /page -->

<script>
"use strict";

/* ── Data ── */
const SCATTER = {scatter_json};
const TS      = {ts_json};
const FORECAST = {forecast_json};
const FOREST  = {forest_json};
const WHATIF  = {whatif_payload_json};
const IS_FORECAST = {is_forecast};
const HAS_SCATTER = {has_scatter};
const HAS_TS      = {has_ts};

/* ── Palette ── */
const C = {{
  maho:    '#381808', walnut: '#5a3018', cara: '#8a5228',
  gold:    '#b8863c', goldL: '#d4a85a',
  green:   '#2d6644', red:   '#7a2828', mid:  '#7a6050',
  faint:   '#a89080', ink:   '#1a0e06',
  bgLine:  'rgba(26,14,6,.08)',
}};

const chartDefaults = {{
  font: {{ family: "'IBM Plex Mono', monospace", size: 10 }},
  color: C.mid,
}};
Chart.defaults.font = chartDefaults.font;
Chart.defaults.color = chartDefaults.color;

function gridLines() {{
  return {{ color: 'rgba(26,14,6,.06)', drawBorder: false }};
}}
function noLegend() {{ return {{ display: false }}; }}

/* Shared base options — no animation, no resize loops */
function baseOpts(extra) {{
  return Object.assign({{
    animation: false,
    responsive: false,
    maintainAspectRatio: false,
    plugins: {{ legend: noLegend() }},
  }}, extra || {{}});
}}

/* ── Build chart zone ── */
function buildCharts() {{
  const zone = document.getElementById('chartsZone');
  if (!zone) return;

  const SCATTER_H = 200, TS_H = 200, FOREST_H = 80;

  const cards = [];

  // Scatter chart
  if (HAS_SCATTER && !IS_FORECAST && SCATTER.pts && SCATTER.pts.length > 0) {{
    cards.push(`<div class="chart-card"><div class="cc-label">Scatter · ${{SCATTER.xLabel}} vs ${{SCATTER.yLabel}}</div><div class="chart-canvas-wrap" style="height:${{SCATTER_H}}px"><canvas id="chartScatter"></canvas></div></div>`);
  }}

  // Time series OR forecast
  if (IS_FORECAST && FORECAST.histV && FORECAST.histV.length > 0) {{
    cards.push(`<div class="chart-card"><div class="cc-label">Forecast · ${{FORECAST.label}}</div><div class="chart-canvas-wrap" style="height:${{TS_H}}px"><canvas id="chartForecast"></canvas></div></div>`);
  }} else if (HAS_TS && TS.v && TS.v.length > 0) {{
    cards.push(`<div class="chart-card"><div class="cc-label">Trend · ${{TS.label}} over time</div><div class="chart-canvas-wrap" style="height:${{TS_H}}px"><canvas id="chartTS"></canvas></div></div>`);
  }}

  // Forest / effect chart
  if (!IS_FORECAST) {{
    cards.push(`<div class="chart-card"><div class="cc-label">Effect · 95% confidence interval</div><div class="chart-canvas-wrap" style="height:${{FOREST_H}}px"><canvas id="chartForest"></canvas></div></div>`);
  }}

  if (cards.length === 0) return;

  // Grid layout — inject HTML first, then wait one frame for layout to settle
  const singleCol = cards.length === 1;
  zone.innerHTML = `<div class="charts-row${{singleCol?' single':''}}" style="margin-bottom:24px">${{cards.join('')}}</div>`;

  // requestAnimationFrame ensures the browser has finished laying out the grid
  // before Chart.js reads element dimensions — prevents the elongation/resize loop
  requestAnimationFrame(() => {{
    sizeCanvases();
    renderScatter();
    renderTS();
    renderForecast();
    renderForest();
  }});
}}

/* Set canvas pixel dimensions to match their wrapper before Chart.js touches them */
function sizeCanvases() {{
  ['chartScatter','chartTS','chartForecast','chartForest'].forEach(id => {{
    const el = document.getElementById(id);
    if (!el) return;
    const wrap = el.parentElement;
    if (!wrap) return;
    const w = wrap.clientWidth || 400;
    const h = wrap.clientHeight || 200;
    el.width  = w;
    el.height = h;
    el.style.width  = w + 'px';
    el.style.height = h + 'px';
  }});
}}

function renderScatter() {{
  const el = document.getElementById('chartScatter');
  if (!el || !SCATTER.pts || SCATTER.pts.length === 0) return;

  const unitSet = [...new Set(SCATTER.units || [])].slice(0, 3);
  const unitColors = [C.walnut, C.green, C.gold];
  const ptColor = (i) => {{
    if (!SCATTER.units || SCATTER.units.length === 0) return 'rgba(90,48,24,.35)';
    const u = SCATTER.units[i];
    const idx = unitSet.indexOf(u);
    return (unitColors[idx] || C.walnut) + '55';
  }};

  new Chart(el, {{
    type: 'scatter',
    data: {{
      datasets: [
        {{
          label: 'Observations',
          data: SCATTER.pts,
          pointBackgroundColor: SCATTER.pts.map((_, i) => ptColor(i)),
          pointRadius: Math.max(2, Math.min(5, Math.floor(200 / SCATTER.pts.length))),
          pointBorderWidth: 0,
        }},
        {{
          label: 'Fit',
          data: SCATTER.fit || [],
          type: 'line',
          borderColor: C.gold, borderWidth: 2,
          pointRadius: 0, tension: 0,
        }}
      ]
    }},
    options: baseOpts({{
      plugins: {{ legend: noLegend(), tooltip: {{ callbacks: {{
        label: (ctx) => {{ const d = ctx.raw; return `(${{d.x.toFixed(3)}}, ${{d.y.toFixed(3)}})`; }}
      }} }} }},
      scales: {{
        x: {{ grid: gridLines(), title: {{ display: true, text: SCATTER.xLabel, color: C.faint }} }},
        y: {{ grid: gridLines(), title: {{ display: true, text: SCATTER.yLabel, color: C.faint }} }},
      }}
    }})
  }});
}}

function renderTS() {{
  const el = document.getElementById('chartTS');
  if (!el || !TS.v || TS.v.length === 0) return;

  new Chart(el, {{
    type: 'line',
    data: {{
      labels: TS.t,
      datasets: [{{
        label: TS.label,
        data: TS.v,
        borderColor: C.walnut, backgroundColor: 'rgba(90,48,24,.06)',
        fill: true, tension: 0.25, borderWidth: 2,
        pointRadius: TS.t.length > 80 ? 0 : 3,
        pointBackgroundColor: C.gold,
      }}]
    }},
    options: baseOpts({{
      scales: {{
        x: {{ grid: gridLines() }},
        y: {{ grid: gridLines() }},
      }}
    }})
  }});
}}

function renderForecast() {{
  const el = document.getElementById('chartForecast');
  if (!el || !FORECAST.histV || FORECAST.histV.length === 0) return;

  const allLabels = FORECAST.histT.concat(FORECAST.fcT);
  const nH = FORECAST.histT.length, nF = FORECAST.fcT.length;
  const nullsH = Array(nH).fill(null), nullsF = Array(nF).fill(null);

  new Chart(el, {{
    type: 'line',
    data: {{
      labels: allLabels,
      datasets: [
        {{
          label: 'History',
          data: FORECAST.histV.concat(nullsF),
          borderColor: C.walnut, borderWidth: 2, fill: false, tension: 0.2,
          pointRadius: nH > 60 ? 0 : 2,
        }},
        {{
          label: 'Forecast',
          data: nullsH.concat(FORECAST.fcV),
          borderColor: C.goldL, borderWidth: 2, borderDash: [6, 3],
          fill: false, tension: 0.2,
          pointRadius: 3, pointBackgroundColor: C.goldL,
        }},
        ...(FORECAST.fcLo && FORECAST.fcLo.length > 0 ? [
          {{
            label: '95% lo', data: nullsH.concat(FORECAST.fcLo),
            borderColor: 'rgba(184,134,60,.25)', borderWidth: 1,
            borderDash: [2, 2], fill: false, pointRadius: 0,
          }},
          {{
            label: '95% hi', data: nullsH.concat(FORECAST.fcHi),
            borderColor: 'rgba(184,134,60,.25)', borderWidth: 1,
            borderDash: [2, 2], fill: '-1',
            backgroundColor: 'rgba(184,134,60,.05)', pointRadius: 0,
          }},
        ] : []),
      ]
    }},
    options: baseOpts({{
      plugins: {{ legend: {{ display: true, position: 'bottom', labels: {{ boxWidth: 10, font: {{ size: 10 }} }} }} }},
      scales: {{
        x: {{ grid: gridLines() }},
        y: {{ grid: gridLines() }},
      }}
    }})
  }});
}}

function renderForest() {{
  const el = document.getElementById('chartForest');
  if (!el || FOREST.eff === undefined) return;

  const passesZero = FOREST.lo < 0 && FOREST.hi > 0;
  const barColor = passesZero ? 'rgba(122,96,80,.45)' : (FOREST.eff >= 0 ? 'rgba(45,102,68,.65)' : 'rgba(122,40,40,.65)');

  new Chart(el, {{
    type: 'bar',
    data: {{
      labels: [FOREST.label],
      datasets: [
        {{ label: 'Effect', data: [FOREST.eff], backgroundColor: barColor, borderRadius: 4, barThickness: 20 }},
        {{ label: 'CI lo',  data: [FOREST.lo],  backgroundColor: 'rgba(184,134,60,.3)', borderRadius: 2, barThickness: 6 }},
        {{ label: 'CI hi',  data: [FOREST.hi],  backgroundColor: 'rgba(184,134,60,.3)', borderRadius: 2, barThickness: 6 }},
      ]
    }},
    options: baseOpts({{
      indexAxis: 'y',
      plugins: {{
        legend: noLegend(),
        tooltip: {{ callbacks: {{
          label: (ctx) => {{
            if (ctx.datasetIndex === 0) return `Effect: ${{FOREST.eff.toFixed(4)}}`;
            if (ctx.datasetIndex === 1) return `CI low: ${{FOREST.lo.toFixed(4)}}`;
              return `CI high: ${{FOREST.hi.toFixed(4)}}`;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ grid: gridLines(), ticks: {{ callback: (v) => v.toFixed(3) }} }},
        y: {{ grid: {{ display: false }} }},
      }}
    }}
  }});
}}

/* ── Tabs ── */
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const id = btn.dataset.tab;
    const card = btn.closest('.interp-card');
    card.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    card.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const pane = card.querySelector('#tab-' + id);
    if (pane) pane.classList.add('active');
  }});
}});

/* ── Confidence ring animation ── */
function animateRing() {{
  const circle = document.getElementById('ringCircle');
  if (!circle) return;
  const target = parseFloat(circle.dataset.target);
  setTimeout(() => {{
    circle.style.strokeDashoffset = target;
  }}, 100);
}}

/* ── What-if ── */
let wiChart = null;
function initWhatIf() {{
  const slider = document.getElementById('wiSlider');
  if (!slider) return;
  const valEl  = document.getElementById('wiVal');
  const predEl = document.getElementById('wiPred');
  const ciEl   = document.getElementById('wiCI');
  const dEl    = document.getElementById('wiDelta');

  const p = WHATIF;
  const x0 = p.x_mean !== undefined && p.x_mean !== null ? parseFloat(p.x_mean) : 0;

  // Build mini chart for what-if
  const wiCanvas = document.getElementById('wiChart');
  if (wiCanvas && p.kind === 'regression') {{
    const nPts = 40;
    const lo = parseFloat(slider.min), hi = parseFloat(slider.max);
    const step = (hi - lo) / nPts;
    const labels = Array.from({{length: nPts+1}}, (_, i) => (lo + i * step).toFixed(2));
    const yVals  = labels.map(x => {{
      const xf = parseFloat(x);
      return (p.intercept || 0) + (p.slope || 0) * xf;
    }});
    wiChart = new Chart(wiCanvas, {{
      type: 'line',
      data: {{
        labels,
        datasets: [
          {{
            label: 'Predicted outcome',
            data: yVals,
            borderColor: C.walnut, borderWidth: 1.5,
            fill: false, tension: 0, pointRadius: 0,
          }},
          {{
            label: 'Current',
            data: labels.map(_ => null), // updated live
            pointBackgroundColor: C.goldL,
            pointRadius: 7, showLine: false,
            type: 'scatter',
          }}
        ]
      }},
      options: baseOpts({{
        scales: {{
          x: {{ grid: gridLines(), ticks: {{ maxTicksLimit: 5 }} }},
          y: {{ grid: gridLines(), ticks: {{ maxTicksLimit: 5 }} }},
        }}
      }})
    }});
  }}

  function update() {{
    const x = parseFloat(slider.value);
    if (valEl) valEl.textContent = x.toFixed(2);

    if (p.kind === 'regression') {{
      const yhat     = (p.intercept || 0) + (p.slope || 0) * x;
      const baseline = (p.intercept || 0) + (p.slope || 0) * x0;
      const half     = 1.96 * (p.se || 0) * Math.abs(x - x0);
      if (predEl) predEl.textContent = yhat.toFixed(4);
      if (ciEl)   ciEl.textContent   = `[${{(yhat-half).toFixed(3)}}, ${{(yhat+half).toFixed(3)}}]`;
      if (dEl)    dEl.textContent    = (yhat - baseline >= 0 ? '+' : '') + (yhat - baseline).toFixed(4);

      // Update scatter dot on mini chart
      if (wiChart) {{
        const labels = wiChart.data.labels;
        const idx = labels.findIndex(l => parseFloat(l) >= x);
        const newPts = labels.map((_, i) => i === idx ? {{x: x.toFixed(2), y: yhat}} : null);
        wiChart.data.datasets[1].data = newPts;
        wiChart.update('none');
      }}
    }} else if (p.kind === 'forecast') {{
      const shock = parseFloat(slider.value);
      const next  = ((p.forecasts && p.forecasts[0]) || p.last_value || 0) + shock;
      const ar1   = p.ar1 !== undefined ? p.ar1.toFixed(3) : '—';
      if (valEl)  valEl.textContent  = shock.toFixed(2);
      if (predEl) predEl.textContent = next.toFixed(4);
      if (dEl)    dEl.textContent    = ar1;
    }}
  }}

  slider.addEventListener('input', update);
  update();
}}

/* ── Init ── */
window.addEventListener('DOMContentLoaded', () => {{
  animateRing();
  buildCharts();
  initWhatIf();
}});
</script>
</body>
</html>"""
