"""
In-memory session state for the agent.

Holds the dataframe, profile, parsed intent, column mapping, model selection,
diagnostics, results, and the full chronological log of agent actions. Used
both by the coordinator (state machine) and by the export step (to render the
HTML dashboard with everything the user has seen).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import pandas as pd


@dataclass
class AgentStep:
    """A single planner-executor step the user sees in the terminal."""

    kind: str                      # "thought" | "tool_call" | "tool_result" | "clarify" | "final"
    tool: Optional[str] = None
    args: dict = field(default_factory=dict)
    result_preview: str = ""       # one-line human summary
    justification: str = ""        # *why* the agent took this step
    status: str = "ok"             # "ok" | "error" | "skipped"
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """Everything the agent knows about the current analysis."""

    df: Optional[pd.DataFrame] = None
    source_path: str = ""
    source_format: str = ""
    sheet: Optional[str] = None

    profile: Any = None             # espresso.profiling.DataProfile
    question: str = ""
    intent: dict = field(default_factory=dict)
    mapping: dict = field(default_factory=dict)

    model_key: str = ""
    model_display: str = ""
    model_alternatives: list = field(default_factory=list)
    model_rejected: dict = field(default_factory=dict)

    diagnostics: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)

    interpretation_blocks: dict = field(default_factory=dict)
    followups: list = field(default_factory=list)
    history: list = field(default_factory=list)         # list[AgentStep]

    # Overrides from the user (expert path). The agent treats anything pinned
    # here as a hard constraint rather than something to decide for itself.
    overrides: dict = field(default_factory=dict)
    expertise: str = "beginner"     # "beginner" | "intermediate" | "expert"

    # V3 additions
    world_events: list = field(default_factory=list)
    era_effects: list = field(default_factory=list)
    confidence_score: Optional[dict] = None
    verdict_text: str = ""
    known_law: Optional[str] = None
    robustness_table: Optional[list] = None

    started_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------ logging
    def log(self, step: AgentStep) -> AgentStep:
        self.history.append(step)
        return step

    def log_tool(self, tool: str, args: dict, preview: str, why: str, status: str = "ok") -> AgentStep:
        return self.log(AgentStep(
            kind="tool_call", tool=tool, args=args,
            result_preview=preview, justification=why, status=status,
        ))

    def log_thought(self, text: str) -> AgentStep:
        return self.log(AgentStep(kind="thought", result_preview=text))

    def log_final(self, text: str) -> AgentStep:
        return self.log(AgentStep(kind="final", result_preview=text))

    # ------------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        """JSON-serializable snapshot (df + profile dropped or sampled)."""
        d = {
            "source_path": self.source_path,
            "source_format": self.source_format,
            "sheet": self.sheet,
            "question": self.question,
            "intent": self.intent,
            "mapping": self.mapping,
            "model_key": self.model_key,
            "model_display": self.model_display,
            "model_alternatives": self.model_alternatives,
            "model_rejected": self.model_rejected,
            "diagnostics": _jsonable(self.diagnostics),
            "result": _jsonable(self.result),
            "interpretation_blocks": self.interpretation_blocks,
            "followups": self.followups,
            "overrides": self.overrides,
            "expertise": self.expertise,
            "history": [asdict(s) for s in self.history],
            "started_at": self.started_at,
        }
        if self.profile is not None and hasattr(self.profile, "to_dict"):
            d["profile"] = self.profile.to_dict()
        if self.df is not None:
            d["data_sample"] = self.df.head(50).to_dict(orient="records")
            d["n_rows"] = int(len(self.df))
        return d

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, default=str, indent=2)
        return path


def _jsonable(x: Any) -> Any:
    """Coerce ndarray / scalar / dict to JSON-serializable form."""
    try:
        import numpy as np
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, (np.floating, np.integer)):
            return x.item()
    except Exception:
        pass
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x
