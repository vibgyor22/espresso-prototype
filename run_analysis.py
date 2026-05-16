"""
Backwards-compatibility shim.

The full CLI now lives in `espresso.cli`. This wrapper preserves the legacy
invocation:

    python run_analysis.py --data path/to/data.csv --question "..."

so existing users and scripts keep working. New users should prefer:

    espresso analyze path/to/data.csv --question "..."

or the interactive REPL:

    espresso
"""

from __future__ import annotations

import argparse
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

from model_specs import MODEL_SPECS


def main() -> int:
    parser = argparse.ArgumentParser(description="Espresso (legacy entry — prefer `espresso analyze`)")
    parser.add_argument("--data", help="Path to data file (csv / tsv / xlsx / parquet)")
    parser.add_argument("--question", help="Research question")
    parser.add_argument("--model", choices=sorted(MODEL_SPECS.keys()), help="Optional model override")
    parser.add_argument("--forecast-periods", type=int)
    parser.add_argument("--outcome")
    parser.add_argument("--treatment")
    parser.add_argument("--unit")
    parser.add_argument("--time")
    parser.add_argument("--level", default="beginner")
    parser.add_argument("--export", help="Export an HTML dashboard to this path.")
    parser.add_argument("--no-clarify", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()

    if args.list_models:
        for name, spec in MODEL_SPECS.items():
            print(f"{name:<18} {spec['display_name']}")
            print(f"  Type: {spec['question_type']}")
            print(f"  {spec['description']}\n")
        return 0

    if not args.data or not args.question:
        parser.error("--data and --question are required unless --list-models is used")

    from espresso.ingest import load as ingest_load
    from espresso.agent.coordinator import Coordinator
    from espresso.agent.session import Session
    from espresso.viz.html_report import create_html_report
    from espresso.cli import _rich_clarifier

    res = ingest_load(args.data)
    if res.error:
        print(f"ERROR: {res.error}")
        return 1
    if res.needs_sheet_choice:
        print("ERROR: Excel file has multiple sheets — pick one with `espresso analyze ... --sheet NAME`.")
        return 1

    overrides = {k: v for k, v in dict(
        outcome=args.outcome, treatment=args.treatment, unit=args.unit, time=args.time,
        model=args.model,
    ).items() if v}

    session = Session()
    clarifier = None if args.no_clarify else _rich_clarifier
    coord = Coordinator(session, clarifier=clarifier)
    coord.attach_data(res.df, path=res.source_path, fmt=res.format, sheet=res.sheet)
    coord.ask(args.question, overrides=overrides, expertise=args.level,
              forecast_periods=args.forecast_periods)

    if args.export:
        path = create_html_report(session, args.export)
        print(f"\nHTML dashboard exported: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
