"""
Espresso API server and web entrypoint.

Provides:
- JSON APIs for listing bundled datasets and running analyses
- Web UI entrypoint rendering the Espresso Inference Console
"""

from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from analysis_core import analyze_dataset
from audit_log import list_runs, record_run
from datasets import get_dataset_metadata, get_dataset_path, list_bundled_datasets
from data_utils import load_data
from data_profile import run_data_profile


BASE_DIR = Path(__file__).resolve().parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    @app.route("/", methods=["GET"])
    def index() -> Any:
        # Main Espresso console UI
        return render_template("index.html")

    @app.route("/api/datasets", methods=["GET"])
    def api_datasets() -> Any:
        """List bundled demo datasets with metadata."""
        return jsonify(list_bundled_datasets())

    @app.route("/api/datasets/<dataset_id>/profile", methods=["GET"])
    def api_dataset_profile(dataset_id: str) -> Any:
        """
        Return schema + structural diagnostics for a bundled dataset.
        Used by the console to show data summary before analysis.
        """
        meta = get_dataset_metadata(dataset_id)
        path = get_dataset_path(dataset_id)
        df = load_data(path)
        profile = run_data_profile(df)
        payload: Dict[str, Any] = {
            "dataset": meta,
            "profile": profile,
        }
        return jsonify(payload)

    @app.route("/api/analyze", methods=["POST"])
    def api_analyze() -> Any:
        """
        Run a full analysis on a bundled dataset.

        Expected JSON body:
        {
          "dataset_id": "...",
          "question": "plain English question"
        }
        """
        data = request.get_json(force=True, silent=True) or {}
        dataset_id = data.get("dataset_id")
        question = data.get("question")

        if not dataset_id or not question:
            return (
                jsonify(
                    {
                        "error": "dataset_id and question are required",
                    }
                ),
                400,
            )

        try:
            meta = get_dataset_metadata(dataset_id)
        except KeyError:
            return jsonify({"error": f"Unknown dataset_id '{dataset_id}'"}), 404

        try:
            path = get_dataset_path(dataset_id)
            analysis = analyze_dataset(path, question)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500

        # Record in audit log
        record_run(
            {
                "dataset_id": dataset_id,
                "dataset_name": meta.get("name"),
                "question": question,
                "selected_model": analysis.get("selected_model"),
                "spec_summary": analysis.get("spec_summary"),
                "html_report_path": analysis.get("html_report_path"),
            }
        )

        response: Dict[str, Any] = {
            "dataset": meta,
            "analysis": analysis,
        }
        return jsonify(response)

    @app.route("/api/history", methods=["GET"])
    def api_history() -> Any:
        """
        Return recent inference runs from the audit log.
        """
        limit_param = request.args.get("limit")
        try:
            limit = int(limit_param) if limit_param is not None else 50
        except ValueError:
            limit = 50

        runs = list_runs(limit=limit)
        return jsonify({"runs": runs})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)

