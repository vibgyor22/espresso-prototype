"""
Agent coordinator.

Drives the analysis end-to-end with a deterministic order of steps that we
*present* agentically: each step streams to the terminal with an icon, a
one-line justification, and a status indicator. When diagnostics fail
critically, the agent decides to switch models, *announces why*, and re-runs.

Why deterministic instead of free-form LLM tool calling: reliability. The user
needs to trust the numbers. The LLM still drives the narration, the column
mapping, the qualitative interpretation, the follow-ups, and the clarification
questions — but the *order of operations* is fixed and audited.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import pandas as pd

from . import tools as T
from . import context as C
from .session import Session, AgentStep
from ..profiling import profile as build_profile, summary_for_llm
from ..viz.terminal import (
    console, render_header, render_profile, render_diagnostics,
    render_forecast, render_regression, render_tool_call,
    render_interpretation, render_followups, thinking,
    render_world_events, render_era_breakdown, render_verdict,
    render_histogram, render_correlation_heatmap,
    compute_confidence_score, render_equation,
    render_marginal_effects, render_deep_block, render_proactive_insights,
    render_animated_result, render_qq_plot,
)


# Type for the optional UI clarifier (returns a chosen option label).
Clarifier = Callable[[str, list[str]], Optional[str]]


class Coordinator:
    """Owns a Session and runs an analysis through it."""

    def __init__(
        self,
        session: Optional[Session] = None,
        *,
        clarifier: Optional[Clarifier] = None,
        verbose: bool = True,
    ):
        self.s = session or Session()
        self.clarifier = clarifier
        self.verbose = verbose

    # ------------------------------------------------------------------ ui
    def _emit(self, tool: str, args: dict, preview: str, why: str, status: str = "ok") -> None:
        step = self.s.log_tool(tool, args, preview, why, status)
        if self.verbose:
            render_tool_call(step)

    def _emit_thought(self, text: str) -> None:
        self.s.log_thought(text)
        if self.verbose:
            console.print(f"[dim italic]  {text}[/dim italic]")

    # ------------------------------------------------------------------ steps
    def attach_data(self, df: pd.DataFrame, *, path: str = "", fmt: str = "", sheet: Optional[str] = None) -> None:
        self.s.df = df
        self.s.source_path = path
        self.s.source_format = fmt
        self.s.sheet = sheet
        self.s.profile = build_profile(df)
        self._emit(
            "profile_data",
            {"path": path, "format": fmt, "sheet": sheet},
            preview=f"{df.shape[0]:,} rows × {df.shape[1]} cols • {self.s.profile.structure}",
            why="Reading and profiling your data so I know what columns we have and how they're shaped.",
        )
        if self.verbose:
            render_profile(self.s.profile, df=df)
            render_correlation_heatmap(df)
            # Histogram for the most likely outcome column
            if self.s.profile and self.s.profile.candidate_outcome_cols:
                oc = self.s.profile.candidate_outcome_cols[0]
                if oc in df.columns:
                    render_histogram(df[oc], col_name=oc)

    def ask(self, question: str, *, overrides: Optional[dict] = None, expertise: str = "beginner",
            forecast_periods: Optional[int] = None) -> Session:
        """Run the full analysis for a question against the attached data."""
        if self.s.df is None:
            raise ValueError("No data attached. Call attach_data(df) first.")
        self.s.question = question
        self.s.overrides = dict(overrides or {})
        self.s.expertise = expertise

        render_header(question=question, source=self.s.source_path or "(in-memory)",
                      structure=self.s.profile.structure if self.s.profile else "?")

        # 1) Parse intent
        with thinking("reading your question…"):
            intent = T.parse_question(question)
        if not intent:
            intent = {}
        intent["question"] = question
        for k in ("outcome", "treatment", "unit", "time"):
            if self.s.overrides.get(k):
                intent[k] = self.s.overrides[k]
        self.s.intent = intent
        self._emit("parse_question", {"text": question},
                   preview=f"type={intent.get('question_type')}, outcome={intent.get('outcome')}, treatment={intent.get('treatment')}",
                   why="Figuring out what kind of question this is (effect / forecast / association) and what variables you're asking about.")

        # 2) Map columns
        with thinking("mapping columns…"):
            mapping = T.map_columns(intent, self.s.df, summary_for_llm(self.s.profile))
        # Honor overrides as the final word
        for k in ("outcome", "treatment", "unit", "time"):
            if self.s.overrides.get(k):
                mapping[k] = {"type": "column", "value": self.s.overrides[k]}
        self.s.mapping = mapping
        self._emit("map_columns", {"intent_keys": list(intent.keys())},
                   preview=f"outcome={_pp(mapping.get('outcome'))}, treatment={_pp(mapping.get('treatment'))}",
                   why="Matching the words in your question to actual columns in your dataset.")

        # 2b) Clarify if outcome is genuinely ambiguous (or mapping failed)
        if not _pp(mapping.get("outcome")):
            if self.s.profile and self.s.profile.candidate_outcome_cols:
                opts = self.s.profile.candidate_outcome_cols[:5]
                chosen = self._clarify(
                    f"I couldn't automatically match the outcome column for: '{question}'. Which column should I use?",
                    opts,
                    why="Column mapping failed or was ambiguous — picking from the most likely numeric candidates."
                )
                if chosen:
                    mapping["outcome"] = {"type": "column", "value": chosen}
                    intent["outcome"] = chosen
        if not _pp(mapping.get("treatment")) and intent.get("treatment"):
            if self.s.profile and self.s.profile.candidate_treatment_cols:
                opts = self.s.profile.candidate_treatment_cols[:5]
                chosen = self._clarify(
                    f"Which column should I use as the predictor ('{intent.get('treatment')}')?",
                    opts,
                    why="Column mapping failed — picking from candidate numeric columns."
                )
                if chosen:
                    mapping["treatment"] = {"type": "column", "value": chosen}
                    intent["treatment"] = chosen

        # 3) Prepare data
        new_df, intent = T.prepare_data(self.s.df, mapping, intent)
        self.s.df = new_df
        self.s.intent = intent
        self._emit("prepare_data", {},
                   preview=f"{len(new_df):,} rows ready"
                            + (f" • filtered to {intent.get('identified_unit')}" if intent.get("identified_unit") else ""),
                   why=("Reshaping/filtering the data so the model sees one row per observation. "
                        + ("I pivoted year columns into long form. " if mapping.get("pivot") else "")
                        + (f"I also focused on '{intent.get('identified_unit')}' as you asked." if intent.get("identified_unit") else "")))

        # 3b) Reject categorical/string outcome columns — remap to a numeric candidate
        outcome_col = intent.get("outcome")
        if outcome_col and outcome_col in self.s.df.columns:
            if not pd.api.types.is_numeric_dtype(self.s.df[outcome_col]):
                numeric_candidates = [
                    c for c in self.s.df.columns
                    if pd.api.types.is_numeric_dtype(self.s.df[c])
                    and c != outcome_col
                    and self.s.df[c].nunique() > 5
                ]
                if numeric_candidates:
                    new_outcome = numeric_candidates[0]
                    self._emit_thought(
                        f"Outcome '{outcome_col}' is non-numeric (categorical). "
                        f"Remapping to '{new_outcome}' which is the first numeric candidate."
                    )
                    intent["outcome"] = new_outcome
                    self.s.intent = intent

        # 3c) Lag construction — when question asks about lead/lag/predict future/Granger
        _lag_keywords = ("lag", "lead", "predict future", "granger", "future unemployment",
                         "future stock", "future return", "future volatility", "predict next")
        q_lower = question.lower()
        if any(kw in q_lower for kw in _lag_keywords):
            treatment_col = intent.get("treatment")
            time_col_lag = intent.get("time")
            if (treatment_col and treatment_col in self.s.df.columns
                    and time_col_lag and time_col_lag in self.s.df.columns):
                try:
                    lag_col = f"{treatment_col}_lag1"
                    if lag_col not in self.s.df.columns:
                        sort_cols = [c for c in (intent.get("unit"), time_col_lag) if c and c in self.s.df.columns]
                        df_sorted = self.s.df.sort_values(sort_cols) if sort_cols else self.s.df.copy()
                        if intent.get("unit") and intent["unit"] in self.s.df.columns:
                            df_sorted[lag_col] = df_sorted.groupby(intent["unit"])[treatment_col].shift(1)
                        else:
                            df_sorted[lag_col] = df_sorted[treatment_col].shift(1)
                        self.s.df = df_sorted
                    intent["treatment"] = lag_col
                    self.s.intent = intent
                    self._emit_thought(
                        f"Lag detected in question — using 1-period lagged {treatment_col} as predictor."
                    )
                except Exception:
                    pass

        # 4) Select model
        sel = T.select_model(intent, self.s.df, override=self.s.overrides.get("model"))

        # Auto-reframe: causal_effect with no admissible model → try association
        if sel.get("error") and intent.get("question_type") == "causal_effect" and not self.s.overrides.get("model"):
            self._emit("reframe_question", {},
                       preview="causal_effect → association",
                       why=(
                           "Your question used causal language ('impact', 'effect'), but the dataset "
                           "doesn't have the panel structure needed for causal inference "
                           "(e.g. no treated vs control groups across time). "
                           "I'll instead measure the statistical association — which tells us "
                           "whether the two variables move together, not whether one causes the other."
                       ))
            intent["question_type"] = "association"
            self.s.intent = intent
            sel = T.select_model(intent, self.s.df)

        if sel.get("error"):
            self._emit("select_model", {}, preview=sel["error"],
                       why="No admissible model found for this data and question type.",
                       status="error")
            self.s.followups = [
                "Check that your data file has a time column and a unit/entity column for causal questions.",
                "Try rephrasing as an association question: 'Is X related to Y?'",
                "Specify columns directly with --outcome and --treatment flags.",
            ]
            if self.verbose:
                render_followups(self.s.followups)
            return self.s
        self.s.model_key = sel["model_key"]
        self.s.model_display = sel["display_name"]
        self.s.model_alternatives = sel["alternatives"]
        self.s.model_rejected = sel.get("rejected", {})
        self._emit("select_model", {"override": self.s.overrides.get("model")},
                   preview=f"{sel['display_name']}" + (f" (alt: {', '.join(sel['alternatives'][:3])})" if sel["alternatives"] else ""),
                   why=self._explain_choice(self.s.model_key, intent))

        # 5) Diagnostics
        diag = T.run_diagnostics(self.s.model_key, self.s.df, intent)
        self.s.diagnostics = diag
        violations = diag.get("violations", []) if isinstance(diag, dict) else []
        self._emit("run_diagnostics", {"model": self.s.model_key},
                   preview=f"{len(diag.get('checks', []))} checks • {len(violations)} violation(s)",
                   why="Checking the assumptions this model relies on before trusting its number.")
        if self.verbose:
            render_diagnostics(diag, model_display=self.s.model_display)

        # 5b) Maybe switch model on critical violation
        alt = T.maybe_corrective_model(self.s.model_key, diag, self.s.model_alternatives + [self.s.model_key])
        if alt and alt != self.s.model_key and not self.s.overrides.get("model"):
            self._emit("switch_model", {"from": self.s.model_key, "to": alt},
                       preview=f"{self.s.model_key} → {alt}",
                       why=f"Critical diagnostic failed; switching to {alt} which is more robust to this violation.")
            self.s.model_key = alt
            self.s.model_display = T.MODEL_SPECS[alt]["display_name"]
            diag = T.run_diagnostics(alt, self.s.df, intent)
            self.s.diagnostics = diag
            self._emit("run_diagnostics", {"model": alt},
                       preview=f"{len(diag.get('checks', []))} checks • {len(diag.get('violations', []))} violation(s)",
                       why="Re-running diagnostics after the model switch.")
            if self.verbose:
                render_diagnostics(diag, model_display=self.s.model_display)

        # 6) Run model (with auto-retry on the next admissible alternative)
        forecast_periods = forecast_periods or intent.get("forecast_periods") or 10
        result = T.run_model(self.s.model_key, self.s.df, intent, forecast_periods=forecast_periods)
        tried = [self.s.model_key]
        while "error" in result and self.s.model_alternatives and not self.s.overrides.get("model"):
            next_model = next((m for m in self.s.model_alternatives if m not in tried), None)
            if not next_model:
                break
            self._emit("switch_model", {"from": self.s.model_key, "to": next_model},
                       preview=f"{self.s.model_key} → {next_model}",
                       why=f"{self.s.model_display} couldn't run here ({result.get('error', '')}). "
                           f"Trying {T.MODEL_SPECS[next_model]['display_name']} instead.")
            tried.append(next_model)
            self.s.model_key = next_model
            self.s.model_display = T.MODEL_SPECS[next_model]["display_name"]
            # Re-run diagnostics for the new model class
            diag = T.run_diagnostics(self.s.model_key, self.s.df, intent)
            self.s.diagnostics = diag
            result = T.run_model(self.s.model_key, self.s.df, intent, forecast_periods=forecast_periods)
        # Runtime causal→association fallback: if causal model failed and we haven't
        # reframed yet, try treating the question as an association.
        if "error" in result and intent.get("question_type") == "causal_effect" and not self.s.overrides.get("model"):
            self._emit("reframe_question", {},
                       preview="causal_effect → association (runtime fallback)",
                       why=(
                           f"{self.s.model_display} failed at runtime — likely the data lacks the "
                           "treated vs control structure needed for causal inference. "
                           "Measuring the statistical association instead."
                       ))
            intent["question_type"] = "association"
            self.s.intent = intent
            sel2 = T.select_model(intent, self.s.df)
            if not sel2.get("error"):
                self.s.model_key = sel2["model_key"]
                self.s.model_display = sel2["display_name"]
                self.s.model_alternatives = sel2["alternatives"]
                diag = T.run_diagnostics(self.s.model_key, self.s.df, intent)
                self.s.diagnostics = diag
                if self.verbose:
                    render_diagnostics(diag, model_display=self.s.model_display)
                result = T.run_model(self.s.model_key, self.s.df, intent, forecast_periods=forecast_periods)
                # retry alternatives if still failing
                for alt_m in sel2.get("alternatives", []):
                    if "error" not in result:
                        break
                    result = T.run_model(alt_m, self.s.df, intent, forecast_periods=forecast_periods)
                    if "error" not in result:
                        self.s.model_key = alt_m
                        self.s.model_display = T.MODEL_SPECS[alt_m]["display_name"]

        if "error" in result:
            self._emit("run_model", {"model": self.s.model_key}, preview=result.get("error", "failed"),
                       why="No admissible model could estimate this question with the available data.",
                       status="error")
            self.s.followups = [
                "Rephrase as an association question: 'Is X related to Y in this data?'",
                "Specify the exact outcome column with --outcome flag.",
                "Check that the data has sufficient variation in both variables.",
            ]
            if self.verbose:
                render_followups(self.s.followups)
            return self.s
        self.s.result = result
        self._emit("run_model", {"model": self.s.model_key},
                   preview=_result_preview(self.s.model_key, result),
                   why="Estimating the actual numbers.")

        # 7) Render numerical results
        if self.verbose:
            if self.s.model_key in T.FORECAST_RUNNERS:
                render_forecast(self.s.model_key, result, intent)
            else:
                # Animated 3-beat reveal before the full table
                n_obs = result.get("n_obs", 0) or len(self.s.df)
                _score_early = compute_confidence_score(result, self.s.diagnostics or {}, n_obs)
                render_animated_result(result, _score_early, intent)
                render_regression(self.s.model_key, result, intent,
                                  diagnostics=self.s.diagnostics,
                                  df=self.s.df)
                render_qq_plot(result)
            # Equation bar (full reveal)
            render_equation(self.s.model_key,
                            outcome=intent.get("outcome", ""),
                            treatment=intent.get("treatment", ""),
                            step=999)

        # 8) Interpretation blocks
        cols_summary = summary_for_llm(self.s.profile, max_cols=20)
        self._emit("interpret_columns", {},
                   preview="Why these columns",
                   why="Explaining why I picked these variables, in plain English.")
        with thinking("interpreting columns…"):
            why_cols = C.why_columns(
                question=question, outcome=intent.get("outcome"),
                treatment=intent.get("treatment"), unit=intent.get("unit"),
                time=intent.get("time"), columns_summary=cols_summary,
            )
        self._emit("interpret_model_choice", {},
                   preview="Why this model",
                   why="Explaining why this is the right tool for the job.")
        with thinking("explaining model choice…"):
            why_model = C.why_model(
                question=question, model_display=self.s.model_display,
                structure=self.s.profile.structure if self.s.profile else "",
                outcome=intent.get("outcome"), treatment=intent.get("treatment"),
                unit=intent.get("unit"), time=intent.get("time"),
            )

        # Statistical interpretation: always deterministic — LLM is unreliable on numbers.
        from interpretation import _fallback_regression_interpretation, _fallback_arima_interpretation, interpret_diagnostics
        from model_specs import MODEL_SPECS
        is_forecast = self.s.model_key in T.FORECAST_RUNNERS
        unit_clause = (f" for {intent.get('identified_unit')}" if intent.get("identified_unit") else "")
        if is_forecast:
            stat_interp = _fallback_arima_interpretation(
                intent.get("outcome", ""), result, unit_clause
            )
        else:
            eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
            se  = result.get("se", 0) or 0
            pval = result.get("pvalue", result.get("p_value", 1)) or 1
            ci_lo = _scalar_ci(result.get("ci_lower"), eff, se, -1.96)
            ci_hi = _scalar_ci(result.get("ci_upper"), eff, se, +1.96)
            r2   = result.get("r_squared", 0) or 0
            n    = result.get("n_obs", "?")
            causal = self.s.model_key == "diff_in_diff"
            stat_interp = _fallback_regression_interpretation(
                intent.get("outcome", ""), intent.get("treatment", ""),
                self.s.model_display, eff, pval, ci_lo, ci_hi, r2, n, causal, unit_clause
            )
        diag_text = ""  # diagnostics already rendered as a table above

        # Qualitative / context-aware
        self._emit("context_interpret", {},
                   preview="Domain · trends · news · literature · sanity check",
                   why="Tying the statistical estimate to real-world context.")
        time_range = _infer_time_range(self.s.df, intent.get("time"))
        hist_summary = _historical_summary(self.s.df, intent.get("outcome"), intent.get("time"))
        with thinking("adding context…"):
            ctx = C.context_interpret(
            question=question, outcome=intent.get("outcome"),
            treatment=intent.get("treatment"), unit=intent.get("identified_unit") or intent.get("unit"),
            time_range=time_range, model=self.s.model_display, result=result,
            historical_summary=hist_summary,
            df=self.s.df, profile=self.s.profile, time_col=intent.get("time"),
        )  # end with thinking

        # Domain engine — known laws + R² context
        try:
            from .domain_engine import infer_domain, identify_known_law, contextualize_r2
            domain = infer_domain(intent.get("outcome", ""), intent.get("treatment", ""))
            known_law = identify_known_law(intent.get("outcome", ""), intent.get("treatment", ""), domain)
            if known_law:
                self.s.known_law = (
                    f"[bold]{known_law['name']}[/bold]\n{known_law['description']}\n\n"
                    f"Benchmark: {known_law['benchmark']}"
                )
            r2 = result.get("r_squared", 0) or 0
            r2_context = contextualize_r2(r2, domain)
        except Exception:
            domain = None
            r2_context = ""
            known_law = None

        # Plain-English statistical translation
        if self.s.model_key not in T.FORECAST_RUNNERS:
            eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
            se = result.get("se", 0) or 0
            pval = result.get("pvalue", result.get("p_value", 1)) or 1
            ci_lo = _scalar_ci(result.get("ci_lower"), eff, se, -1.96)
            ci_hi = _scalar_ci(result.get("ci_upper"), eff, se, +1.96)
            r2 = result.get("r_squared", 0) or 0
            n = result.get("n_obs", 0)
            with thinking("translating to plain English…"):
                plain_eng = C.plain_english_stats(
                    estimate=eff, pvalue=pval, ci_lo=ci_lo, ci_hi=ci_hi,
                    r2=r2, n_obs=n,
                )
            if r2_context:
                plain_eng += f"\n- {r2_context}"
        else:
            plain_eng = ""

        self.s.interpretation_blocks = {
            "why_columns": why_cols,
            "why_model": why_model,
            "diagnostics_text": diag_text,
            "statistical": stat_interp,
            "plain_english": plain_eng,
            "domain": ctx.get("domain", ""),
            "past_trends": ctx.get("past_trends", ""),
            "literature": ctx.get("literature", ""),
            "sanity_check": ctx.get("sanity_check", ""),
        }

        # World context + era breakdown (time-series/panel data, range > 5 years)
        world_events = []
        era_effects = []
        # World context — runs whenever a domain is detected (no year-range gate)
        try:
            from .world_context import get_world_events
            if domain:
                with thinking("finding world context…"):
                    world_events = get_world_events(
                        self.s.df, domain,
                        intent.get("outcome", ""), intent.get("treatment", ""),
                        intent.get("time"),
                    )
                self.s.world_events = world_events
        except Exception:
            pass

        # Era breakdown — runs whenever there are world events and time data
        try:
            if world_events and self.s.model_key not in T.FORECAST_RUNNERS:
                from .era_breakdown import compute_era_effects
                era_effects = compute_era_effects(self.s, world_events)
                self.s.era_effects = era_effects
        except Exception:
            pass

        # Confidence score (with era stability)
        if self.s.model_key not in T.FORECAST_RUNNERS:
            try:
                n_obs = result.get("n_obs", 0) or len(self.s.df)
                score = compute_confidence_score(result, self.s.diagnostics or {}, n_obs, era_effects)
                self.s.confidence_score = score
            except Exception:
                score = {"score": 50, "label": "Moderate confidence",
                         "color": "#F39C12", "bullet": "🟡",
                         "sig": 10, "diag": 15, "samp": 15, "era": 10}
        else:
            score = None

        # Verdict
        if self.s.model_key not in T.FORECAST_RUNNERS and score:
            eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
            se = result.get("se", 0) or 0
            pval = result.get("pvalue", result.get("p_value", 1)) or 1
            ci_lo = _scalar_ci(result.get("ci_lower"), eff, se, -1.96)
            ci_hi = _scalar_ci(result.get("ci_upper"), eff, se, +1.96)
            with thinking("writing verdict…"):
                verdict_text = C.generate_verdict(
                    outcome=intent.get("outcome", "outcome"),
                    treatment=intent.get("treatment", "predictor"),
                    estimate=eff, pvalue=pval, ci_lo=ci_lo, ci_hi=ci_hi,
                    model=self.s.model_display,
                    is_causal=(self.s.model_key == "diff_in_diff"),
                )
            self.s.verdict_text = verdict_text
        else:
            verdict_text = ""
            score = score or {}

        # Web research context (LLM knowledge)
        web_ctx = ""
        if self.s.model_key not in T.FORECAST_RUNNERS:
            with thinking("researching context…"):
                web_ctx = C.web_research_context(
                    outcome=intent.get("outcome", ""),
                    treatment=intent.get("treatment", ""),
                    domain=domain or "",
                    time_range=_infer_time_range(self.s.df, intent.get("time")),
                    question=question,
                )

        # Deep analysis (narrative paragraphs)
        deep_text = ""
        if self.s.model_key not in T.FORECAST_RUNNERS:
            eff2  = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
            se2   = result.get("se", 0) or 0
            pval2 = result.get("pvalue", result.get("p_value", 1)) or 1
            ci_lo2 = _scalar_ci(result.get("ci_lower"), eff2, se2, -1.96)
            ci_hi2 = _scalar_ci(result.get("ci_upper"), eff2, se2, +1.96)
            r2_2  = result.get("r_squared", 0) or 0
            n2    = result.get("n_obs", 0) or 0
            with thinking("writing deep analysis…"):
                deep_text = C.deep_analysis(
                    question=question,
                    outcome=intent.get("outcome", ""),
                    treatment=intent.get("treatment", ""),
                    domain=domain or "economics",
                    model=self.s.model_display,
                    estimate=eff2, se=se2, pvalue=pval2,
                    ci_lo=ci_lo2, ci_hi=ci_hi2,
                    r2=r2_2, n_obs=n2,
                    time_range=_infer_time_range(self.s.df, intent.get("time")),
                    hist_summary=_historical_summary(self.s.df, intent.get("outcome"), intent.get("time")),
                    web_context=web_ctx,
                )

        # Proactive insights (pure pandas)
        proactive = C.compute_proactive_insights(
            self.s.df, result, intent,
            known_law=known_law if known_law else None,
        )

        if self.verbose:
            # Marginal effects chart (key visual — shows the finding, not just dots)
            if self.s.model_key not in T.FORECAST_RUNNERS:
                render_marginal_effects(result, intent, df=self.s.df)

            render_interpretation(
                self.s.interpretation_blocks,
                expertise=self.s.expertise,
                web_context=web_ctx,
                deep_text=deep_text,
            )
            if world_events:
                render_world_events(world_events, outcome_col=intent.get("outcome", ""))
            if era_effects:
                render_era_breakdown(era_effects)
            if proactive:
                render_proactive_insights(proactive)
            if verdict_text and score:
                sanity = (self.s.interpretation_blocks or {}).get("sanity_check", "")
                import re as _re
                first_caveat = next(
                    (_re.sub(r"^[\-\*•·]+\s*", "", l.strip()) for l in (sanity or "").splitlines()
                     if l.strip() and len(l.strip()) > 10), ""
                )[:120]
                render_verdict(verdict_text, score, caveat=first_caveat)

        # 8b) Multi-predictor comparison — run each extra treatment separately and compare
        extra_treatments = intent.get("_extra_treatments", [])
        if extra_treatments and self.s.model_key not in T.FORECAST_RUNNERS and self.verbose:
            comparison_rows = []
            primary_t = intent.get("treatment", "")
            primary_eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
            primary_p = result.get("pvalue", result.get("p_value", 1)) or 1
            primary_r2 = result.get("r_squared", 0) or 0
            comparison_rows.append((primary_t, primary_eff, primary_p, primary_r2))

            for extra_t in extra_treatments[:3]:
                if extra_t not in self.s.df.columns:
                    continue
                try:
                    extra_intent = dict(intent)
                    extra_intent["treatment"] = extra_t
                    extra_intent.pop("_extra_treatments", None)
                    extra_sel = T.select_model(extra_intent, self.s.df)
                    if not extra_sel.get("error"):
                        extra_result = T.run_model(extra_sel["model_key"], self.s.df, extra_intent)
                        if "error" not in extra_result:
                            e_eff = extra_result.get("treatment_effect", extra_result.get("slope", extra_result.get("effect", 0))) or 0
                            e_p = extra_result.get("pvalue", extra_result.get("p_value", 1)) or 1
                            e_r2 = extra_result.get("r_squared", 0) or 0
                            comparison_rows.append((extra_t, e_eff, e_p, e_r2))
                except Exception:
                    pass

            if len(comparison_rows) > 1:
                from rich.table import Table as _Table
                cmp_table = _Table(
                    title="[bold #D4A85A]Predictor Comparison[/bold #D4A85A]",
                    border_style="#6F4E37",
                    show_lines=False,
                )
                cmp_table.add_column("Predictor", style="bold")
                cmp_table.add_column("Effect", justify="right")
                cmp_table.add_column("p-value", justify="right")
                cmp_table.add_column("R²", justify="right")
                cmp_table.add_column("Stronger?", justify="center")
                best_r2 = max(r for _, _, _, r in comparison_rows)
                for tname, eff_v, pv, r2v in comparison_rows:
                    star = "★" if r2v >= best_r2 - 0.001 else ""
                    sig_col = "#6AB08A" if pv < 0.05 else ("#F39C12" if pv < 0.10 else "#95A5A6")
                    cmp_table.add_row(
                        tname,
                        f"[{sig_col}]{eff_v:+.4f}[/{sig_col}]",
                        f"[{sig_col}]{pv:.3f}[/{sig_col}]",
                        f"{r2v:.3f}",
                        f"[bold #D4A85A]{star}[/bold #D4A85A]",
                    )
                console.print(cmp_table)
                self._emit_thought(
                    f"Multi-predictor comparison: ran {len(comparison_rows)} predictors for {intent.get('outcome')}."
                )

        # 9) Follow-ups
        self._emit("suggest_followups", {},
                   preview="Suggesting next analyses",
                   why="Proposing logical next steps you can run with one click.")
        with thinking("suggesting follow-ups…"):
            self.s.followups = C.suggest_followups(
                question=question, outcome=intent.get("outcome"),
                treatment=intent.get("treatment"), model=self.s.model_display,
                result_summary=_result_preview(self.s.model_key, result),
            )
        if self.verbose:
            render_followups(self.s.followups)

        self.s.log_final("Analysis complete.")
        if self.verbose:
            console.print()
        return self.s

    # ------------------------------------------------------------------ helpers
    def _clarify(self, question: str, options: list[str], why: str) -> Optional[str]:
        self._emit("clarify", {"question": question, "options": options},
                   preview=f"asking: {question}", why=why)
        if self.clarifier is None:
            # No UI available — pick the first option silently.
            self._emit_thought(f"No clarifier configured; defaulting to '{options[0]}'.")
            return options[0] if options else None
        return self.clarifier(question, options)

    def _explain_choice(self, model_key: str, intent: dict) -> str:
        """One-line reason for the model selection, before LLM long-form text."""
        if model_key == "diff_in_diff":
            return "Question is causal, data is panel, treatment varies within units — diff-in-diff is the standard estimator."
        if model_key == "panel_ols":
            return "Question is association, data is panel — using two-way fixed effects to absorb unit and time confounders."
        if model_key in ("ols", "pooled_ols"):
            return "No panel structure detected — using cross-sectional OLS with robust SEs."
        if model_key == "arima":
            return "Forecast question on a time series — ARIMA picks (p,d,q) by AIC."
        if model_key in ("linear_trend", "exp_smoothing", "random_walk"):
            return f"Forecast question — {model_key.replace('_', ' ')} is a transparent baseline."
        return f"Selected based on data structure and question type."


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _pp(mapping_field) -> str:
    if isinstance(mapping_field, dict):
        v = mapping_field.get("value")
    else:
        v = mapping_field
    return v if v else ""


def _scalar_ci(v, eff: float = 0.0, se: float = 0.0, multiplier: float = 1.96) -> float:
    """Safely extract a scalar CI bound from a result value (handles ARIMA list returns)."""
    if v is None:
        return eff + multiplier * se
    if isinstance(v, (list, tuple)):
        v = v[0] if v else eff + multiplier * se
    try:
        return float(v)
    except (TypeError, ValueError):
        return eff + multiplier * se


def _result_preview(model_key: str, result: dict) -> str:
    if model_key in T.FORECAST_RUNNERS:
        fc = result.get("forecasts", [])
        if fc:
            return f"next={fc[0]:.4f} ({len(fc)} periods, RMSE={result.get('rmse', 0):.3f})"
        return "no forecast"
    eff = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
    p = result.get("pvalue", result.get("p_value", 1)) or 1
    return f"effect={eff:.4f}, p={p:.3f}, R²={result.get('r_squared', 0):.3f}"


def _infer_time_range(df: pd.DataFrame, time_col: Optional[str]) -> str:
    if not time_col or time_col not in df.columns:
        return ""
    try:
        s = pd.to_numeric(df[time_col], errors="coerce").dropna()
        if s.empty:
            return ""
        return f"{int(s.min())}–{int(s.max())}"
    except Exception:
        return ""


def _historical_summary(df: pd.DataFrame, outcome_col: Optional[str], time_col: Optional[str]) -> str:
    if not outcome_col or outcome_col not in df.columns:
        return ""
    try:
        y = pd.to_numeric(df[outcome_col], errors="coerce").dropna()
        if y.empty:
            return ""
        msg = f"mean={y.mean():.4g}, std={y.std():.4g}, min={y.min():.4g}, max={y.max():.4g}, n={len(y)}"
        if time_col and time_col in df.columns:
            tr = _infer_time_range(df, time_col)
            if tr:
                msg = f"{tr}: " + msg
        return msg
    except Exception:
        return ""
