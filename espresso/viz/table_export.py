"""
Regression table export — Markdown and LaTeX (stargazer-style).

Usage:
  from espresso.viz.table_export import export_table
  md, tex = export_table(session)
  # or multi-column: export_table(sessions=[s1, s2, s3])
"""

from __future__ import annotations

from typing import Optional
import os


def _stars(p: float) -> str:
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    if p < 0.10:  return "†"
    return ""


def export_table(session=None, sessions: Optional[list] = None,
                 path: Optional[str] = None) -> tuple[str, str]:
    """
    Build Markdown and LaTeX regression tables.

    Single session:  export_table(session)
    Multi-column:    export_table(sessions=[s1, s2, s3])

    Returns (markdown_str, latex_str). Optionally writes to path.stem.md and path.stem.tex.
    """
    cols = sessions if sessions else ([session] if session else [])
    cols = [s for s in cols if s and getattr(s, "result", None)]
    if not cols:
        return ("No results to export.", "% No results to export.")

    # ── column metadata ──
    headers = []
    for i, s in enumerate(cols, 1):
        model = getattr(s, "model_display", f"Model {i}")
        outcome = (getattr(s, "intent", {}) or {}).get("outcome", "Y")
        headers.append(f"({i}) {outcome}")

    # ── row data ──
    # For single model we show all available key/value pairs from result
    def _get_num(s, key, default=None):
        v = s.result.get(key, default)
        try:
            return float(v)
        except Exception:
            return default

    def _fmt(v, decimals=4):
        if v is None: return "—"
        return f"{v:.{decimals}f}"

    def _fmt_n(n):
        if n is None: return "—"
        return f"{int(n):,}"

    rows_data = []
    for s in cols:
        r = s.result or {}
        intent = getattr(s, "intent", {}) or {}
        treatment = intent.get("treatment", "Predictor")
        eff   = _get_num(s, "treatment_effect") or _get_num(s, "slope") or _get_num(s, "effect", 0)
        se    = _get_num(s, "se", 0)
        pval  = _get_num(s, "pvalue") or _get_num(s, "p_value", 1)
        ci_lo = _get_num(s, "ci_lower", (eff or 0) - 1.96 * (se or 0))
        ci_hi = _get_num(s, "ci_upper", (eff or 0) + 1.96 * (se or 0))
        r2    = _get_num(s, "r_squared", 0)
        n     = _get_num(s, "n_obs")
        fe    = r.get("fe_type", "")
        se_t  = r.get("se_type", "")
        rows_data.append({
            "treatment": treatment,
            "eff": eff, "se": se, "pval": pval,
            "ci_lo": ci_lo, "ci_hi": ci_hi,
            "r2": r2, "n": n, "fe": fe, "se_type": se_t,
            "model": getattr(s, "model_display", "OLS"),
        })

    # ── Markdown table ──
    def _md_table() -> str:
        sep  = " | "
        lines = []
        # Header
        lines.append("| Variable" + sep + sep.join(headers) + " |")
        lines.append("|---" + ("|---" * len(cols)) + "|")
        # Coefficient rows
        treatments = list(dict.fromkeys(d["treatment"] for d in rows_data))
        for t in treatments:
            coef_cells = []
            se_cells   = []
            for d in rows_data:
                if d["treatment"] == t:
                    stars = _stars(d["pval"] or 1)
                    coef_cells.append(f"{(d['eff'] or 0):+.4f}{stars}")
                    se_cells.append(f"({(d['se'] or 0):.4f})")
                else:
                    coef_cells.append("—")
                    se_cells.append("")
            lines.append(f"| **{t}**" + sep + sep.join(coef_cells) + " |")
            lines.append(f"|" + sep + sep.join(se_cells) + " |")

        # Separator
        lines.append("|" + (" |" * (len(cols) + 1)))
        # Stats
        lines.append("| **R²**" + sep + sep.join(_fmt(d["r2"]) for d in rows_data) + " |")
        lines.append("| **N**"  + sep + sep.join(_fmt_n(d["n"])  for d in rows_data) + " |")

        fe_vals = [d["fe"] or "—" for d in rows_data]
        if any(v and v != "—" for v in fe_vals):
            lines.append("| **Fixed Effects**" + sep + sep.join(fe_vals) + " |")

        se_vals = [d["se_type"] or "OLS" for d in rows_data]
        lines.append("| **SE type**" + sep + sep.join(se_vals) + " |")

        lines.append("")
        lines.append("*p < 0.10, **p < 0.05, ***p < 0.01, †p < 0.10")
        lines.append("*Standard errors in parentheses.*")
        return "\n".join(lines)

    # ── LaTeX table ──
    def _tex_table() -> str:
        nc = len(cols)
        col_spec = "l" + "c" * nc
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Regression Results}",
            r"\label{tab:results}",
            r"\begin{tabular}{" + col_spec + "}",
            r"\hline\hline",
        ]
        # Header row
        header_row = " & " + " & ".join(f"\\textbf{{{h}}}" for h in headers) + r" \\"
        lines.append(header_row)
        lines.append(r"\hline")

        # Coefficient rows
        treatments = list(dict.fromkeys(d["treatment"] for d in rows_data))
        for t in treatments:
            coef_cells = []
            se_cells   = []
            for d in rows_data:
                if d["treatment"] == t:
                    stars = _stars(d["pval"] or 1).replace("*", "$^{*}$").replace("†", "$^{\\dagger}$")
                    coef_cells.append(f"{(d['eff'] or 0):+.4f}{stars}")
                    se_cells.append(f"({(d['se'] or 0):.4f})")
                else:
                    coef_cells.append("")
                    se_cells.append("")
            lines.append(f"{t.replace('_', ' ')} & " + " & ".join(coef_cells) + r" \\")
            lines.append(" & " + " & ".join(se_cells) + r" \\")

        lines.append(r"\hline")
        # Stats
        lines.append(r"$R^2$ & " + " & ".join(_fmt(d["r2"]) for d in rows_data) + r" \\")
        lines.append(r"$N$ & "   + " & ".join(_fmt_n(d["n"])  for d in rows_data) + r" \\")

        fe_vals = [d["fe"] or "—" for d in rows_data]
        if any(v and v != "—" for v in fe_vals):
            lines.append("Fixed Effects & " + " & ".join(v.replace("_", " ") for v in fe_vals) + r" \\")

        se_vals = [d["se_type"] or "OLS" for d in rows_data]
        lines.append("SE Type & " + " & ".join(se_vals) + r" \\")

        lines += [
            r"\hline\hline",
            r"\multicolumn{" + str(nc + 1) + r"}{l}{\footnotesize{$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$, $^{\dagger}p<0.10$. Standard errors in parentheses.}}\\",
            r"\end{tabular}",
            r"\end{table}",
        ]
        return "\n".join(lines)

    md  = _md_table()
    tex = _tex_table()

    if path:
        stem = os.path.splitext(path)[0]
        with open(stem + ".md",  "w", encoding="utf-8") as f:
            f.write(md)
        with open(stem + ".tex", "w", encoding="utf-8") as f:
            f.write(tex)

    return md, tex
