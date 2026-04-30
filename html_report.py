"""
HTML report generator for Espresso.

Supports all four model types:
  - ARIMA            (time-series chart with confidence bands)
  - Difference-in-Differences (coefficient plot with CI)
  - Panel OLS        (same layout as DiD, different labelling)
  - OLS              (scatter + regression line)
"""

import os
import json
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COLORS = {
    'primary':   '#6F4E37',
    'secondary': '#A67C52',
    'light':     '#D4A574',
    'cream':     '#F5E6D3',
    'dark':      '#3E2723',
    'accent':    '#8D6E63',
    'bg':        '#FFFBF5',
    'ok':        '#4CAF50',
    'fail':      '#FF5722',
}

C = COLORS  # shorthand


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_html_report(output_path, intent, mapping, model_results, data_sample=None):
    """
    Write a self-contained HTML report to `output_path`.

    Returns the path that was written.
    """
    question_text = intent.get('question', intent.get('outcome', 'Analysis'))
    unit_name = intent.get('identified_unit')

    model_sections_html = ""
    for result in model_results:
        model_name = result.get('model', '')
        interp_raw = result.get('llm_interpretation', '')
        interp_raw = interp_raw.replace('**', '').replace('*', '')
        interp_html = _format_interpretation(interp_raw)

        if result.get('forecasts'):
            model_sections_html += _arima_section(result, interp_html)
        elif 'Difference-in-Differences' in model_name:
            model_sections_html += _regression_section(result, interp_html, 'DiD')
        elif 'Panel OLS' in model_name:
            model_sections_html += _regression_section(result, interp_html, 'Panel OLS')
        elif model_name == 'OLS':
            model_sections_html += _regression_section(result, interp_html, 'OLS')
        elif result.get('effect') is not None:
            model_sections_html += _regression_section(result, interp_html, model_name)

    unit_banner = ''
    if unit_name:
        unit_banner = f'''
        <div style="margin-top:20px;padding:15px;background:{C['cream']};
                    border-left:4px solid {C['primary']};border-radius:4px;">
          <strong style="color:{C['primary']};">Unit of Analysis:</strong>
          <span style="font-size:1.1em;font-weight:600;margin-left:8px;">{unit_name}</span>
        </div>'''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Espresso Analysis Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box;}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
          background:linear-gradient(135deg,{C['bg']} 0%,{C['cream']} 100%);
          color:{C['dark']};line-height:1.7;padding:20px;}}
    .container{{max-width:1200px;margin:0 auto;background:white;
                box-shadow:0 10px 50px rgba(62,39,35,.12);border-radius:16px;overflow:hidden;}}
    .header{{background:linear-gradient(135deg,{C['primary']} 0%,{C['secondary']} 100%);
             color:white;padding:50px 40px;text-align:center;}}
    .header h1{{font-size:2.8em;margin-bottom:15px;font-weight:700;letter-spacing:-.5px;}}
    .header .subtitle{{font-size:1.2em;opacity:.95;font-weight:300;}}
    .section{{padding:40px;}}
    .section-title{{font-size:2em;color:{C['primary']};margin-bottom:25px;
                    padding-bottom:15px;border-bottom:3px solid {C['cream']};font-weight:600;}}
    .interpretation{{background:{C['bg']};border-left:4px solid {C['secondary']};
                     padding:30px;margin:25px 0;border-radius:8px;font-size:1.05em;}}
    .interpretation h3{{color:{C['primary']};font-size:1.4em;margin-bottom:20px;font-weight:600;}}
    .interpretation-content{{color:{C['dark']};line-height:1.9;}}
    .interpretation-content > div{{margin-bottom:20px;}}
    .interpretation-content .answer{{background:white;padding:20px;border-radius:6px;
                                     border:2px solid {C['light']};margin-bottom:20px;
                                     font-size:1.1em;font-weight:500;color:{C['primary']};}}
    .interpretation-content ul{{list-style:none;padding-left:0;}}
    .interpretation-content li{{padding:8px 0 8px 25px;position:relative;line-height:1.8;}}
    .interpretation-content li:before{{content:'';position:absolute;left:0;top:15px;
                                        width:8px;height:8px;background:{C['secondary']};border-radius:50%;}}
    .chart-container{{margin:30px 0;padding:25px;background:white;
                      border-radius:8px;border:1px solid {C['cream']};}}
    .chart-title{{font-size:1.3em;color:{C['primary']};margin-bottom:20px;font-weight:600;}}
    .stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:20px;margin:25px 0;}}
    .stat-card{{background:linear-gradient(135deg,{C['cream']} 0%,white 100%);
                padding:20px;border-radius:8px;border:1px solid {C['light']};}}
    .stat-label{{font-size:.9em;color:{C['secondary']};text-transform:uppercase;
                 letter-spacing:.5px;margin-bottom:8px;font-weight:600;}}
    .stat-value{{font-size:1.7em;color:{C['primary']};font-weight:700;}}
    .forecast-table{{width:100%;border-collapse:collapse;margin:25px 0;background:white;
                     border-radius:8px;overflow:hidden;border:1px solid {C['cream']};}}
    .forecast-table th{{background:{C['primary']};color:white;padding:15px;
                        text-align:left;font-weight:600;}}
    .forecast-table td{{padding:12px 15px;border-bottom:1px solid {C['cream']};}}
    .forecast-table tr:last-child td{{border-bottom:none;}}
    .forecast-table tr:hover{{background:{C['bg']};}}
    .diagnostics-box{{background:{C['cream']};padding:20px;border-radius:8px;margin:20px 0;}}
    .diagnostics-box h4{{color:{C['primary']};margin-bottom:15px;}}
    .badge-ok{{color:{C['ok']};font-weight:600;}}
    .badge-fail{{color:{C['fail']};font-weight:600;}}
    .meta-badge{{display:inline-block;padding:4px 10px;border-radius:12px;font-size:.85em;
                 font-weight:600;margin-right:6px;margin-bottom:6px;}}
    .meta-badge.fe{{background:{C['cream']};color:{C['primary']};border:1px solid {C['light']};}}
    .meta-badge.se{{background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7;}}
    .timestamp{{text-align:center;padding:20px;color:{C['secondary']};font-size:.9em;}}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>☕ Espresso Analysis Report</h1>
      <div class="subtitle">Statistical Analysis &amp; Interpretation</div>
    </div>

    <div class="section">
      <h2 class="section-title">Research Question</h2>
      <div style="font-size:1.2em;color:{C['dark']};padding:20px;background:{C['bg']};border-radius:8px;">
        "{question_text}"
      </div>
      {unit_banner}
    </div>

    {model_sections_html}

    <div class="timestamp">
      Report generated on {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}
    </div>
  </div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------

def _arima_section(result, interp_html):
    forecasts      = result.get('forecasts', [])
    forecast_times = result.get('forecast_times', [])
    hist_vals      = result.get('historical_values', [])
    hist_times     = result.get('historical_times', [])
    ci_lower       = result.get('ci_lower', [])
    ci_upper       = result.get('ci_upper', [])
    ar1_coef       = result.get('ar1_coef', 0)
    rmse           = result.get('rmse', 0) or 0
    n_obs          = result.get('n_obs', 0)
    order          = result.get('arima_order', (1, 0, 0))
    engine         = result.get('engine', '')
    aic            = result.get('aic')
    n_fc           = len(forecasts)

    # Chart data
    all_times  = [int(t) for t in hist_times] + [int(t) for t in forecast_times]
    hist_plot  = list(hist_vals) + [None] * n_fc
    fc_plot    = [None] * len(hist_vals) + list(forecasts)
    # Confidence band (only over forecast horizon)
    band_lo    = [None] * len(hist_vals) + (ci_lower if ci_lower else [None] * n_fc)
    band_hi    = [None] * len(hist_vals) + (ci_upper if ci_upper else [None] * n_fc)

    # Forecast table rows
    rows = ""
    for i, (t, fc) in enumerate(zip(forecast_times, forecasts)):
        lo = f"{ci_lower[i]:,.4f}" if ci_lower else "—"
        hi = f"{ci_upper[i]:,.4f}" if ci_upper else "—"
        rows += (
            f"<tr><td>t+{i+1}</td><td>{int(t)}</td>"
            f"<td style='font-weight:600;color:{C['primary']}'>{fc:,.4f}</td>"
            f"<td>{lo}</td><td>{hi}</td></tr>"
        )

    aic_str = f"{aic:.1f}" if aic is not None else "N/A"
    engine_badge = f"<span class='meta-badge se'>{engine}</span>"

    title = result.get('model', f'ARIMA{order}')
    section_title = title if 'forecast' in title.lower() else f'{title} Forecast'
    chart_title = 'Time Series with Forecast and 95% Confidence Band'
    return f"""
  <div class="section">
    <h2 class="section-title">{section_title}</h2>
    <div style="margin-bottom:16px;">{engine_badge}</div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Model</div>
        <div class="stat-value" style="font-size:1.3em;">{title}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AIC</div>
        <div class="stat-value">{aic_str}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">RMSE</div>
        <div class="stat-value">{rmse:,.4f}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Observations</div>
        <div class="stat-value">{n_obs:,}</div>
      </div>
    </div>

    <div class="chart-container">
      <div class="chart-title">{chart_title}</div>
      <canvas id="arimaChart" height="100"></canvas>
    </div>

    <div class="chart-container">
      <div class="chart-title">Forecast Table ({n_fc} Periods)</div>
      <table class="forecast-table">
        <thead>
          <tr>
            <th>Period</th><th>Year</th>
            <th>Forecast</th><th>95% CI Lower</th><th>95% CI Upper</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div class="interpretation">
      <h3>Interpretation</h3>
      <div class="interpretation-content">{interp_html}</div>
    </div>
  </div>

  <script>
  (function(){{
    const ctx = document.getElementById('arimaChart').getContext('2d');
    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: {json.dumps(all_times)},
        datasets: [
          {{
            label: 'Historical',
            data: {json.dumps(hist_plot)},
            borderColor: '{C['primary']}',
            backgroundColor: 'rgba(111,78,55,0.08)',
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: '{C['primary']}',
            fill: false,
            tension: 0.3,
            spanGaps: false
          }},
          {{
            label: 'Forecast',
            data: {json.dumps(fc_plot)},
            borderColor: '{C['secondary']}',
            backgroundColor: 'rgba(166,124,82,0.08)',
            borderWidth: 2.5,
            borderDash: [8, 4],
            pointRadius: 4,
            pointBackgroundColor: '{C['secondary']}',
            fill: false,
            tension: 0.3,
            spanGaps: false
          }},
          {{
            label: '95% CI Upper',
            data: {json.dumps(band_hi)},
            borderColor: 'rgba(166,124,82,0.3)',
            backgroundColor: 'rgba(166,124,82,0.12)',
            borderWidth: 1,
            pointRadius: 0,
            fill: '+1',
            tension: 0.3,
            spanGaps: false
          }},
          {{
            label: '95% CI Lower',
            data: {json.dumps(band_lo)},
            borderColor: 'rgba(166,124,82,0.3)',
            backgroundColor: 'rgba(166,124,82,0.12)',
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            spanGaps: false
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {{
          legend: {{
            position: 'top',
            labels: {{
              filter: (item) => !item.text.includes('CI '),
              font: {{size:13, weight:'600'}},
              color: '{C['dark']}'
            }}
          }},
          tooltip: {{
            backgroundColor: 'rgba(62,39,35,0.9)',
            titleFont: {{size:13,weight:'600'}},
            bodyFont: {{size:12}},
            padding: 10
          }}
        }},
        scales: {{
          x: {{
            title: {{display:true, text:'Year', font:{{size:13,weight:'600'}}, color:'{C['dark']}'}},
            grid: {{color:'rgba(111,78,55,0.08)'}}
          }},
          y: {{
            title: {{display:true, text:'Value', font:{{size:13,weight:'600'}}, color:'{C['dark']}'}},
            grid: {{color:'rgba(111,78,55,0.08)'}}
          }}
        }}
      }}
    }});
  }})();
  </script>
"""


def _regression_section(result, interp_html, section_type='DiD'):
    effect   = result.get('effect', 0) or 0
    se       = result.get('se', 0) or 0
    pval     = result.get('p_value', 1) or 1
    r_sq     = result.get('r_squared', 0) or 0
    n_obs    = result.get('n_obs', 0)
    ci_lo    = result.get('ci_lower', effect - 1.96 * se)
    ci_hi    = result.get('ci_upper', effect + 1.96 * se)
    fe_type  = result.get('fe_type', '')
    se_type  = result.get('se_type', '')
    n_units  = result.get('n_units')
    n_periods= result.get('n_periods')

    is_sig = pval < 0.05
    sig_color = C['ok'] if is_sig else C['fail']
    sig_label = "Yes ✓" if is_sig else "No ✗"

    titles = {
        'DiD':       'Difference-in-Differences Analysis (TWFE)',
        'Panel OLS': 'Panel OLS Analysis (Two-Way FE)',
        'OLS':       'OLS Regression',
    }
    chart_id = ''.join(ch if ch.isalnum() else '_' for ch in section_type)
    effect_label = 'Causal Effect' if section_type == 'DiD' else 'Coefficient'

    fe_badge = f"<span class='meta-badge fe'>{fe_type}</span>" if fe_type else ''
    se_badge = f"<span class='meta-badge se'>{se_type}</span>" if se_type else ''

    # CI chart data — bar-like representation using scatter
    chart_labels = ['Lower CI', 'Estimate', 'Upper CI']
    chart_data   = [ci_lo, effect, ci_hi]

    # Diagnostics box
    diag_html = ''
    diag = result.get('diagnostics', {})
    violations = diag.get('violations', [])
    corrections = diag.get('corrections', [])
    if violations:
        v_items = ''.join(f"<li class='badge-fail'>✗ {v}</li>" for v in violations)
        c_items = ''.join(f"<li>{c}</li>" for c in corrections)
        diag_html = f"""
      <div class="diagnostics-box">
        <h4>Diagnostic Checks</h4>
        <p><strong>Violations:</strong></p>
        <ul>{v_items}</ul>
        <p style="margin-top:10px;"><strong>Corrections Applied:</strong></p>
        <ul>{c_items}</ul>
      </div>"""
    else:
        checks = diag.get('checks', [])
        if checks:
            check_items = ''.join(
                f"<li class='badge-ok'>✓ {c.get('interpretation','')}</li>"
                for c in checks if not c.get('is_violated') and 'interpretation' in c
            )
            diag_html = f"""
      <div class="diagnostics-box">
        <h4>Diagnostic Checks</h4>
        <ul>{check_items}</ul>
      </div>"""

    n_units_str   = f"<div class='stat-card'><div class='stat-label'>Units</div><div class='stat-value'>{n_units:,}</div></div>" if n_units else ''
    n_periods_str = f"<div class='stat-card'><div class='stat-label'>Periods</div><div class='stat-value'>{n_periods:,}</div></div>" if n_periods else ''

    return f"""
  <div class="section">
    <h2 class="section-title">{titles.get(section_type, section_type)}</h2>
    <div style="margin-bottom:16px;">{fe_badge}{se_badge}</div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">{effect_label}</div>
        <div class="stat-value">{effect:,.4f}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Std Error</div>
        <div class="stat-value">{se:,.4f}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">P-Value</div>
        <div class="stat-value" style="color:{sig_color};">{pval:.4f}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Significant</div>
        <div class="stat-value" style="color:{sig_color};font-size:1.3em;">{sig_label}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">R-Squared</div>
        <div class="stat-value">{r_sq:.4f}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Observations</div>
        <div class="stat-value">{n_obs:,}</div>
      </div>
      {n_units_str}
      {n_periods_str}
    </div>

    <div class="chart-container">
      <div class="chart-title">{effect_label} with 95% Confidence Interval</div>
      <canvas id="regChart_{chart_id}" height="80"></canvas>
    </div>

    {diag_html}

    <div class="interpretation">
      <h3>Interpretation</h3>
      <div class="interpretation-content">{interp_html}</div>
    </div>
  </div>

  <script>
  (function(){{
    const ctx = document.getElementById('regChart_{chart_id}').getContext('2d');
    const effectVal = {effect};
    const ciLo = {ci_lo};
    const ciHi = {ci_hi};
    const isSig = {str(is_sig).lower()};
    const mainColor = isSig ? '{C['primary']}' : '{C['accent']}';

    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: ['95% CI Lower', '{effect_label}', '95% CI Upper'],
        datasets: [{{
          label: '{effect_label}',
          data: [ciLo, effectVal, ciHi],
          backgroundColor: [
            'rgba(166,124,82,0.3)',
            isSig ? 'rgba(111,78,55,0.75)' : 'rgba(141,110,99,0.5)',
            'rgba(166,124,82,0.3)'
          ],
          borderColor: [
            '{C['secondary']}',
            mainColor,
            '{C['secondary']}'
          ],
          borderWidth: 2,
          borderRadius: 6
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {{
          legend: {{display: false}},
          tooltip: {{
            backgroundColor: 'rgba(62,39,35,0.9)',
            callbacks: {{
              label: ctx => `${{ctx.label}}: ${{ctx.parsed.y.toFixed(4)}}`
            }}
          }},
          annotation: {{}}
        }},
        scales: {{
          x: {{
            grid: {{color: 'rgba(111,78,55,0.08)'}},
            ticks: {{color: '{C['dark']}', font: {{size:13}}}}
          }},
          y: {{
            title: {{display:true, text:'Effect Size', font:{{size:13,weight:'600'}}, color:'{C['dark']}'}},
            grid: {{color:'rgba(111,78,55,0.08)'}},
            ticks: {{color: '{C['dark']}'}}
          }}
        }}
      }}
    }});

    // Draw zero reference line via plugin
    Chart.register({{
      id: 'zeroLine_{chart_id}',
      afterDraw(chart) {{
        const yScale = chart.scales.y;
        if (yScale.min <= 0 && yScale.max >= 0) {{
          const y = yScale.getPixelForValue(0);
          const ctx2 = chart.ctx;
          ctx2.save();
          ctx2.beginPath();
          ctx2.moveTo(chart.chartArea.left, y);
          ctx2.lineTo(chart.chartArea.right, y);
          ctx2.strokeStyle = '#999';
          ctx2.lineWidth = 1.5;
          ctx2.setLineDash([6, 3]);
          ctx2.stroke();
          ctx2.restore();
        }}
      }}
    }});
  }})();
  </script>
"""


# ---------------------------------------------------------------------------
# Interpretation text → HTML
# ---------------------------------------------------------------------------

def _format_interpretation(text):
    """Convert plain-text interpretation (bullet hyphens) to HTML."""
    if not text:
        return "<p>No interpretation available.</p>"

    lines = text.strip().split('\n')
    parts = []
    first_answer = True
    ul_open = False

    for line in lines:
        line = line.strip()
        if not line:
            if ul_open:
                parts.append('</ul>')
                ul_open = False
            continue

        if line.startswith('-') or line.startswith('•'):
            clean = line.lstrip('-•').strip()
            if not ul_open:
                parts.append('<ul>')
                ul_open = True
            parts.append(f'<li>{clean}</li>')
        elif first_answer and len(line) > 20:
            if ul_open:
                parts.append('</ul>')
                ul_open = False
            parts.append(f'<div class="answer">{line}</div>')
            first_answer = False
        else:
            if ul_open:
                parts.append('</ul>')
                ul_open = False
            parts.append(f'<p>{line}</p>')

    if ul_open:
        parts.append('</ul>')

    return '\n'.join(parts)
