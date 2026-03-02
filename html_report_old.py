import os
from datetime import datetime, timezone
import io
import base64

def _safe_str(x):
    try:
        return str(x)
    except Exception:
        return ""

def _format_num(x, precision=2):
    """Format a number for display."""
    try:
        return f"{float(x):,.{precision}f}"
    except Exception:
        return str(x)

def _format_diagnostics(diagnostics):
    """Format diagnostics dict for HTML display."""
    if not diagnostics or 'error' in diagnostics:
        return "<p>Diagnostics unavailable</p>"
    
    html_lines = []
    checks = diagnostics.get('checks', [])
    violations = diagnostics.get('violations', [])
    corrections = diagnostics.get('corrections', [])
    
    for check in checks:
        if 'error' not in check:
            is_pass = not check.get('is_violated', False)
            css_class = 'check-pass' if is_pass else 'check-fail'
            icon = '✓' if is_pass else '✗'
            html_lines.append(f'<div class="{css_class}">{icon} {check.get("interpretation", "Check performed")}</div>')
    
    if violations:
        html_lines.append(f'<div style="margin-top: 10px; color: #e74c3c; font-weight: bold;">⚠️ Violations Detected:</div>')
        for v in violations:
            html_lines.append(f'<div style="padding-left: 10px;">• {v}</div>')
    
    if corrections:
        html_lines.append(f'<div style="margin-top: 10px; color: #27ae60; font-weight: bold;">✓ Corrections Applied:</div>')
        for c in corrections:
            html_lines.append(f'<div style="padding-left: 10px;">• {c}</div>')
    
    return "\n".join(html_lines) if html_lines else "<p>All diagnostic checks passed</p>"

def _generate_ci_plot_svg(effect, se, ci_lo, ci_hi):
    """Generate SVG of confidence interval plot."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        
        fig, ax = plt.subplots(figsize=(10, 3))
        
        # Plot CI as horizontal line
        ax.hlines(0.5, ci_lo, ci_hi, colors='steelblue', linewidth=16, alpha=0.7)
        
        # Plot point estimate
        ax.plot(effect, 0.5, 'o', color='darkblue', markersize=14, zorder=5)
        
        # Plot null line
        ax.axvline(0, color='red', linestyle='--', linewidth=2, alpha=0.6, label='Null (0)')
        
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_xlabel('Treatment Effect', fontsize=11, weight='bold')
        ax.set_title('95% Confidence Interval', fontsize=12, weight='bold')
        ax.grid(axis='x', alpha=0.3, linestyle=':')
        ax.legend(loc='upper right')
        
        # Save to SVG string
        svg_buf = io.StringIO()
        plt.savefig(svg_buf, format='svg', bbox_inches='tight', dpi=100)
        svg_buf.seek(0)
        svg_str = svg_buf.getvalue()
        plt.close(fig)
        
        return svg_str
    except Exception:
        return ""

def _generate_effect_bar_svg(effect, se):
    """Generate SVG bar chart of effect with error bars."""
    try:
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 4))
        
        # Bar chart with error bar
        ci_lower = 1.96 * se
        ax.bar(0, effect, width=0.4, color='steelblue', alpha=0.8, capsize=10)
        ax.errorbar(0, effect, yerr=ci_lower, fmt='none', ecolor='darkblue', elinewidth=2, capsize=5)
        
        # Add value label
        ax.text(0, effect + ci_lower + abs(effect) * 0.05, f'{effect:.0f}', 
               ha='center', fontsize=11, weight='bold')
        
        ax.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.5)
        ax.set_ylabel('Effect Estimate', fontsize=11, weight='bold')
        ax.set_title('Treatment Effect with 95% CI', fontsize=12, weight='bold')
        ax.set_xticks([])
        ax.grid(axis='y', alpha=0.3)
        
        # Save to SVG
        svg_buf = io.StringIO()
        plt.savefig(svg_buf, format='svg', bbox_inches='tight', dpi=100)
        svg_buf.seek(0)
        svg_str = svg_buf.getvalue()
        plt.close(fig)
        
        return svg_str
    except Exception:
        return ""

def _generate_forecast_comparison_svg(last_val, forecast):
    """Generate SVG comparison chart of last value vs forecast."""
    try:
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 4))
        
        vals = [last_val, forecast]
        colors = ['coral', 'steelblue']
        labels = ['Last Observed', 'Forecast (t+1)']
        
        bars = ax.bar(labels, vals, color=colors, alpha=0.8, width=0.5)
        
        # Add value labels on bars
        for bar, val in zip(bars, vals):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{val:.1f}', ha='center', va='bottom', fontsize=11, weight='bold')
        
        ax.set_ylabel('Value', fontsize=11, weight='bold')
        ax.set_title('Time Series Forecast Comparison', fontsize=12, weight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        # Save to SVG
        svg_buf = io.StringIO()
        plt.savefig(svg_buf, format='svg', bbox_inches='tight', dpi=100)
        svg_buf.seek(0)
        svg_str = svg_buf.getvalue()
        plt.close(fig)
        
        return svg_str
    except Exception:
        return ""

def create_html_report(out_path, intent, mapping, model_results, data_sample=None):
    """Create a professional HTML report with advanced visualizations.
    
    - out_path: full path to write HTML
    - intent: parsed question intent
    - mapping: LLM mapping dict
    - model_results: list of result dicts (use exact values from this, don't recalculate)
    - data_sample: small pandas DataFrame sample (optional)
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Espresso Analysis Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f5f7fa; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); overflow: hidden; }
        header { background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 40px 30px; text-align: center; }
        header h1 { font-size: 32px; margin-bottom: 10px; }
        header p { font-size: 14px; opacity: 0.9; }
        .content { padding: 30px; }
        section { margin-bottom: 50px; }
        section h2 { font-size: 20px; color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }
        .result-box { background-color: #ecf0f1; border-left: 5px solid #3498db; padding: 20px; margin-bottom: 20px; border-radius: 4px; }
        .result-box h3 { font-size: 18px; color: #2c3e50; margin-bottom: 15px; }
        .metric { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #bdc3c7; }
        .metric:last-child { border-bottom: none; }
        .metric-label { font-weight: 600; color: #34495e; flex: 1; }
        .metric-value { text-align: right; color: #2c3e50; font-family: 'Courier New', monospace; font-weight: 500; }
        .interpretation { background-color: #eaf4fc; border-left: 4px solid #3498db; padding: 15px; margin-top: 15px; border-radius: 4px; font-style: italic; color: #2c3e50; }
        .viz-container { margin: 25px 0; padding: 20px; background-color: #f8f9fa; border-radius: 4px; }
        .viz-container svg { width: 100%; height: auto; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        table th { background-color: #34495e; color: white; padding: 12px 15px; text-align: left; font-weight: 600; border: none; }
        table td { padding: 12px 15px; border-bottom: 1px solid #ecf0f1; font-family: 'Courier New', monospace; }
        table tr:nth-child(even) { background-color: #f8f9fa; }
        table tr:hover { background-color: #ecf0f1; }
        .metadata { background-color: #f8f9fa; border: 1px solid #ecf0f1; border-radius: 4px; padding: 15px; margin-bottom: 20px; }
        .metadata dt { font-weight: 600; color: #34495e; margin-top: 8px; }
        .metadata dd { color: #555; margin-left: 0; padding-left: 0; margin-bottom: 8px; font-family: 'Courier New', monospace; }
        .significance { display: inline-block; padding: 4px 8px; border-radius: 3px; font-weight: 600; font-size: 13px; }
        .sig-high { background-color: #d4edda; color: #155724; }
        .sig-med { background-color: #fff3cd; color: #856404; }
        .sig-low { background-color: #f8d7da; color: #721c24; }
        .diagnostics-section { background-color: #f0f8ff; border: 1px solid #3498db; border-radius: 4px; padding: 15px; margin-bottom: 20px; }
        .diagnostics-section h4 { color: #2c3e50; margin-bottom: 10px; font-size: 16px; }
        .check-pass { color: #27ae60; padding: 5px 0; }
        .check-fail { color: #e74c3c; padding: 5px 0; }
        .llm-interpretation { background-color: #f9f5e6; border-left: 4px solid #f39c12; padding: 15px; margin-top: 15px; border-radius: 4px; line-height: 1.7; color: #333; }
        .llm-interpretation strong { color: #d68910; }
        footer { background-color: #ecf0f1; padding: 20px 30px; text-align: center; font-size: 12px; color: #7f8c8d; border-top: 1px solid #bdc3c7; }
        .no-results { color: #e74c3c; font-size: 16px; padding: 20px; background-color: #fadbd8; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Espresso Analysis Report</h1>
            <p>Generated: """ + now + """</p>
        </header>
        
        <div class="content">
"""

    # Analysis metadata section
    html_content += f"""
            <section>
                <h2>Analysis Overview</h2>
                <div class="metadata">
                    <dl>
                        <dt>Outcome Variable:</dt>
                        <dd>{_safe_str(intent.get('outcome'))[:100]}</dd>
                        <dt>Treatment Variable:</dt>
                        <dd>{_safe_str(intent.get('treatment'))[:100]}</dd>
                        <dt>Unit (Group):</dt>
                        <dd>{_safe_str(intent.get('unit'))[:100]}</dd>
                        <dt>Time Variable:</dt>
                        <dd>{_safe_str(intent.get('time'))[:100]}</dd>
                    </dl>
                </div>
            </section>
"""

    # Primary result section with visualizations
    if model_results:
        r = model_results[0]
        html_content += """
            <section>
                <h2>Primary Result & Visualizations</h2>
"""
        if r.get('effect') is not None:
            # DiD result - use values directly from model_results
            eff = float(r['effect'])
            se = float(r.get('se', 0)) if r.get('se') is not None else 0
            p = float(r.get('p_value', 1))
            t_stat = float(r.get('t_stat', 0)) if r.get('t_stat') is not None else 0
            r_sq = float(r.get('r_squared', 0)) if r.get('r_squared') is not None else 0
            n_obs = r.get('n_obs', 'N/A')
            
            # Calculate CI from effect and SE (use same calculation as terminal output)
            ci_lo = eff - 1.96 * se if se > 0 else eff
            ci_hi = eff + 1.96 * se if se > 0 else eff
            
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            sig_class = "sig-high" if p < 0.05 else "sig-med" if p < 0.1 else "sig-low"
            
            html_content += f"""
                <div class="result-box">
                    <h3>{r.get('model', 'Model')}</h3>
                    <div class="metric">
                        <span class="metric-label">Treatment Effect Estimate:</span>
                        <span class="metric-value">{_format_num(eff)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Standard Error:</span>
                        <span class="metric-value">{_format_num(se)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">95% Confidence Interval:</span>
                        <span class="metric-value">[{_format_num(ci_lo)}, {_format_num(ci_hi)}]</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">t-statistic:</span>
                        <span class="metric-value">{_format_num(t_stat, 4)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">p-value:</span>
                        <span class="metric-value">{_format_num(p, 4)} <span class="significance {sig_class}">{sig}</span></span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">R-squared:</span>
                        <span class="metric-value">{_format_num(r_sq, 4)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Observations:</span>
                        <span class="metric-value">{str(n_obs)}</span>
                    </div>
                    <div class="interpretation">
                        <strong>Interpretation:</strong> {r.get('interpretation', 'No interpretation available.')}
                    </div>
                </div>

                <!-- Diagnostics Section -->
                {f'''
                <div class="diagnostics-section">
                    <h4>🔍 Pre-Analysis Diagnostic Checks</h4>
                    {_format_diagnostics(r.get('diagnostics', {}))}
                </div>
                ''' if r.get('diagnostics') else ''}

                <!-- LLM Interpretation Section -->
                {f'''
                <div class="llm-interpretation">
                    <strong>📊 AI-Powered Analysis:</strong>
                    <p>{r.get('llm_interpretation', 'Interpretation unavailable')}</p>
                </div>
                ''' if r.get('llm_interpretation') else ''}
"""
            
            # Add visualizations
            ci_svg = _generate_ci_plot_svg(eff, se, ci_lo, ci_hi)
            if ci_svg:
                html_content += f"""
                <div class="viz-container">
                    <h4 style="margin-bottom: 15px; color: #2c3e50;">Confidence Interval Visualization</h4>
                    {ci_svg}
                </div>
"""
            
            effect_svg = _generate_effect_bar_svg(eff, se)
            if effect_svg:
                html_content += f"""
                <div class="viz-container">
                    <h4 style="margin-bottom: 15px; color: #2c3e50;">Effect with Error Bars</h4>
                    {effect_svg}
                </div>
"""
            
        elif r.get('forecast') is not None:
            # ARIMA result - use values directly from model_results
            fc = float(r.get('forecast', 0))
            ar_coef = float(r.get('ar1_coef', 0)) if r.get('ar1_coef') is not None else 0
            intercept = float(r.get('intercept', 0)) if r.get('intercept') is not None else 0
            aic = float(r.get('aic', 0)) if r.get('aic') is not None else 0
            rmse = float(r.get('rmse', 0)) if r.get('rmse') is not None else 0
            n_obs = r.get('n_obs', 'N/A')
            last_val = float(r.get('last_value', fc)) if r.get('last_value') is not None else fc
            
            stability = "STABLE" if abs(ar_coef) < 1 else "UNSTABLE"
            
            html_content += f"""
                <div class="result-box">
                    <h3>{r.get('model', 'Model')}</h3>
                    <div class="metric">
                        <span class="metric-label">Forecast (t+1):</span>
                        <span class="metric-value">{_format_num(fc)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">AR(1) Coefficient:</span>
                        <span class="metric-value">{_format_num(ar_coef, 4)} ({stability})</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Intercept:</span>
                        <span class="metric-value">{_format_num(intercept, 4)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">AIC:</span>
                        <span class="metric-value">{_format_num(aic, 2)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">RMSE:</span>
                        <span class="metric-value">{_format_num(rmse, 6)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Observations:</span>
                        <span class="metric-value">{str(n_obs)}</span>
                    </div>
                    <div class="interpretation">
                        <strong>Interpretation:</strong> {r.get('interpretation', 'No interpretation available.')}
                    </div>
                </div>

                <!-- Diagnostics Section -->
                {f'''
                <div class="diagnostics-section">
                    <h4>🔍 Pre-Analysis Diagnostic Checks</h4>
                    {_format_diagnostics(r.get('diagnostics', {}))}
                </div>
                ''' if r.get('diagnostics') else ''}

                <!-- LLM Interpretation Section -->
                {f'''
                <div class="llm-interpretation">
                    <strong>📊 AI-Powered Analysis:</strong>
                    <p>{r.get('llm_interpretation', 'Interpretation unavailable')}</p>
                </div>
                ''' if r.get('llm_interpretation') else ''}
"""
            
            # Add forecast visualization
            forecast_svg = _generate_forecast_comparison_svg(last_val, fc)
            if forecast_svg:
                html_content += f"""
                <div class="viz-container">
                    <h4 style="margin-bottom: 15px; color: #2c3e50;">Forecast Comparison</h4>
                    {forecast_svg}
                </div>
"""
        
        html_content += """
            </section>
"""

        # Comprehensive diagnostic table
        if len(model_results) > 0:
            html_content += """
            <section>
                <h2>Diagnostic Statistics</h2>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 35%;">Statistic</th>
                            <th style="width: 65%;">Value</th>
                        </tr>
                    </thead>
                    <tbody>
"""
            
            r = model_results[0]
            if r.get('effect') is not None:
                # DiD diagnostics - use exact values from model_results
                eff = float(r['effect'])
                se = float(r.get('se', 0)) if r.get('se') is not None else 0
                p = float(r.get('p_value', 1))
                t_stat = float(r.get('t_stat', 0)) if r.get('t_stat') is not None else 0
                r_sq = float(r.get('r_squared', 0)) if r.get('r_squared') is not None else 0
                ci_lo = eff - 1.96 * se if se > 0 else eff
                ci_hi = eff + 1.96 * se if se > 0 else eff
                n_obs = r.get('n_obs', 'N/A')
                sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
                
                diagnostics = [
                    ("Model Type", str(r.get('model', 'N/A'))),
                    ("Treatment Effect", _format_num(eff)),
                    ("Standard Error", _format_num(se)),
                    ("95% CI Lower Bound", _format_num(ci_lo)),
                    ("95% CI Upper Bound", _format_num(ci_hi)),
                    ("t-statistic", _format_num(t_stat, 4)),
                    ("p-value", _format_num(p, 4)),
                    ("Significance Level", sig),
                    ("R-squared", _format_num(r_sq, 4)),
                    ("Number of Observations", str(n_obs)),
                ]
            elif r.get('forecast') is not None:
                # ARIMA diagnostics - use exact values from model_results
                fc = float(r.get('forecast', 0))
                ar_coef = float(r.get('ar1_coef', 0)) if r.get('ar1_coef') is not None else 0
                intercept = float(r.get('intercept', 0)) if r.get('intercept') is not None else 0
                aic = float(r.get('aic', 0)) if r.get('aic') is not None else 0
                rmse = float(r.get('rmse', 0)) if r.get('rmse') is not None else 0
                n_obs = r.get('n_obs', 'N/A')
                stability = "STABLE" if abs(ar_coef) < 1 else "UNSTABLE"
                
                diagnostics = [
                    ("Model Type", str(r.get('model', 'N/A'))),
                    ("Forecast (t+1)", _format_num(fc)),
                    ("AR(1) Coefficient", _format_num(ar_coef, 4)),
                    ("Intercept", _format_num(intercept, 4)),
                    ("Process Stability", stability),
                    ("AIC", _format_num(aic, 2)),
                    ("RMSE", _format_num(rmse, 6)),
                    ("Number of Observations", str(n_obs)),
                ]
            else:
                diagnostics = []
            
            for label, value in diagnostics:
                html_content += f"""
                        <tr>
                            <td><strong>{label}</strong></td>
                            <td>{value}</td>
                        </tr>
"""
            
            html_content += """
                    </tbody>
                </table>
            </section>
"""
    else:
        html_content += """
            <section>
                <div class="no-results">
                    ⚠️ No valid models found for this analysis. Please check the data and question mapping.
                </div>
            </section>
"""

    # Footer
    html_content += f"""
        </div>
        
        <footer>
            <p>Espresso Statistical Inference Engine | Generated {now}</p>
        </footer>
    </div>
</body>
</html>
"""

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return out_path

