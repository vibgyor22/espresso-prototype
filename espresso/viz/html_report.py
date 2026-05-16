"""
Self-contained, professional HTML dashboard.

Built from a `Session`. Never auto-generated — created only when the user
types `export` (REPL) or passes `--export` (one-shot). Single file, no
external requests: Chart.js is the only dependency and we load it from a
public CDN once with `crossorigin`. If you want fully air-gapped output, swap
the CDN line for an inlined script.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from ..whatif import html_payload


PALETTE = {
    "primary":   "#6F4E37",
    "secondary": "#A67C52",
    "light":     "#D4A574",
    "cream":     "#F5E6D3",
    "dark":      "#3E2723",
    "accent":    "#8D6E63",
    "bg":        "#FFFBF5",
    "ok":        "#2E7D32",
    "warn":      "#F9A825",
    "fail":      "#C62828",
    "ink":       "#1F1B16",
    "ink2":      "#5B4636",
}


def create_html_report(session, output_path: str | None = None) -> str:
    """
    Render the session's full analysis to a single HTML file. Returns the path.
    """
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
# Build helpers
# ---------------------------------------------------------------------------

def _build_html(s) -> str:
    intent = s.intent or {}
    result = s.result or {}
    blocks = s.interpretation_blocks or {}
    profile = s.profile

    payload = html_payload(result, s.model_key) if result else {"kind": "none"}

    title = intent.get("question") or s.question or "Espresso analysis"
    subtitle_bits = []
    if s.source_path:
        subtitle_bits.append(f"Source · <code>{_h(s.source_path)}</code>")
    if s.sheet:
        subtitle_bits.append(f"Sheet · <code>{_h(s.sheet)}</code>")
    if profile:
        subtitle_bits.append(f"{profile.n_rows:,} rows × {profile.n_cols} cols · {profile.structure}")
    if s.model_display:
        subtitle_bits.append(f"Model · <strong>{_h(s.model_display)}</strong>")
    subtitle = " &nbsp;·&nbsp; ".join(subtitle_bits)

    timeline_html = _timeline_html(s.history or [])
    profile_html = _profile_html(profile)
    interp_html = _interpretation_html(blocks)
    diag_html = _diagnostics_html(s.diagnostics or {})
    result_html = _result_html(s.model_key, result)
    followups_html = _followups_html(s.followups or [])
    chart_section, chart_init = _chart_html(s.model_key, result)
    whatif_section, whatif_js = _whatif_html(payload, intent)

    return _PAGE.format(
        title=_h(title),
        subtitle=subtitle,
        palette_json=json.dumps(PALETTE),
        timeline=timeline_html,
        profile=profile_html,
        diagnostics=diag_html,
        results=result_html,
        chart=chart_section,
        interpretation=interp_html,
        whatif=whatif_section,
        followups=followups_html,
        question=_h(title),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        chart_init=chart_init,
        whatif_js=whatif_js,
        payload=json.dumps(payload),
    )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _timeline_html(history) -> str:
    if not history:
        return ""
    rows = []
    for step in history:
        if step.kind == "thought":
            continue
        tool = step.tool or step.kind
        preview = _h(step.result_preview or "")
        why = _h(step.justification or "")
        status_class = step.status or "ok"
        rows.append(
            f'<li class="step status-{status_class}">'
            f'<div class="step-head"><span class="tool">{_h(tool)}</span>'
            f'<span class="status">{_h(step.status)}</span></div>'
            f'<div class="step-preview">{preview}</div>'
            f'<div class="step-why">{why}</div></li>'
        )
    return f'<ol class="timeline">{"".join(rows)}</ol>'


def _profile_html(profile) -> str:
    if profile is None:
        return ""
    rows = []
    for c in profile.columns[:60]:
        if c.min is not None and c.max is not None:
            r = f"[{c.min:.4g} … {c.max:.4g}]"
        elif c.top_values:
            r = ", ".join(f"{_h(str(t['value']))} ({t['count']})" for t in c.top_values[:3])
        elif c.sample_values:
            r = ", ".join(map(lambda x: _h(str(x)), c.sample_values[:3]))
        else:
            r = ""
        rows.append(
            f"<tr><td><strong>{_h(c.name)}</strong></td>"
            f"<td>{_h(c.semantic_type)}</td>"
            f"<td>{c.n_unique:,}</td>"
            f"<td>{c.missing_pct:.1f}%</td>"
            f"<td>{r}</td></tr>"
        )
    notes = "".join(f"<li>{_h(n)}</li>" for n in profile.notes)
    notes_html = f'<ul class="notes">{notes}</ul>' if notes else ""
    return f"""
      <table class="profile">
        <thead><tr><th>Column</th><th>Type</th><th>Unique</th><th>Missing</th><th>Range / Top</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      {notes_html}
    """


def _diagnostics_html(diag: dict) -> str:
    if not diag:
        return "<p class='muted'>No diagnostics recorded.</p>"
    if "error" in diag:
        return f"<div class='fail'>Diagnostics error: {_h(diag['error'])}</div>"
    rows = []
    for ch in diag.get("checks", []):
        if "error" in ch:
            rows.append(f"<tr><td>⚠️</td><td>{_h(ch.get('test', ''))}</td><td>{_h(ch['error'])}</td></tr>")
        else:
            ok = not ch.get("is_violated")
            mark = "✓" if ok else "✗"
            cls = "ok" if ok else "fail"
            rows.append(
                f"<tr class='{cls}'><td>{mark}</td>"
                f"<td>{_h(ch.get('test', ''))}</td>"
                f"<td>{_h(ch.get('interpretation', ''))}</td></tr>"
            )
    v = diag.get("violations", [])
    cor = diag.get("corrections", [])
    badges = ""
    if v:
        badges += f"<div class='badge fail'>Violations: {_h('; '.join(v))}</div>"
    if cor:
        badges += f"<div class='badge ok'>Corrections: {_h('; '.join(cor))}</div>"
    return f"""
      <table class='diag'>
        <thead><tr><th></th><th>Check</th><th>What it means</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      {badges}
    """


def _result_html(model_key: str, result: dict) -> str:
    if not result:
        return "<p class='muted'>No result produced.</p>"
    if result.get("forecasts"):
        fc = result["forecasts"]
        rows = []
        lo = result.get("ci_lower", []) or []
        hi = result.get("ci_upper", []) or []
        times = result.get("forecast_times", list(range(1, len(fc) + 1)))
        for i, f in enumerate(fc):
            ci = f"[{lo[i]:.3f}, {hi[i]:.3f}]" if i < len(lo) and i < len(hi) else "—"
            rows.append(f"<tr><td>{times[i]}</td><td>{f:.4f}</td><td>{ci}</td></tr>")
        meta = (
            f"<div class='kv'><span>AIC</span><strong>{result.get('aic', '—')}</strong></div>"
            f"<div class='kv'><span>RMSE</span><strong>{result.get('rmse', 0):.4f}</strong></div>"
            f"<div class='kv'><span>N</span><strong>{result.get('n_obs', 0):,}</strong></div>"
            f"<div class='kv'><span>Engine</span><strong>{_h(result.get('engine', '—'))}</strong></div>"
        )
        return f"""
          <div class='metrics'>{meta}</div>
          <table class='result'>
            <thead><tr><th>Period</th><th>Forecast</th><th>95% CI</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        """

    eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    se = result.get("se", 0) or 0
    pval = result.get("pvalue", result.get("p_value", 1)) or 1
    ci_lo = result.get("ci_lower", eff - 1.96 * se)
    ci_hi = result.get("ci_upper", eff + 1.96 * se)
    r2 = result.get("r_squared", 0) or 0
    n = result.get("n_obs", 0)
    sig = (
        "p&lt;0.001 ***" if pval < 0.001 else
        "p&lt;0.01 **" if pval < 0.01 else
        "p&lt;0.05 *" if pval < 0.05 else
        "n.s."
    )
    return f"""
      <div class='metrics'>
        <div class='kv'><span>Effect</span><strong>{eff:,.4f}</strong></div>
        <div class='kv'><span>SE</span><strong>{se:,.4f}</strong></div>
        <div class='kv'><span>95% CI</span><strong>[{ci_lo:,.3f}, {ci_hi:,.3f}]</strong></div>
        <div class='kv'><span>p-value</span><strong>{pval:.4f} <em>{sig}</em></strong></div>
        <div class='kv'><span>R²</span><strong>{r2:.4f}</strong></div>
        <div class='kv'><span>N</span><strong>{n:,}</strong></div>
      </div>
    """


def _chart_html(model_key: str, result: dict) -> tuple[str, str]:
    """Returns (html_section, js_init_snippet)."""
    if not result:
        return "", ""

    if result.get("forecasts"):
        hist_y = result.get("historical_values", []) or []
        hist_t = result.get("historical_times", []) or list(range(len(hist_y)))
        fc_y = result.get("forecasts", []) or []
        fc_t = result.get("forecast_times", []) or list(range(len(hist_y), len(hist_y) + len(fc_y)))
        lo = result.get("ci_lower", []) or []
        hi = result.get("ci_upper", []) or []
        data = {
            "hist_t": [str(x) for x in hist_t],
            "hist_y": list(map(float, hist_y)),
            "fc_t": [str(x) for x in fc_t],
            "fc_y": list(map(float, fc_y)),
            "lo": list(map(float, lo)),
            "hi": list(map(float, hi)),
        }
        return (
            '<canvas id="chartMain" height="120"></canvas>',
            f"renderForecastChart(document.getElementById('chartMain'), {json.dumps(data)});"
        )

    eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    se = result.get("se", 0) or 0
    lo = result.get("ci_lower", eff - 1.96 * se)
    hi = result.get("ci_upper", eff + 1.96 * se)
    data = {"label": "Effect", "eff": float(eff), "lo": float(lo), "hi": float(hi)}
    return (
        '<canvas id="chartMain" height="80"></canvas>',
        f"renderEffectChart(document.getElementById('chartMain'), {json.dumps(data)});"
    )


def _interpretation_html(blocks: dict) -> str:
    if not blocks:
        return "<p class='muted'>No interpretation available.</p>"
    titles = [
        ("why_columns", "1 · Why these columns"),
        ("why_model", "2 · Why this model"),
        ("statistical", "3 · Statistical result"),
        ("domain", "4a · What this data is about"),
        ("past_trends", "4b · Past trends in the data"),
        ("news_context", "4c · Real-world context"),
        ("literature", "4d · What the literature finds"),
        ("sanity_check", "4e · Sanity check"),
    ]
    out = []
    for key, title in titles:
        text = (blocks.get(key) or "").strip()
        if not text:
            continue
        out.append(f"<section class='interp'><h3>{_h(title)}</h3><div>{_md_inline(text)}</div></section>")
    return "".join(out)


def _followups_html(items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_h(q)}</li>" for q in items)
    return f"<ol class='followups'>{lis}</ol>"


def _whatif_html(payload: dict, intent: dict) -> tuple[str, str]:
    if payload.get("kind") == "regression":
        label = _h(intent.get("treatment", "predictor"))
        out_label = _h(intent.get("outcome", "outcome"))
        # Build a sensible slider range using x_mean if we have it
        x0 = payload.get("x_mean") or 0
        try:
            x0f = float(x0)
        except Exception:
            x0f = 0.0
        return (
            f"""
            <div class='whatif-card'>
              <div class='whatif-controls'>
                <label>If <strong>{label}</strong> were:
                  <input id='whatifSlider' type='range' min='{x0f-100}' max='{x0f+100}' step='0.5' value='{x0f}'>
                  <output id='whatifValue'>{x0f:.2f}</output>
                </label>
              </div>
              <div class='whatif-readout'>
                <div><span>Predicted {out_label}</span><strong id='whatifPred'>—</strong></div>
                <div><span>95% CI</span><strong id='whatifCI'>—</strong></div>
                <div><span>Δ vs baseline</span><strong id='whatifDelta'>—</strong></div>
              </div>
            </div>
            """,
            "initWhatIfRegression();",
        )
    if payload.get("kind") == "forecast":
        return (
            """
            <div class='whatif-card'>
              <div class='whatif-controls'>
                <label>Shock to most-recent value:
                  <input id='whatifSlider' type='range' min='-10' max='10' step='0.1' value='0'>
                  <output id='whatifValue'>0.00</output>
                </label>
              </div>
              <div class='whatif-readout'>
                <div><span>Shifted next-period forecast</span><strong id='whatifPred'>—</strong></div>
                <div><span>Decay rate (AR1)</span><strong id='whatifDelta'>—</strong></div>
              </div>
              <canvas id='whatifChart' height='90'></canvas>
            </div>
            """,
            "initWhatIfForecast();",
        )
    return "", ""


# ---------------------------------------------------------------------------
# small helpers
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


def _md_inline(text: str) -> str:
    # Tiny: bold **x**, italic *x*, newlines→<br>
    t = _h(text)
    import re
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = t.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<p>{t}</p>"


# ---------------------------------------------------------------------------
# Page template
# ---------------------------------------------------------------------------

_PAGE = """<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<title>{title} · Espresso</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<style>
  :root {{
    --primary:#6F4E37; --secondary:#A67C52; --light:#D4A574;
    --cream:#F5E6D3; --dark:#3E2723; --accent:#8D6E63;
    --bg:#FFFBF5; --ok:#2E7D32; --warn:#F9A825; --fail:#C62828;
    --ink:#1F1B16; --ink2:#5B4636;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font:15px/1.55 'Helvetica Neue',system-ui,-apple-system,sans-serif;
         color:var(--ink); background:var(--bg); }}
  header.top {{ padding:28px 36px 18px; background:linear-gradient(135deg,var(--primary),var(--dark));
                color:#FAF6EE; box-shadow:0 6px 18px rgba(0,0,0,.08); }}
  header.top .brand {{ font-size:13px; letter-spacing:2px; text-transform:uppercase; opacity:.75; }}
  header.top h1 {{ margin:6px 0 4px; font-size:28px; font-weight:700; }}
  header.top .sub {{ font-size:13px; opacity:.85; }}
  main {{ max-width:1100px; margin:0 auto; padding:24px 28px 80px; }}
  section.card {{ background:#fff; border:1px solid #EAD9C2; border-radius:14px;
                  padding:20px 24px; margin:18px 0; box-shadow:0 2px 10px rgba(110,78,55,.04); }}
  section.card h2 {{ margin:0 0 12px; color:var(--primary); font-size:18px; letter-spacing:.3px; }}
  .muted {{ color:#9c8675; font-style:italic; }}
  .grid {{ display:grid; gap:18px; }}
  .grid-2 {{ grid-template-columns: 1fr 1fr; }}
  @media (max-width:900px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .metrics {{ display:flex; flex-wrap:wrap; gap:18px; }}
  .kv {{ background:var(--cream); padding:10px 14px; border-radius:10px; min-width:120px; }}
  .kv span {{ display:block; font-size:11px; text-transform:uppercase; color:var(--ink2); letter-spacing:1px; }}
  .kv strong {{ font-size:18px; color:var(--dark); }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #f0e2cf; }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--ink2); }}
  table.result td:not(:first-child), table.profile td:nth-child(3), table.profile td:nth-child(4)
    {{ font-variant-numeric: tabular-nums; }}
  table.diag tr.ok td:first-child {{ color: var(--ok); font-weight:bold; }}
  table.diag tr.fail td:first-child {{ color: var(--fail); font-weight:bold; }}
  .badge {{ display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; margin:8px 8px 0 0; }}
  .badge.ok {{ background:#E8F5E9; color:var(--ok); }}
  .badge.fail {{ background:#FFEBEE; color:var(--fail); }}
  ol.timeline {{ list-style:none; padding:0; margin:0; }}
  ol.timeline li.step {{ border-left:3px solid var(--light); padding:8px 12px; margin:4px 0; background:#FFFBF5; border-radius:6px; }}
  ol.timeline li.step.status-error {{ border-color:var(--fail); }}
  ol.timeline .step-head {{ display:flex; justify-content:space-between; }}
  ol.timeline .tool {{ font-weight:700; color:var(--primary); }}
  ol.timeline .status {{ font-size:11px; text-transform:uppercase; color:var(--ink2); }}
  ol.timeline .step-preview {{ font-size:13px; color:var(--ink); }}
  ol.timeline .step-why {{ font-size:12px; color:var(--ink2); font-style:italic; margin-top:2px; }}
  .interp {{ background:#FFFCF7; border-left:4px solid var(--light); padding:12px 16px; margin:12px 0; border-radius:0 8px 8px 0; }}
  .interp h3 {{ margin:0 0 6px; color:var(--primary); font-size:14px; letter-spacing:.4px; }}
  .interp p {{ margin:6px 0; }}
  ol.followups {{ background:var(--cream); padding:14px 28px; border-radius:10px; }}
  ol.followups li {{ padding:4px 0; }}
  .whatif-card {{ background:linear-gradient(135deg,#fff,#FFFBF5); border:1px dashed var(--light); border-radius:12px; padding:18px 22px; }}
  .whatif-controls input[type=range] {{ width:60%; vertical-align:middle; }}
  .whatif-controls output {{ display:inline-block; min-width:60px; font-weight:700; color:var(--primary); }}
  .whatif-readout {{ display:flex; gap:24px; margin-top:14px; flex-wrap:wrap; }}
  .whatif-readout div {{ background:var(--cream); padding:8px 14px; border-radius:8px; min-width:140px; }}
  .whatif-readout span {{ display:block; font-size:11px; text-transform:uppercase; color:var(--ink2); }}
  .whatif-readout strong {{ font-size:18px; color:var(--primary); }}
  footer {{ text-align:center; color:var(--ink2); padding:24px 0; font-size:12px; }}
  code {{ background:#F5E6D3; padding:1px 5px; border-radius:4px; font-size:12px; }}
</style>
</head>
<body>
<header class='top'>
  <div class='brand'>Espresso · Agentic Econometric Analyst</div>
  <h1>{title}</h1>
  <div class='sub'>{subtitle}</div>
</header>
<main>

  <section class='card'>
    <h2>What we did and why</h2>
    {timeline}
  </section>

  <div class='grid grid-2'>
    <section class='card'>
      <h2>Data profile</h2>
      {profile}
    </section>
    <section class='card'>
      <h2>Pre-analysis diagnostics</h2>
      {diagnostics}
    </section>
  </div>

  <section class='card'>
    <h2>Result</h2>
    {results}
    {chart}
  </section>

  <section class='card'>
    <h2>Interpretation</h2>
    {interpretation}
  </section>

  <section class='card'>
    <h2>What-if scenarios</h2>
    <p class='muted'>Move the slider to see how the prediction shifts. Math runs in your browser from the model's stored coefficients — nothing is sent anywhere.</p>
    {whatif}
  </section>

  <section class='card'>
    <h2>Suggested follow-ups</h2>
    {followups}
  </section>

  <footer>
    <div>Generated by Espresso · <strong>{generated_at}</strong></div>
    <div style='margin-top:6px;opacity:.7'>Statistical estimates are deterministic. Qualitative context (news, literature) is LLM-generated narrative and should not be cited verbatim.</div>
  </footer>
</main>

<script>
const PAYLOAD = {payload};
const PALETTE = {palette_json};

function renderForecastChart(canvas, d) {{
  const histLabels = d.hist_t;
  const fcLabels = d.fc_t;
  const labels = histLabels.concat(fcLabels);
  const histData = d.hist_y.concat(new Array(d.fc_y.length).fill(null));
  const fcData = new Array(d.hist_y.length).fill(null).concat(d.fc_y);
  const loData = new Array(d.hist_y.length).fill(null).concat(d.lo);
  const hiData = new Array(d.hist_y.length).fill(null).concat(d.hi);
  new Chart(canvas, {{
    type: 'line',
    data: {{ labels, datasets: [
      {{ label: 'History', data: histData, borderColor: PALETTE.primary, backgroundColor: 'transparent', tension:.2 }},
      {{ label: 'Forecast', data: fcData, borderColor: PALETTE.secondary, backgroundColor:'transparent', borderDash:[6,4], tension:.2 }},
      {{ label: '95% lo', data: loData, borderColor: PALETTE.light, backgroundColor:'transparent', borderDash:[2,2], pointRadius:0 }},
      {{ label: '95% hi', data: hiData, borderColor: PALETTE.light, backgroundColor:'transparent', borderDash:[2,2], pointRadius:0 }},
    ]}},
    options: {{ responsive:true, plugins:{{ legend:{{ position:'bottom' }} }} }}
  }});
}}

function renderEffectChart(canvas, d) {{
  new Chart(canvas, {{
    type: 'bar',
    data: {{ labels: [d.label], datasets: [
      {{ label:'Effect', data: [d.eff], backgroundColor: PALETTE.primary }},
      {{ label:'CI low', data: [d.lo], backgroundColor: 'transparent', borderColor: PALETTE.secondary, borderWidth:2, type:'line' }},
      {{ label:'CI high', data: [d.hi], backgroundColor: 'transparent', borderColor: PALETTE.secondary, borderWidth:2, type:'line' }},
    ]}},
    options: {{ indexAxis:'y', responsive:true, plugins:{{ legend:{{ position:'bottom' }} }} }}
  }});
}}

function initWhatIfRegression() {{
  const slider = document.getElementById('whatifSlider');
  const out = document.getElementById('whatifValue');
  const pred = document.getElementById('whatifPred');
  const ci   = document.getElementById('whatifCI');
  const dEl  = document.getElementById('whatifDelta');
  const p = PAYLOAD;
  function update() {{
    const x = parseFloat(slider.value);
    const yhat = p.intercept + p.slope * x;
    const x0 = (p.x_mean !== null && p.x_mean !== undefined) ? p.x_mean : 0;
    const baseline = p.intercept + p.slope * x0;
    const half = 1.96 * p.se * Math.abs(x - x0);
    out.value = x.toFixed(2);
    pred.textContent = yhat.toFixed(3);
    ci.textContent = `[${{(yhat - half).toFixed(3)}}, ${{(yhat + half).toFixed(3)}}]`;
    dEl.textContent = (yhat - baseline >= 0 ? '+' : '') + (yhat - baseline).toFixed(3);
  }}
  slider.addEventListener('input', update);
  update();
}}

function initWhatIfForecast() {{
  const slider = document.getElementById('whatifSlider');
  const out = document.getElementById('whatifValue');
  const pred = document.getElementById('whatifPred');
  const dEl  = document.getElementById('whatifDelta');
  const p = PAYLOAD;
  function update() {{
    const shock = parseFloat(slider.value);
    const next = (p.forecasts && p.forecasts[0] !== undefined ? p.forecasts[0] : p.last_value) + shock;
    out.value = shock.toFixed(2);
    pred.textContent = next.toFixed(4);
    dEl.textContent = (p.ar1 || 0).toFixed(3);
  }}
  slider.addEventListener('input', update);
  update();
}}

document.addEventListener('DOMContentLoaded', () => {{
  try {{ {chart_init} }} catch (e) {{ console.error(e); }}
  try {{ {whatif_js} }} catch (e) {{ console.error(e); }}
}});
</script>
</body>
</html>
"""
