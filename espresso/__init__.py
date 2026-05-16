"""
Espresso — agentic econometric analyst.

Public API. The deterministic statistical core (models, diagnostics, selector,
model_specs, data_utils) lives at the top level of the repo and is re-exported
here so the package presents a single, stable import surface.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Re-export the deterministic statistical core (untouched).
import data_utils  # noqa: F401
import diagnostics  # noqa: F401
import interpretation  # noqa: F401
import llm  # noqa: F401
import model_specs  # noqa: F401
import models  # noqa: F401
import selector  # noqa: F401

from .ingest import load as load_data
from .profiling import profile
from .agent.session import Session
from .agent.coordinator import Coordinator
from .whatif import simulate as whatif_simulate
from .glossary import GLOSSARY, define

__all__ = [
    "__version__",
    "load_data",
    "profile",
    "Session",
    "Coordinator",
    "whatif_simulate",
    "GLOSSARY",
    "define",
]
