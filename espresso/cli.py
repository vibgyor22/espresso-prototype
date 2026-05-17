"""
Espresso CLI — V3.

Two surfaces:
  - `espresso analyze <file> --question "..."` (one-shot)
  - `espresso` (no args) → interactive REPL

V3 REPL adds: eras, robustness, context, explain, verdict, why not <model>, benchmark.
"""

from __future__ import annotations

import os
import sys
import warnings
warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from typing import Optional

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .ingest import load as ingest_load
from .agent.coordinator import Coordinator
from .agent.session import Session
from .viz.terminal import (
    console, render_header, P, MASCOT,
    render_era_breakdown, render_world_events,
)
from .viz.html_report import create_html_report
from .viz.table_export import export_table
from .whatif import simulate as whatif_simulate
from .glossary import define
from llm import chat_about_result


app = typer.Typer(
    add_completion=False,
    help="Espresso · agentic econometric analyst. Run with no args for the REPL.",
    invoke_without_command=True,
    no_args_is_help=False,
)


# ---------------------------------------------------------------------------
# REPL clarifier
# ---------------------------------------------------------------------------

def _rich_clarifier(question: str, options: list[str]) -> Optional[str]:
    console.print(Panel(
        Text.from_markup(f"[bold yellow]I need your input:[/bold yellow] {question}"),
        border_style="yellow", padding=(0, 1),
    ))
    for i, opt in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}.[/bold cyan] {opt}")
    while True:
        try:
            raw = input("Choose 1-{n} (or type your own): ".format(n=len(options))).strip()
        except (EOFError, KeyboardInterrupt):
            return options[0] if options else None
        if not raw:
            continue
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        return raw


# ---------------------------------------------------------------------------
# Shared loader
# ---------------------------------------------------------------------------

def _load_dataset(path: str, sheet: Optional[str] = None):
    res = ingest_load(path, sheet=sheet)
    if res.error:
        console.print(f"[bold red]Could not load file:[/bold red] {res.error}")
        return None
    if res.needs_sheet_choice:
        console.print(f"[yellow]Excel file has multiple sheets:[/yellow] {res.available_sheets}")
        chosen = _rich_clarifier("Which sheet should I use?", res.available_sheets)
        return _load_dataset(path, sheet=chosen)
    console.print(f"[dim]✓ {path}[/dim] · {len(res.df):,} rows × {len(res.df.columns)} cols"
                  + (f" · sheet=[bold]{res.sheet}[/bold]" if res.sheet else ""))
    return res


# ---------------------------------------------------------------------------
# `analyze` — one-shot
# ---------------------------------------------------------------------------

@app.command(help="One-shot: load a file, run an analysis, render to the terminal.")
def analyze(
    file: str = typer.Argument(..., help="Path to CSV / TSV / XLSX / Parquet."),
    question: str = typer.Option(..., "--question", "-q", help="Your research question."),
    outcome: Optional[str] = typer.Option(None, "--outcome"),
    treatment: Optional[str] = typer.Option(None, "--treatment"),
    unit: Optional[str] = typer.Option(None, "--unit"),
    time: Optional[str] = typer.Option(None, "--time"),
    model: Optional[str] = typer.Option(None, "--model"),
    sheet: Optional[str] = typer.Option(None, "--sheet"),
    forecast_periods: Optional[int] = typer.Option(None, "--forecast-periods"),
    level: str = typer.Option("beginner", "--level"),
    export: Optional[str] = typer.Option(None, "--export"),
    no_clarify: bool = typer.Option(False, "--no-clarify"),
):
    res = _load_dataset(file, sheet=sheet)
    if res is None:
        raise typer.Exit(code=1)
    overrides = {k: v for k, v in dict(
        outcome=outcome, treatment=treatment, unit=unit, time=time, model=model,
    ).items() if v}

    session = Session()
    clarifier = None if no_clarify else _rich_clarifier
    coord = Coordinator(session, clarifier=clarifier)
    coord.attach_data(res.df, path=res.source_path, fmt=res.format, sheet=res.sheet)
    coord.ask(question, overrides=overrides, expertise=level, forecast_periods=forecast_periods)

    if export:
        path = create_html_report(session, export)
        console.print(f"\n[green]HTML dashboard exported:[/green] {path}")


# ---------------------------------------------------------------------------
# `repl` — interactive
# ---------------------------------------------------------------------------

@app.command(help="Start the interactive REPL.")
def repl():
    _run_repl()


@app.callback()
def _default(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        _run_repl()


# ---------------------------------------------------------------------------
# Welcome screen
# ---------------------------------------------------------------------------

def _print_welcome() -> None:
    from .viz.terminal import MASCOT_ART
    inner = (
        f"\n"
        f"{MASCOT_ART}\n"
        f"\n"
        f"  [bold {P['brand']}]E S P R E S S O[/bold {P['brand']}]   "
        f"[dim {P['accent']}]Inference Engine[/dim {P['accent']}]  "
        f"[dim]·[/dim]  [dim {P['accent']}]v3[/dim {P['accent']}]\n"
        f"  [italic {P['plain']}]Agentic econometrics for the terminal.[/italic {P['plain']}]\n"
        f"\n"
        f"  [dim {P['primary']}]──────────────────────────────────────────────────────[/dim {P['primary']}]\n"
        f"\n"
        f"   [{P['brand']}]◈[/{P['brand']}]  Loads any CSV, Excel, Parquet — zero setup\n"
        f"   [{P['brand']}]◈[/{P['brand']}]  Auto-selects the right model from 15+ estimators\n"
        f"   [{P['brand']}]◈[/{P['brand']}]  Runs diagnostics, switches models if assumptions fail\n"
        f"   [{P['brand']}]◈[/{P['brand']}]  Knows real-world events that shaped your data\n"
        f"   [{P['brand']}]◈[/{P['brand']}]  Surfaces what you didn't ask but should know\n"
        f"\n"
        f"  [dim {P['primary']}]──────────────────────────────────────────────────────[/dim {P['primary']}]\n"
        f"\n"
        f"  [bold {P['accent']}]›[/bold {P['accent']}] [bold]load[/bold] [dim]data.csv[/dim]\n"
        f"  [dim {P['accent']}]  then just ask anything, no commands needed[/dim {P['accent']}]\n"
        f"\n"
        f"  [dim]eras · context · robustness · export table · what if · ?term[/dim]\n"
        f"\n"
    )
    console.print(Panel(
        Text.from_markup(inner),
        border_style=f"bold {P['primary']}",
        box=box.DOUBLE,
        padding=(0, 2),
    ))
    console.print(f"  [bold {P['brand']}]{MASCOT}[/bold {P['brand']}]  "
                  f"[{P['primary']}]ready  ›[/{P['primary']}]\n")


# ---------------------------------------------------------------------------
# REPL implementation
# ---------------------------------------------------------------------------

def _run_repl():
    _print_welcome()
    session = Session()
    coord: Optional[Coordinator] = None
    last_followups: list[str] = []
    _explain_mode = [False]

    def need_data() -> bool:
        if session.df is None:
            console.print("[yellow]No data loaded yet. Use:[/yellow] [bold]load <path-to-file>[/bold]")
            return True
        return False

    def need_result() -> bool:
        if not session.result:
            console.print("[yellow]No result yet. First run:[/yellow] [bold]ask <question>[/bold]")
            return True
        return False

    while True:
        try:
            raw = input(f"\n{MASCOT}  ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n[dim {P['accent']}]bye.[/dim {P['accent']}]")
            return

        if not raw:
            continue

        # ?term → glossary
        if raw.startswith("?"):
            console.print(Panel(define(raw), title=f"?{raw.lstrip('?').strip()}",
                                border_style="cyan", title_align="left"))
            continue

        if raw in ("exit", "quit"):
            console.print(f"[dim {P['accent']}]bye.[/dim {P['accent']}]")
            return

        if raw in ("help", "?", "h"):
            _print_help()
            continue

        # ── load ──
        if raw.startswith("load "):
            path = raw[5:].strip().strip('"\'')
            res = _load_dataset(path)
            if res is None:
                continue
            session = Session()
            coord = Coordinator(session, clarifier=_rich_clarifier)
            coord.attach_data(res.df, path=res.source_path, fmt=res.format, sheet=res.sheet)
            continue

        # ── ask ──
        if raw.startswith("ask "):
            if need_data():
                continue
            question = raw[4:].strip().strip('"\'')
            session = Session()
            coord = Coordinator(session, clarifier=_rich_clarifier)
            res_df = _last_df_holder.get("df")
            if res_df is None:
                console.print("[red]Internal: no dataframe held. Reload your file.[/red]")
                continue
            coord.attach_data(res_df["df"], path=res_df["path"], fmt=res_df["fmt"], sheet=res_df["sheet"])
            coord.ask(question)
            last_followups = list(session.followups or [])
            if last_followups:
                chosen = _show_countdown_menu(last_followups)
                if chosen and 1 <= chosen <= len(last_followups):
                    raw = str(chosen)  # fall through to the number-picker below
                    # re-process as if user typed the number
                    picked = last_followups[chosen - 1]
                    console.print(f"[dim {P['accent']}]→ auto-running follow-up {chosen}:[/dim {P['accent']}]  {picked}")
                    res_df2 = _last_df_holder.get("df")
                    session = Session()
                    coord2  = Coordinator(session, clarifier=_rich_clarifier)
                    if res_df2:
                        coord2.attach_data(res_df2["df"], path=res_df2["path"], fmt=res_df2["fmt"], sheet=res_df2["sheet"])
                    coord2.ask(picked)
                    last_followups = list(session.followups or [])
            continue

        # ── what if ──
        if raw.startswith("what if"):
            if need_result():
                continue
            _handle_whatif(session, raw)
            continue

        # ── export ──
        if raw == "export" or raw.startswith("export "):
            if need_result():
                continue
            parts = raw.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""

            if arg == "table" or arg.startswith("table"):
                # LaTeX + Markdown regression table
                try:
                    fname = arg[6:].strip() or "espresso_table"
                    md, tex = export_table(session)
                    stem = fname.replace(".md","").replace(".tex","")
                    with open(stem + ".md",  "w", encoding="utf-8") as f: f.write(md)
                    with open(stem + ".tex", "w", encoding="utf-8") as f: f.write(tex)
                    console.print(f"[{P['success']}]Table exported:[/{P['success']}]  "
                                  f"[dim]{stem}.md[/dim]  and  [dim]{stem}.tex[/dim]")
                    console.print()
                    console.print(md)
                except Exception as e:
                    console.print(f"[red]Table export failed:[/red] {e}")
            else:
                target = arg or None
                try:
                    path = create_html_report(session, target)
                    console.print(f"[{P['success']}]Exported:[/{P['success']}] {path}")
                except Exception as e:
                    console.print(f"[red]Export failed:[/red] {e}")
            continue

        # ── show commands ──
        if raw == "show profile":
            from .viz.terminal import render_profile
            if session.profile is not None:
                render_profile(session.profile)
            else:
                console.print("[yellow]No profile available.[/yellow]")
            continue

        if raw == "show interpretation":
            from .viz.terminal import render_interpretation
            if session.interpretation_blocks:
                render_interpretation(session.interpretation_blocks, expertise=session.expertise)
            else:
                console.print("[yellow]No interpretation yet.[/yellow]")
            continue

        # ── V3 REPL commands ──

        if raw == "eras":
            if need_result():
                continue
            eras = getattr(session, "era_effects", None)
            if eras:
                render_era_breakdown(eras)
            else:
                console.print(f"[dim]No era breakdown available. Requires time-series data spanning >10 years.[/dim]")
            continue

        if raw == "context":
            if need_result():
                continue
            events = getattr(session, "world_events", None)
            if events:
                outcome = session.intent.get("outcome", "") if session.intent else ""
                render_world_events(events, outcome_col=outcome)
            else:
                console.print(f"[dim]No world context available for this analysis.[/dim]")
            continue

        if raw == "explain":
            _explain_mode[0] = not _explain_mode[0]
            state = "ON" if _explain_mode[0] else "OFF"
            console.print(f"[dim]Plain-English annotation mode: [bold]{state}[/bold][/dim]")
            continue

        if raw == "verdict":
            if need_result():
                continue
            vt = getattr(session, "verdict_text", None)
            score = getattr(session, "confidence_score", None)
            if vt and score:
                from .viz.terminal import render_verdict
                caveat = (session.interpretation_blocks or {}).get("sanity_check", "")
                _first_line = next((l.strip() for l in (caveat or "").splitlines() if l.strip()), "")
                # Strip bullet prefix
                import re
                _first_line = re.sub(r"^[\-\*•·]+\s*", "", _first_line)
                render_verdict(vt, score, caveat=_first_line[:120])
            else:
                console.print(f"[dim]No verdict yet. Run an analysis first.[/dim]")
            continue

        if raw == "robustness":
            if need_result():
                continue
            rob = getattr(session, "robustness_table", None)
            if rob:
                _print_robustness(rob)
            else:
                console.print(f"[dim {P['accent']}]Running robustness checks…[/dim {P['accent']}]")
                try:
                    from .agent.robustness import run_robustness
                    rob = run_robustness(session)
                    session.robustness_table = rob
                    _print_robustness(rob)
                except Exception as e:
                    console.print(f"[dim]Robustness not available: {e}[/dim]")
            continue

        if raw.startswith("split by "):
            if need_result():
                continue
            col = raw[9:].strip()
            console.print(f"[dim]Splitting analysis by [bold]{col}[/bold]…[/dim]")
            try:
                from .agent.heterogeneity import split_by
                ht = split_by(session, col)
                _print_heterogeneity(ht, col)
            except Exception as e:
                console.print(f"[dim]Split failed: {e}[/dim]")
            continue

        if raw.startswith("why not "):
            if need_result():
                continue
            model = raw[8:].strip()
            rejected = getattr(session, "model_rejected", {}) or {}
            if model in rejected:
                console.print(Panel(rejected[model], title=f"Why not {model}",
                                    border_style=P["accent"]))
            elif rejected:
                console.print(f"  Models rejected: {', '.join(rejected.keys())}")
            else:
                console.print("[dim]No rejection info available.[/dim]")
            continue

        if raw in ("how certain", "confidence"):
            if need_result():
                continue
            score = getattr(session, "confidence_score", None)
            if score:
                _print_confidence_breakdown(score)
            else:
                console.print("[dim]No confidence score yet.[/dim]")
            continue

        if raw in ("benchmark", "law?"):
            if need_result():
                continue
            law = getattr(session, "known_law", None)
            if law:
                console.print(Panel(law, title="Economic benchmark",
                                    border_style=P["world"]))
            else:
                console.print("[dim]No benchmark found for this variable pair.[/dim]")
            continue

        # ── pick follow-up by number ──
        if raw.isdigit() and last_followups and 1 <= int(raw) <= len(last_followups):
            picked = last_followups[int(raw) - 1]
            console.print(f"[dim {P['accent']}]→[/dim {P['accent']}]  {picked}")
            res_df = _last_df_holder.get("df")
            session = Session()
            coord = Coordinator(session, clarifier=_rich_clarifier)
            if res_df:
                coord.attach_data(res_df["df"], path=res_df["path"], fmt=res_df["fmt"], sheet=res_df["sheet"])
            coord.ask(picked)
            last_followups = list(session.followups or [])
            continue

        # ── natural conversation: chat about existing result OR run new analysis ──
        if _last_df_holder.get("df"):
            if not _is_new_analysis_request(raw, session):
                # User is chatting about the current result — no re-run needed
                ctx = _session_context_for_chat(session)
                reply = chat_about_result(raw, ctx)
                if reply:
                    console.print(Panel(
                        reply,
                        border_style=P["accent"], padding=(0, 2),
                        title=f"[dim {P['accent']}]espresso[/dim {P['accent']}]",
                        title_align="left",
                    ))
                else:
                    console.print(f"[dim]Run an analysis first, then ask me anything about the results.[/dim]")
            else:
                # Fresh analytical question — spin up a new session and run the pipeline
                session = Session()
                coord = Coordinator(session, clarifier=_rich_clarifier)
                res_df = _last_df_holder["df"]
                coord.attach_data(res_df["df"], path=res_df["path"], fmt=res_df["fmt"], sheet=res_df["sheet"])
                coord.ask(raw)
                last_followups = list(session.followups or [])
                if last_followups:
                    chosen = _show_countdown_menu(last_followups)
                    if chosen and 1 <= chosen <= len(last_followups):
                        picked = last_followups[chosen - 1]
                        console.print(f"[dim {P['accent']}]→ running:[/dim {P['accent']}]  {picked}")
                        session = Session()
                        coord2  = Coordinator(session, clarifier=_rich_clarifier)
                        res_df2 = _last_df_holder.get("df")
                        if res_df2:
                            coord2.attach_data(res_df2["df"], path=res_df2["path"], fmt=res_df2["fmt"], sheet=res_df2["sheet"])
                        coord2.ask(picked)
                        last_followups = list(session.followups or [])
        else:
            console.print(
                f"  [{P['accent']}]No data loaded yet.[/{P['accent']}]  "
                f"[dim]Use [bold]load <path>[/bold] to load a CSV, Excel, or Parquet file.[/dim]"
            )


# We keep the most recently loaded df around so `ask` and follow-ups can reuse
# it across freshly created sessions.
_last_df_holder: dict = {}

# ---------------------------------------------------------------------------
# Conversational chat helpers
# ---------------------------------------------------------------------------

_ANALYSIS_TRIGGERS = (
    "what is the effect of", "what's the effect of",
    "effect of ", "impact of ",
    "predict ", "forecast ",
    "relationship between ", "correlation between ",
    "does ", "is there a ", "how does ",
    "what drives ", "what causes ",
    "regress ", "run an analysis", "run analysis",
)


def _is_new_analysis_request(text: str, session) -> bool:
    """Return True if this looks like a fresh analytical run rather than
    a conversational question about the existing result."""
    if not session or not getattr(session, "result", None):
        return True
    low = text.lower().strip()
    # Very short messages are almost always conversational
    if len(low.split()) <= 5:
        return False
    has_trigger = any(t in low for t in _ANALYSIS_TRIGGERS)
    if not has_trigger:
        return False
    # Even with a trigger, if the message names the same outcome+treatment
    # the user is probably asking about the current result, not starting fresh.
    intent = getattr(session, "intent", None) or {}
    outcome = str(intent.get("outcome", "")).lower()
    treatment = str(intent.get("treatment", "")).lower()
    if outcome and outcome in low and treatment and treatment in low:
        return False
    return True


def _session_context_for_chat(session) -> dict:
    result = session.result or {}
    intent = session.intent or {}
    interp = session.interpretation_blocks or {}
    eff = result.get("treatment_effect", result.get("slope", result.get("effect", "?")))
    return {
        "model_key": session.model_key or "unknown",
        "outcome": intent.get("outcome", "?"),
        "treatment": intent.get("treatment", "?"),
        "eff": eff,
        "pval": result.get("pval", result.get("p_value", "?")),
        "r2": result.get("r2", "?"),
        "n_obs": result.get("n_obs", result.get("nobs", "?")),
        "verdict": getattr(session, "verdict_text", "") or "",
        "mechanism": interp.get("mechanism", ""),
    }


# ---------------------------------------------------------------------------
# Helper renderers for new REPL commands
# ---------------------------------------------------------------------------

def _print_robustness(rob: list) -> None:
    if not rob:
        return
    t = Table(title="Robustness check", box=box.SIMPLE,
              header_style=f"bold {P['primary']}", show_lines=False)
    t.add_column("Model", style="bold")
    t.add_column("Effect", justify="right")
    t.add_column("p", justify="right")
    t.add_column("Consistent?")
    for row in rob:
        p = row.get("pvalue", 1.0)
        p_color = P["success"] if p < 0.05 else (P["warning"] if p < 0.1 else P["neutral"])
        consistent = row.get("consistent", "")
        c_color = P["success"] if "✓" in consistent else (P["danger"] if "✗" in consistent else P["neutral"])
        t.add_row(
            row.get("model", ""),
            f"{row.get('estimate', 0.0):+.3f}",
            f"[{p_color}]{p:.3f}[/{p_color}]",
            f"[{c_color}]{consistent}[/{c_color}]",
        )
    console.print(t)


def _print_heterogeneity(ht: list, col: str) -> None:
    if not ht:
        return
    t = Table(title=f"Effect by {col}", box=box.SIMPLE,
              header_style=f"bold {P['primary']}", show_lines=False)
    t.add_column("Group", style="bold")
    t.add_column("N", justify="right")
    t.add_column("Effect", justify="right")
    t.add_column("p", justify="right")
    for row in ht:
        p = row.get("pvalue", 1.0)
        p_color = P["success"] if p < 0.05 else P["neutral"]
        t.add_row(
            str(row.get("group", "")),
            str(row.get("n", "")),
            f"{row.get('estimate', 0.0):+.3f}",
            f"[{p_color}]{p:.3f}[/{p_color}]",
        )
    console.print(t)


def _print_confidence_breakdown(score: dict) -> None:
    console.print()
    console.print(f"  [{P['brand']}]Espresso Confidence Score:  "
                  f"{score['score']} / 100  {score['bullet']}[/{P['brand']}]")
    console.print()
    from .viz.terminal import _block_bar
    console.print(f"  [dim]Statistical significance[/dim]  "
                  f"{_block_bar(score['sig'] * 30 // 40)}  [dim]{score['sig']}/40[/dim]")
    console.print(f"  [dim]Diagnostic health      [/dim]  "
                  f"{_block_bar(score['diag'] * 30 // 25)}  [dim]{score['diag']}/25[/dim]")
    console.print(f"  [dim]Sample adequacy        [/dim]  "
                  f"{_block_bar(score['samp'] * 30 // 20)}  [dim]{score['samp']}/20[/dim]")
    console.print(f"  [dim]Era stability          [/dim]  "
                  f"{_block_bar(score['era'] * 30 // 15)}  [dim]{score['era']}/15[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# what-if handler
# ---------------------------------------------------------------------------

def _show_countdown_menu(followups: list, secs: int = 8) -> int:
    """
    Show a live countdown after analysis completes.
    Returns selected index (1-based) or 0 for skip.
    This is the UX moment: the tool anticipates the next step.
    """
    if not followups:
        return 0
    from .viz.terminal import _followup_countdown, P as _P, MASCOT as _M
    n = len(followups)
    console.print(
        f"\n  [{_P['brand']}]{_M}[/{_P['brand']}]  "
        f"[{_P['primary']}]auto-running #1 in {secs}s[/{_P['primary']}]  "
        f"[dim](press 1–{n} to choose, Enter to skip)[/dim]"
    )
    return _followup_countdown(n, secs)


def _handle_whatif(session: Session, raw: str) -> None:
    import re
    body = raw[7:].strip()
    m = re.match(r"shock\s*=\s*(-?\d+(?:\.\d+)?)", body, re.I)
    if m:
        wi = whatif_simulate(session.result, {"shock": float(m.group(1))})
        console.print(Panel(wi.explanation, title="What-if · forecast shock",
                            border_style="magenta"))
        return
    m = re.match(r"([A-Za-z_][\w\-]*)\s*=\s*(-?\d+(?:\.\d+)?)", body)
    if m:
        try:
            wi = whatif_simulate(session.result, {"x": float(m.group(2)), "x_mean": session.result.get("x_mean")})
            console.print(Panel(
                wi.explanation
                + (f"\n95% CI: [{wi.ci_lower:.3f}, {wi.ci_upper:.3f}]" if wi.ci_lower is not None else ""),
                title=f"What-if · {m.group(1)} = {m.group(2)}",
                border_style="magenta",
            ))
            return
        except Exception as e:
            console.print(f"[red]What-if failed:[/red] {e}")
            return
    console.print("[yellow]Format:[/yellow] [bold]what if <var> = <number>[/bold] or [bold]what if shock = <number>[/bold]")


def _print_help() -> None:
    body = (
        f"[bold {P['brand']}]Analysis[/bold {P['brand']}]\n"
        "  load <path>            Load a CSV/TSV/XLSX/Parquet file.\n"
        "  ask <question>         Run an analysis.\n"
        "  <question>             Same as ask if line looks like a question.\n"
        "  what if <var> = <n>    Predict outcome at a scenario value.\n"
        "  what if shock = <n>    Forecast shock simulation.\n\n"
        f"[bold {P['brand']}]Explore results[/bold {P['brand']}]\n"
        "  eras                   Effect across historical time periods.\n"
        "  context                Real-world events that shaped the data.\n"
        "  robustness             Stress-test across alternative model specs.\n"
        "  split by <col>         Subgroup effect analysis.\n"
        "  why not <model>        Why a model was rejected.\n"
        "  how certain            Confidence score breakdown.\n"
        "  benchmark              Literature benchmarks for this relationship.\n"
        "  verdict                Re-show the Espresso Verdict.\n"
        "  explain                Toggle plain-English annotation mode.\n\n"
        f"[bold {P['brand']}]Other[/bold {P['brand']}]\n"
        "  ?<term>                Define a statistics term (e.g. ?p-value).\n"
        "  show profile           Re-print the data profile.\n"
        "  show interpretation    Re-print the latest interpretation.\n"
        "  export [path.html]     Save interactive HTML dashboard.\n"
        "  <number>               Pick a follow-up by number.\n"
        "  help / exit\n"
    )
    console.print(Panel(Text.from_markup(body), title="Help", border_style=P["primary"]))


# ---------------------------------------------------------------------------
# Wrap attach_data to cache df for REPL reuse
# ---------------------------------------------------------------------------

_orig_attach = Coordinator.attach_data


def _attach_and_cache(self, df, *, path="", fmt="", sheet=None):
    _last_df_holder["df"] = {"df": df, "path": path, "fmt": fmt, "sheet": sheet}
    return _orig_attach(self, df, path=path, fmt=fmt, sheet=sheet)


Coordinator.attach_data = _attach_and_cache  # type: ignore


def main():  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
