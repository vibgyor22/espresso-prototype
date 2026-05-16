"""
Era breakdown — splits data at historical event years and re-runs the same
model on each sub-period, revealing whether the effect is stable or varies
across economic regimes.

Only runs when: panel or time-series data, time range > 10 years, N > 20.
"""

from __future__ import annotations

from typing import Optional, Any

import pandas as pd


def compute_era_effects(session, world_events: list) -> list:
    """
    Split the session's data at world event years and run the same model on each era.

    Returns list of dicts:
      [{"label": str, "period": str, "estimate": float, "pvalue": float, "n": int,
        "consistent": str}, ...]
    """
    try:
        from espresso.agent import tools as T

        df = session.df
        intent = session.intent or {}
        model_key = session.model_key
        time_col = intent.get("time")
        outcome = intent.get("outcome")

        if df is None or not time_col or not outcome or not model_key:
            return []
        if time_col not in df.columns:
            return []
        if model_key in T.FORECAST_RUNNERS:
            return []

        time_vals = pd.to_numeric(df[time_col], errors="coerce").dropna()
        if time_vals.empty:
            return []
        t_min, t_max = int(time_vals.min()), int(time_vals.max())
        if t_max - t_min < 10:
            return []

        # Build era boundaries from event years
        event_years = sorted(set(
            int(ev["year"]) for ev in world_events
            if t_min < int(ev["year"]) < t_max
        ))

        if not event_years:
            # Fallback: split at thirds
            span = t_max - t_min
            event_years = [t_min + span // 3, t_min + 2 * span // 3]

        boundaries = [t_min] + event_years + [t_max]
        eras = []
        for i in range(len(boundaries) - 1):
            lo, hi = boundaries[i], boundaries[i + 1]
            if hi - lo < 3:
                continue
            era_df = df[
                pd.to_numeric(df[time_col], errors="coerce").between(lo, hi)
            ].copy()
            if len(era_df) < 10:
                continue
            try:
                result = T.run_model(model_key, era_df, intent, forecast_periods=1)
                if "error" in result:
                    continue
                est = result.get("treatment_effect", result.get("slope", result.get("effect", 0))) or 0
                pval = result.get("pvalue", result.get("p_value", 1.0)) or 1.0
                n = result.get("n_obs", len(era_df))

                # Build a descriptive label from nearby world events
                nearby = [ev["event"] for ev in world_events
                          if lo <= int(ev["year"]) <= hi]
                if nearby:
                    label = nearby[0][:22]
                elif i == 0:
                    label = f"Early period"
                elif i == len(boundaries) - 2:
                    label = f"Recent period"
                else:
                    label = f"Mid period"

                eras.append({
                    "label": label,
                    "period": f"{lo}–{hi}",
                    "estimate": est,
                    "pvalue": pval,
                    "n": n,
                })
            except Exception:
                continue

        # Tag consistency vs main estimate
        if eras and session.result:
            main_est = session.result.get("treatment_effect",
                       session.result.get("slope",
                       session.result.get("effect", 0))) or 0
            main_sign = 1 if main_est >= 0 else -1
            for era in eras:
                era_sign = 1 if era["estimate"] >= 0 else -1
                if era_sign == main_sign:
                    era["consistent"] = "✓ consistent"
                else:
                    era["consistent"] = "✗ sign flip"

        return eras
    except Exception:
        return []
