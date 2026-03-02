"""
Beautiful HTML report generator with clean design and excellent visualizations
"""
import os
import json
from datetime import datetime, timezone

def create_html_report(output_path, intent, mapping, model_results, data_sample=None):
    """Generate a beautiful HTML report with clean styling and Chart.js visualizations"""
    
    # Extract info - store actual question from mapping if available
    question_text = mapping.get('question') if mapping and 'question' in mapping else intent.get('question', 'N/A')
    if not question_text or question_text == 'N/A':
        question_text = intent.get('outcome', 'Analysis')
    intent['question'] = question_text  # Ensure it's in intent dict
    outcome = intent.get('outcome', 'N/A')
    treatment = intent.get('treatment', 'None')
    unit_name = intent.get('identified_unit', None)
    
    # Modern espresso color palette
    colors = {
        'primary': '#6F4E37',
        'secondary': '#A67C52',
        'light': '#D4A574',
        'cream': '#F5E6D3',
        'dark': '#3E2723',
        'accent': '#8D6E63',
        'bg': '#FFFBF5'
    }
    
    # Generate model sections
    model_sections_html = ""
    for result in model_results:
        model_name = result.get('model', 'Unknown')
        interpretation = result.get('llm_interpretation', 'No interpretation available')
        
        # Clean up interpretation - remove asterisks and markdown formatting
        interpretation = interpretation.replace('**', '').replace('*', '')
        
        # Convert interpretation to proper HTML with clean bullets
        interpretation_html = format_interpretation(interpretation)
        
        if 'ARIMA' in model_name:
            model_sections_html += generate_arima_section(result, interpretation_html, colors)
        elif 'Difference-in-Differences' in model_name or 'DiD' in model_name:
            model_sections_html += generate_did_section(result, interpretation_html, colors)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Espresso Analysis Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, {colors['bg']} 0%, {colors['cream']} 100%);
            color: {colors['dark']};
            line-height: 1.7;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 10px 50px rgba(62, 39, 35, 0.12);
            border-radius: 16px;
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, {colors['primary']} 0%, {colors['secondary']} 100%);
            color: white;
            padding: 50px 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.8em;
            margin-bottom: 15px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.95;
            font-weight: 300;
        }}
        
        .section {{
            padding: 40px;
        }}
        
        .section-title {{
            font-size: 2em;
            color: {colors['primary']};
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 3px solid {colors['cream']};
            font-weight: 600;
        }}
        
        .interpretation {{
            background: {colors['bg']};
            border-left: 4px solid {colors['secondary']};
            padding: 30px;
            margin: 25px 0;
            border-radius: 8px;
            font-size: 1.05em;
        }}
        
        .interpretation h3 {{
            color: {colors['primary']};
            font-size: 1.4em;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        
        .interpretation-content {{
            color: {colors['dark']};
            line-height: 1.9;
        }}
        
        .interpretation-content > div {{
            margin-bottom: 20px;
        }}
        
        .interpretation-content .answer {{
            background: white;
            padding: 20px;
            border-radius: 6px;
            border: 2px solid {colors['light']};
            margin-bottom: 20px;
            font-size: 1.1em;
            font-weight: 500;
            color: {colors['primary']};
        }}
        
        .interpretation-content ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .interpretation-content li {{
            padding: 8px 0 8px 25px;
            position: relative;
            line-height: 1.8;
        }}
        
        .interpretation-content li:before {{
            content: '';
            position: absolute;
            left: 0;
            top: 15px;
            width: 8px;
            height: 8px;
            background: {colors['secondary']};
            border-radius: 50%;
        }}
        
        .chart-container {{
            margin: 30px 0;
            padding: 25px;
            background: white;
            border-radius: 8px;
            border: 1px solid {colors['cream']};
        }}
        
        .chart-title {{
            font-size: 1.3em;
            color: {colors['primary']};
            margin-bottom: 20px;
            font-weight: 600;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, {colors['cream']} 0%, white 100%);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid {colors['light']};
        }}
        
        .stat-label {{
            font-size: 0.9em;
            color: {colors['secondary']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        
        .stat-value {{
            font-size: 1.8em;
            color: {colors['primary']};
            font-weight: 700;
        }}
        
        .forecast-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid {colors['cream']};
        }}
        
        .forecast-table th {{
            background: {colors['primary']};
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        .forecast-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid {colors['cream']};
        }}
        
        .forecast-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .forecast-table tr:hover {{
            background: {colors['bg']};
        }}
        
        .diagnostics {{
            background: {colors['cream']};
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        
        .diagnostics h4 {{
            color: {colors['primary']};
            margin-bottom: 15px;
        }}
        
        .diagnostics ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .diagnostics li {{
            padding: 6px 0;
        }}
        
        .timestamp {{
            text-align: center;
            padding: 20px;
            color: {colors['secondary']};
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Espresso Analysis Report</h1>
            <div class="subtitle">Statistical Analysis & Interpretation</div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Research Question</h2>
            <div style="font-size: 1.2em; color: {colors['dark']}; padding: 20px; background: {colors['bg']}; border-radius: 8px;">
                "{intent.get('question', 'Analysis')}"
            </div>
            {f'''<div style="margin-top: 20px; padding: 15px; background: {colors['cream']}; border-left: 4px solid {colors['primary']}; border-radius: 4px;">
                <strong style="color: {colors['primary']};">Unit of Analysis:</strong> <span style="font-size: 1.1em; font-weight: 600;">{unit_name}</span>
            </div>''' if unit_name else ''}
        </div>
        
        {model_sections_html}
        
        <div class="timestamp">
            Report generated on {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}
        </div>
    </div>
</body>
</html>"""
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write the HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return output_path


def format_interpretation(text):
    """Convert interpretation text to clean HTML"""
    if not text:
        return "<p>No interpretation available</p>"
    
    lines = text.strip().split('\n')
    html_parts = []
    current_section = []
    first_answer = True
    
    for line in lines:
        line = line.strip()
        if not line:
            if current_section:
                html_parts.append('<div>' + '\n'.join(current_section) + '</div>')
                current_section = []
            continue
        
        # Check if this looks like a direct answer (first substantive sentence)
        if first_answer and len(line) > 20 and not line.startswith('-'):
            html_parts.append(f'<div class="answer">{line}</div>')
            first_answer = False
        elif line.startswith('-') or line.startswith('•'):
            # Bullet point
            clean_line = line.lstrip('-•').strip()
            if not current_section or (current_section and '</ul>' in current_section[-1]):
                current_section.append('<ul>')
            current_section.append(f'<li>{clean_line}</li>')
        else:
            # Regular text
            if current_section and current_section[-1].startswith('<li>'):
                current_section.append('</ul>')
            current_section.append(f'<p>{line}</p>')
    
    if current_section:
        # Close any open ul tags
        if current_section and current_section[-1].startswith('<li>'):
            current_section.append('</ul>')
        html_parts.append('<div>' + '\n'.join(current_section) + '</div>')
    
    return '\n'.join(html_parts)


def generate_arima_section(result, interpretation_html, colors):
    """Generate HTML for ARIMA results with time series visualization"""
    
    forecasts = result.get('forecasts', [])
    forecast_times = result.get('forecast_times', [])
    historical_values = result.get('historical_values', [])
    historical_times = result.get('historical_times', [])
    ar_coef = result.get('ar1_coef', 0)
    rmse = result.get('rmse', 0)
    n_obs = result.get('n_obs', 0)
    
    # Use all forecast periods, not just 10
    num_forecast_periods = len(forecasts)
    
    # Prepare data for Chart.js
    all_times = list(historical_times) + list(forecast_times)
    all_values = list(historical_values) + [None] * len(forecast_times)
    forecast_values = [None] * len(historical_values) + list(forecasts)
    
    chart_data = {
        'labels': [int(t) for t in all_times],
        'historical': all_values,
        'forecast': forecast_values
    }
    
    # Generate forecast table - show all periods
    forecast_table_rows = ""
    for i, (time, value) in enumerate(zip(forecast_times, forecasts), 1):
        forecast_table_rows += f"""
        <tr>
            <td>Period t+{i}</td>
            <td>{int(time)}</td>
            <td style="font-weight: 600; color: {colors['primary']}">{value:,.2f}</td>
        </tr>
        """
    
    return f"""
    <div class="section">
        <h2 class="section-title">ARIMA Forecast Results</h2>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Model Type</div>
                <div class="stat-value" style="font-size: 1.3em;">AR(1)</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">AR Coefficient</div>
                <div class="stat-value">{ar_coef:.4f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Model Quality (RMSE)</div>
                <div class="stat-value">{rmse:,.2f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Observations</div>
                <div class="stat-value">{n_obs:,}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Time Series with {num_forecast_periods}-Period Forecast</div>
            <canvas id="arimaChart" height="100"></canvas>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Forecast Table ({num_forecast_periods} Periods)</div>
            <table class="forecast-table">
                <thead>
                    <tr>
                        <th>Period</th>
                        <th>Year</th>
                        <th>Forecast Value</th>
                    </tr>
                </thead>
                <tbody>
                    {forecast_table_rows}
                </tbody>
            </table>
        </div>
        
        <div class="interpretation">
            <h3>Interpretation</h3>
            <div class="interpretation-content">
                {interpretation_html}
            </div>
        </div>
    </div>
    
    <script>
        const arimaCtx = document.getElementById('arimaChart').getContext('2d');
        new Chart(arimaCtx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(chart_data['labels'])},
                datasets: [
                    {{
                        label: 'Historical Data',
                        data: {json.dumps(chart_data['historical'])},
                        borderColor: '{colors['primary']}',
                        backgroundColor: 'rgba(111, 78, 55, 0.1)',
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: '{colors['primary']}',
                        fill: false,
                        tension: 0.3
                    }},
                    {{
                        label: 'Forecast',
                        data: {json.dumps(chart_data['forecast'])},
                        borderColor: '{colors['secondary']}',
                        backgroundColor: 'rgba(166, 124, 82, 0.1)',
                        borderWidth: 3,
                        borderDash: [10, 5],
                        pointRadius: 5,
                        pointBackgroundColor: '{colors['secondary']}',
                        fill: false,
                        tension: 0.3
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
                            font: {{ size: 14, weight: '600' }},
                            color: '{colors['dark']}'
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(62, 39, 35, 0.9)',
                        titleFont: {{ size: 14, weight: '600' }},
                        bodyFont: {{ size: 13 }},
                        padding: 12,
                        displayColors: true
                    }}
                }},
                scales: {{
                    x: {{
                        title: {{
                            display: true,
                            text: 'Year',
                            font: {{ size: 14, weight: '600' }},
                            color: '{colors['dark']}'
                        }},
                        grid: {{
                            color: 'rgba(111, 78, 55, 0.1)'
                        }}
                    }},
                    y: {{
                        title: {{
                            display: true,
                            text: 'Value',
                            font: {{ size: 14, weight: '600' }},
                            color: '{colors['dark']}'
                        }},
                        grid: {{
                            color: 'rgba(111, 78, 55, 0.1)'
                        }}
                    }}
                }}
            }}
        }});
    </script>
    """


def generate_did_section(result, interpretation_html, colors):
    """Generate HTML for Difference-in-Differences results with appropriate visualizations"""
    
    effect = result.get('effect', 0)
    se = result.get('se', 0)
    p_value = result.get('p_value', 1)
    r_squared = result.get('r_squared', 0)
    n_obs = result.get('n_obs', 0)
    
    # Calculate confidence interval
    ci_lower = effect - 1.96 * se
    ci_upper = effect + 1.96 * se
    
    # Determine significance
    is_significant = p_value < 0.05
    
    # Create visualization data for treatment effect
    chart_data = {
        'effect': effect,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'is_significant': is_significant
    }
    
    diagnostics_html = ""
    if 'diagnostics' in result:
        diag = result['diagnostics']
        violations = diag.get('violations', [])
        corrections = diag.get('corrections', [])
        if violations:
            violations_html = ''.join([f'<li>{v}</li>' for v in violations])
            corrections_html = ''.join([f'<li>{c}</li>' for c in corrections])
            diagnostics_html = f"""
            <div class="diagnostics">
                <h4>Diagnostic Checks</h4>
                <p><strong>Violations Detected:</strong></p>
                <ul>{violations_html}</ul>
                <p><strong>Corrections Applied:</strong></p>
                <ul>{corrections_html}</ul>
            </div>
            """
    
    return f"""
    <div class="section">
        <h2 class="section-title">Difference-in-Differences Analysis</h2>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Treatment Effect</div>
                <div class="stat-value">{effect:,.2f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Standard Error</div>
                <div class="stat-value">{se:,.2f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">P-Value</div>
                <div class="stat-value" style="color: {'#4CAF50' if is_significant else '#FF5722'}">{p_value:.4f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">R-Squared</div>
                <div class="stat-value">{r_squared:.4f}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Treatment Effect with 95% Confidence Interval</div>
            <canvas id="didChart" height="80"></canvas>
        </div>
        
        {diagnostics_html}
        
        <div class="interpretation">
            <h3>Interpretation</h3>
            <div class="interpretation-content">
                {interpretation_html}
            </div>
        </div>
    </div>
    
    <script>
        const didCtx = document.getElementById('didChart').getContext('2d');
        new Chart(didCtx, {{
            type: 'line',
            data: {{
                labels: ['Lower CI', 'Effect', 'Upper CI'],
                datasets: [
                    {{
                        label: 'Treatment Effect',
                        data: [{ci_lower}, {effect}, {ci_upper}],
                        borderColor: '{colors['primary'] if is_significant else colors['secondary']}',
                        backgroundColor: 'rgba(111, 78, 55, 0.1)',
                        borderWidth: 3,
                        pointRadius: 6,
                        pointBackgroundColor: ['{colors['secondary']}', '{colors['primary']}', '{colors['secondary']}'],
                        pointBorderColor: '{colors['dark']}',
                        pointBorderWidth: 2,
                        fill: true,
                        tension: 0.1
                    }},
                    {{
                        label: 'Zero Line',
                        data: [0, 0, 0],
                        borderColor: '#999',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false
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
                            font: {{ size: 14, weight: '600' }},
                            color: '{colors['dark']}'
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(62, 39, 35, 0.9)',
                        titleFont: {{ size: 14, weight: '600' }},
                        bodyFont: {{ size: 13 }},
                        padding: 12,
                        callbacks: {{
                            label: function(context) {{
                                let label = context.dataset.label || '';
                                if (label) {{
                                    label += ': ';
                                }}
                                label += context.parsed.y.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                                return label;
                            }},
                            afterBody: function() {{
                                return [
                                    'P-value: {p_value:.4f}',
                                    'Standard Error: {se:,.2f}',
                                    'Significant: {'Yes' if is_significant else 'No'}'
                                ];
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        title: {{
                            display: true,
                            text: '95% Confidence Interval',
                            font: {{ size: 14, weight: '600' }},
                            color: '{colors['dark']}'
                        }},
                        grid: {{
                            color: 'rgba(111, 78, 55, 0.1)'
                        }}
                    }},
                    y: {{
                        title: {{
                            display: true,
                            text: 'Effect Size',
                            font: {{ size: 14, weight: '600' }},
                            color: '{colors['dark']}'
                        }},
                        grid: {{
                            color: 'rgba(111, 78, 55, 0.1)'
                        }}
                    }}
                }}
            }}
        }});
    </script>
    """
