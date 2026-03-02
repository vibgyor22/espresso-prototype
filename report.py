import os
from datetime import datetime, timezone
import textwrap

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

def create_pdf_report(out_path, intent, mapping, model_results, data_sample=None):
    """Create a professional, clean PDF report with no overlaps.

    - out_path: full path to write PDF
    - intent: parsed question intent
    - mapping: LLM mapping dict
    - model_results: list of result dicts built in run.py
    - data_sample: small pandas DataFrame sample (optional)
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        import numpy as np
    except Exception as e:
        raise RuntimeError(f"Missing plotting dependency: {e}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with PdfPages(out_path) as pdf:
        # ===== PAGE 1: EXECUTIVE SUMMARY =====
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.5, 0.97, "Espresso Analysis Report", ha='center', fontsize=20, weight='bold')
        fig.text(0.5, 0.945, f"Generated: {now}", ha='center', fontsize=8, style='italic')
        
        # Create main grid: two sections vertically
        gs = fig.add_gridspec(2, 1, top=0.93, bottom=0.05, hspace=0.3)
        
        # ===== SECTION 1: Primary Result Visualization =====
        ax1 = fig.add_subplot(gs[0])
        ax1.axis('off')
        
        if model_results and len(model_results) > 0:
            r = model_results[0]  # Primary result
            
            # Title
            ax1.text(0.05, 0.95, f"Primary Model: {r.get('model', 'Model')}", 
                    fontsize=13, weight='bold', transform=ax1.transAxes)
            
            if r.get('effect') is not None:
                # ===== DiD RESULT =====
                eff = float(r['effect'])
                se = float(r.get('se', 0)) if r.get('se') is not None else abs(eff) * 0.2
                p = float(r.get('p_value', 1))
                ci_lo = eff - 1.96 * se
                ci_hi = eff + 1.96 * se
                
                # Create visualization axes within ax1
                ax_viz = fig.add_axes([0.12, 0.60, 0.75, 0.12])
                ax_viz.hlines(0.5, ci_lo, ci_hi, colors='steelblue', linewidth=14, alpha=0.8)
                ax_viz.plot(eff, 0.5, 'o', color='darkblue', markersize=12, zorder=5)
                ax_viz.axvline(0, color='red', linestyle='--', linewidth=2, alpha=0.6)
                ax_viz.set_ylim(0, 1)
                ax_viz.set_yticks([])
                ax_viz.set_xlabel('Treatment Effect Value', fontsize=10, weight='bold')
                ax_viz.grid(axis='x', alpha=0.3, linestyle=':')
                
                # Key stats below chart
                sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
                ax1.text(0.05, 0.50, f"Point Estimate:  {_format_num(eff)}", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                ax1.text(0.05, 0.44, f"Std. Error:      {_format_num(se)}", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                ax1.text(0.05, 0.38, f"95% CI:          [{_format_num(ci_lo)}, {_format_num(ci_hi)}]", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                ax1.text(0.05, 0.32, f"p-value:         {_format_num(p, 4)} ({sig})", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                
                # Interpretation
                interp = r.get('interpretation', '')[:150]
                ax1.text(0.05, 0.20, f"Interpretation:", fontsize=10, weight='bold', transform=ax1.transAxes)
                ax1.text(0.05, 0.15, textwrap.fill(interp, width=90), fontsize=9, 
                        transform=ax1.transAxes, va='top')
                
            elif r.get('forecast') is not None:
                # ===== ARIMA RESULT =====
                fc = float(r['forecast'])
                last = float(r.get('last_value', fc)) if r.get('last_value') else fc
                rmse = float(r.get('rmse', 0))
                
                # Simple forecast visualization
                ax_viz = fig.add_axes([0.12, 0.60, 0.75, 0.12])
                vals = [last, fc]
                colors = ['lightcoral', 'steelblue']
                bars = ax_viz.bar([0, 1], vals, color=colors, alpha=0.8, width=0.6)
                ax_viz.set_xticks([0, 1])
                ax_viz.set_xticklabels(['Last Observed', 'Forecast (t+1)'], fontsize=10)
                ax_viz.set_ylabel('Value', fontsize=10, weight='bold')
                ax_viz.grid(axis='y', alpha=0.3, linestyle=':')
                
                # Add value labels on bars
                for bar, val in zip(bars, vals):
                    height = bar.get_height()
                    ax_viz.text(bar.get_x() + bar.get_width()/2., height,
                              f'{_format_num(val)}', ha='center', va='bottom', fontsize=9)
                
                # Key stats
                ax1.text(0.05, 0.50, f"Forecast (t+1):  {_format_num(fc)}", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                ax1.text(0.05, 0.44, f"Last Observed:   {_format_num(last)}", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                ax1.text(0.05, 0.38, f"Expected Change: {_format_num(fc - last)}", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                ax1.text(0.05, 0.32, f"Model RMSE:      {_format_num(rmse)}", 
                        fontsize=10, transform=ax1.transAxes, family='monospace')
                
                # Interpretation
                interp = r.get('interpretation', '')[:150]
                ax1.text(0.05, 0.20, f"Interpretation:", fontsize=10, weight='bold', transform=ax1.transAxes)
                ax1.text(0.05, 0.15, textwrap.fill(interp, width=90), fontsize=9, 
                        transform=ax1.transAxes, va='top')
        
        # ===== SECTION 2: Diagnostic Statistics Table =====
        ax2 = fig.add_subplot(gs[1])
        ax2.axis('off')
        
        ax2.text(0.05, 0.98, "Diagnostic Statistics", fontsize=12, weight='bold', 
                transform=ax2.transAxes, va='top')
        
        # Build comprehensive diagnostic table
        table_data = []
        if model_results:
            for r in model_results:
                if r.get('effect') is not None:
                    # DiD statistics
                    table_data.extend([
                        ['Model', r.get('model', 'Model')],
                        ['Treatment Effect', _format_num(r['effect'])],
                        ['Std. Error', _format_num(r.get('se', 'N/A'))],
                        ['95% CI Lower', _format_num(r['effect'] - 1.96 * r.get('se', 0))],
                        ['95% CI Upper', _format_num(r['effect'] + 1.96 * r.get('se', 0))],
                        ['t-statistic', _format_num(r.get('t_stat', 'N/A'), 4)],
                        ['p-value', _format_num(r.get('p_value', 'N/A'), 4)],
                        ['R-squared', _format_num(r.get('r_squared', 'N/A'), 4)],
                        ['N Observations', str(r.get('n_obs', 'N/A'))],
                        ['Significance', '***' if r.get('p_value', 1) < 0.001 else '**' if r.get('p_value', 1) < 0.01 else '*' if r.get('p_value', 1) < 0.05 else 'ns'],
                    ])
                elif r.get('forecast') is not None:
                    # ARIMA statistics
                    table_data.extend([
                        ['Model', r.get('model', 'Model')],
                        ['Forecast (t+1)', _format_num(r.get('forecast'))],
                        ['AR(1) Coefficient', _format_num(r.get('ar1_coef', 'N/A'), 4)],
                        ['Intercept', _format_num(r.get('intercept', 'N/A'), 4)],
                        ['AIC', _format_num(r.get('aic', 'N/A'), 2)],
                        ['RMSE', _format_num(r.get('rmse', 'N/A'), 6)],
                        ['N Observations', str(r.get('n_obs', 'N/A'))],
                        ['Process Type', 'STABLE' if abs(float(r.get('ar1_coef', 0))) < 1 else 'UNSTABLE'],
                    ])
        
        if table_data:
            # Create table with proper formatting
            table = ax2.table(
                cellText=table_data,
                colLabels=['Statistic', 'Value'],
                cellLoc='left',
                loc='center',
                bbox=[0.0, 0.05, 1.0, 0.88]
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8.5)
            table.scale(1, 2.0)
            
            # Style header
            for i in range(2):
                table[(0, i)].set_facecolor('steelblue')
                table[(0, i)].set_text_props(weight='bold', color='white')
            
            # Alternate row colors and add padding
            for i in range(1, len(table_data) + 1):
                for j in range(2):
                    if i % 2 == 0:
                        table[(i, j)].set_facecolor('whitesmoke')
                    else:
                        table[(i, j)].set_facecolor('white')
                    table[(i, j)].set_edgecolor('lightgray')
                    table[(i, j)].set_linewidth(0.5)
        else:
            ax2.text(0.05, 0.85, "No results available.", fontsize=10, 
                    transform=ax2.transAxes, va='top')
        
        # Footer
        ax2.text(0.05, 0.01, f"Question: {_safe_str(intent.get('outcome'))} vs {_safe_str(intent.get('treatment'))}", 
                fontsize=7, transform=ax2.transAxes, style='italic', color='gray')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    return out_path
