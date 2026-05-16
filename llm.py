"""
LLM interface for Espresso.

Backends (auto-selected):
  - Anthropic Claude (preferred when ANTHROPIC_API_KEY is set)
        Models default to claude-haiku-4-5-20251001 (cheap, fast).
        Override via ESPRESSO_CLAUDE_MODEL.
  - Google Gemini (fallback when only GEMINI_API_KEY is set)

Public API stays stable — `parse_question`, `map_columns`,
`identify_unit_value`, `query_gemini` (kept for back-compat; routes to the
active backend). When no backend is available the functions return safe
defaults and the rest of the pipeline degrades gracefully to its local prose.
"""

from __future__ import annotations

import json
import os
import random
import time

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
_GEMINI_KEY = os.getenv("GEMINI_API_KEY")

CLAUDE_MODEL = os.getenv("ESPRESSO_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GEMINI_MODEL_FAST = "gemini-2.5-flash"
GEMINI_MODEL_QUALITY = "gemini-2.5-pro"

_anthropic_client = None
_gemini_client = None
BACKEND: str = "none"

_VERBOSE_LLM = os.getenv("ESPRESSO_LLM_VERBOSE", "0") not in ("", "0", "false", "False")


def _llog(msg: str) -> None:
    """Internal LLM debug log — silent by default; set ESPRESSO_LLM_VERBOSE=1 to enable."""
    if _VERBOSE_LLM:
        print(msg)


if _ANTHROPIC_KEY:
    try:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
        BACKEND = "anthropic"
        _llog(f"[LLM] Anthropic backend ready · model={CLAUDE_MODEL}")
    except Exception as e:  # pragma: no cover
        _llog(f"[LLM] Could not initialize Anthropic client: {e}")

if BACKEND == "none" and _GEMINI_KEY:
    try:
        import google.genai as genai
        _gemini_client = genai.Client(api_key=_GEMINI_KEY)
        BACKEND = "gemini"
        _llog(f"[LLM] Gemini backend ready · model={GEMINI_MODEL_FAST}/{GEMINI_MODEL_QUALITY}")
    except Exception as e:  # pragma: no cover
        _llog(f"[LLM] Could not initialize Gemini client: {e}")

if BACKEND == "none":
    _llog("[LLM] No API key found (set ANTHROPIC_API_KEY or GEMINI_API_KEY).")


# ---------------------------------------------------------------------------
# Prompts (system text moved to module-level so Claude can prompt-cache them)
# ---------------------------------------------------------------------------

PARSE_PROMPT = """You are a JSON extractor. Extract analytical intent from research questions.
Output ONLY valid JSON — no prose, no markdown fences.

Fields to extract:
  question_type  : "causal_effect" | "forecast" | "association"
  outcome        : the dependent variable (string or null)
  treatment      : the independent/treatment variable (string or null)
  time           : the time dimension label (string or null)
  unit           : type of entity (e.g. "country", "firm", "state") or null
  unit_value     : specific entity name OR descriptive phrase (e.g. "India", "most populous country") or null
  forecast_periods : integer number of periods to forecast, or null
  pre_period     : cutoff year/period before which is "pre-treatment" (integer or null)

Guidelines:
  - "causal_effect" → effect of X on Y (use words: effect, impact, cause, affect)
  - "association"   → relationship/correlation between X and Y (no causal language)
  - "forecast"      → prediction of future values (use words: forecast, predict, project)
  - forecast_periods: default 10 if not specified for forecast questions
  - pre_period: extract ONLY if the question mentions a specific year/cutoff (e.g. "policy implemented in 2010")
  - unit_value: extract EVEN IF it is a descriptive phrase; the system will resolve it to an actual entity

Examples:

"What is the effect of minimum wage on employment?"
{"question_type":"causal_effect","outcome":"employment","treatment":"minimum_wage","time":"year","unit":"state","unit_value":null,"forecast_periods":null,"pre_period":null}

"What is the relationship between inflation and GDP growth?"
{"question_type":"association","outcome":"gdp_growth","treatment":"inflation","time":"year","unit":"country","unit_value":null,"forecast_periods":null,"pre_period":null}

"Forecast unemployment in India for the next 10 years"
{"question_type":"forecast","outcome":"unemployment","treatment":null,"time":"year","unit":"country","unit_value":"India","forecast_periods":10,"pre_period":null}

Output JSON only.
"""


# ---------------------------------------------------------------------------
# Backend dispatch
# ---------------------------------------------------------------------------

def _is_transient(msg: str) -> bool:
    msg = msg.lower()
    return any(kw in msg for kw in (
        "429", "rate", "resource_exhausted", "too many requests",
        "timeout", "temporarily", "unavailable", "overloaded",
    ))


def _chat(*, system: str, user: str, temperature: float = 0.2,
          max_tokens: int = 1024, model: str | None = None,
          cache_system: bool = True, max_retries: int = 4) -> str:
    """
    Single chat completion. Returns the assistant text, or "" on failure.

    `cache_system=True` enables Anthropic prompt caching on the system block,
    which pays off because we send the same system text for many short user
    prompts within a single CLI session.
    """
    if BACKEND == "anthropic":
        return _call_anthropic(system=system, user=user, temperature=temperature,
                               max_tokens=max_tokens, model=model or CLAUDE_MODEL,
                               cache_system=cache_system, max_retries=max_retries)
    if BACKEND == "gemini":
        return _call_gemini(system=system, user=user, temperature=temperature,
                            model=model or GEMINI_MODEL_FAST, max_retries=max_retries)
    return ""


def _call_anthropic(*, system: str, user: str, temperature: float, max_tokens: int,
                    model: str, cache_system: bool, max_retries: int) -> str:
    base, cap = 1.5, 20.0
    sys_blocks = (
        [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        if cache_system and system else
        system
    )
    for attempt in range(1, max_retries + 1):
        try:
            resp = _anthropic_client.messages.create(
                model=model,
                system=sys_blocks,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": user}],
            )
            parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
            return "".join(parts).strip()
        except Exception as e:
            err = str(e)
            if attempt == max_retries or not _is_transient(err):
                _llog(f"[LLM] Anthropic error: {err.splitlines()[0]}")
                return ""
            delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.4)
            _llog(f"[LLM] Transient Anthropic error, retry {attempt}/{max_retries} in {delay:.1f}s")
            time.sleep(delay)
    return ""


def _call_gemini(*, system: str, user: str, temperature: float,
                 model: str, max_retries: int) -> str:
    base, cap = 1.5, 20.0
    contents = f"{system}\n\n{user}" if system else user
    for attempt in range(1, max_retries + 1):
        try:
            resp = _gemini_client.models.generate_content(
                model=model, contents=contents,
                config={"temperature": temperature, "top_p": 0.95, "top_k": 40},
            )
            return (resp.text or "").strip()
        except Exception as e:
            err = str(e)
            if attempt == max_retries or not _is_transient(err):
                msg = err.lower()
                if "quota" in msg or "resource_exhausted" in msg:
                    _llog("[LLM] Gemini quota reached.")
                else:
                    _llog(f"[LLM] Gemini error: {err.splitlines()[0]}")
                return ""
            delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.4)
            _llog(f"[LLM] Transient Gemini error, retry {attempt}/{max_retries} in {delay:.1f}s")
            time.sleep(delay)
    return ""


def _extract_json(text: str) -> str:
    if not text:
        return text
    if "```" in text:
        text = text.replace("```json", "```").split("```")[1] if "```" in text else text
    if "{" in text:
        return text[text.index("{"): text.rindex("}") + 1]
    return text


# ---------------------------------------------------------------------------
# Public API — same surface as before
# ---------------------------------------------------------------------------

def parse_question(text: str):
    """NL question → structured intent dict, or None."""
    if BACKEND == "none":
        return None
    try:
        _llog(f"[LLM] Parsing question: {text[:60]}…")
        out = _chat(
            system=PARSE_PROMPT,
            user=f"Question: {text}\n\nJSON:",
            temperature=0.1, max_tokens=400,
        )
        result = json.loads(_extract_json(out))
        _llog(f"[LLM] Intent: {result}")
        return result
    except Exception as e:
        _llog(f"[LLM] parse_question failed: {e}")
        return None


def map_columns(intent: dict, column_samples: dict):
    """Map intent fields to actual dataset column names."""
    if BACKEND == "none":
        return {"outcome": None, "treatment": None, "time": None, "unit": None}
    try:
        _llog("[LLM] Mapping columns…")
        cols_text = "\n".join(
            f"- {col}: {', '.join(samples[:5])}"
            for col, samples in column_samples.items()
        )
        system = (
            "You map a parsed user intent to actual dataset columns. "
            "If the dataset is indicator-style (one row per series with year columns), "
            "set pivot=true and map outcome/treatment to EXACT indicator values from the samples. "
            "Otherwise map to direct column names. Output JSON only — no prose, no fences."
        )
        user = (
            f"Columns and samples:\n{cols_text}\n\n"
            f"User intent: {json.dumps(intent)}\n\n"
            "Response schema:\n"
            '{ "outcome": {"type": "column|indicator", "value": "..."},\n'
            '  "treatment": {"type": "column|indicator", "value": "..."},\n'
            '  "time": {"type": "column|years", "value": "<col>" or [year_list]},\n'
            '  "unit": {"type": "column", "value": "<col>"},\n'
            '  "pivot": true|false,\n'
            '  "indicator_column": "<col>" or null,\n'
            '  "year_columns": [list] or null,\n'
            '  "notes": "short explanation" }'
        )
        out = _chat(system=system, user=user, temperature=0.1, max_tokens=600)
        mapping = json.loads(_extract_json(out))
        _llog(f"[LLM] Column mapping: {list(mapping.keys())}")
        return mapping
    except Exception as e:
        _llog(f"[LLM] map_columns failed: {e}")
        return {"outcome": None, "treatment": None, "time": None, "unit": None}


def identify_unit_value(unit_description: str, unit_column_name: str, df):
    """Resolve a unit description (exact name or phrase) to an actual data value."""
    if BACKEND == "none" or not unit_description or not unit_column_name:
        return None
    try:
        all_units = df[unit_column_name].dropna().unique().tolist()
        low_desc = unit_description.lower()
        matches = [u for u in all_units if low_desc in str(u).lower()]
        sample = (matches[:50] + [u for u in all_units if u not in matches][:50])

        system = (
            "Given a list of dataset values and a description, return the EXACT value from "
            "the list that best matches. Use world knowledge for descriptive phrases "
            "(e.g. 'most happy country in europe' → 'Finland'). "
            "If nothing reasonably matches, return NOT_FOUND. Output only the matched value."
        )
        user = (
            f"Column: {unit_column_name}\n"
            f"Description: \"{unit_description}\"\n"
            f"Available values: {', '.join(str(u) for u in sample)}\n\n"
            "Matched value:"
        )
        identified = _chat(system=system, user=user, temperature=0.1, max_tokens=80).strip()
        _llog(f"[LLM] Identified unit: '{identified}'")
        if not identified or identified == "NOT_FOUND":
            return None
        if identified in all_units:
            return identified
        # Fuzzy fallback (preserved from old code)
        ignore = [
            "people's republic of", "republic of", "kingdom of",
            "special administrative region", "the ", "province of",
            "commonwealth of", "state of ",
        ]
        def strip_prefix(s):
            for p in ignore:
                s = s.replace(p, "").strip(" ,")
            return s
        id_low = strip_prefix(identified.lower())
        best, best_score = None, 0.0
        for u in all_units:
            u_clean = strip_prefix(str(u).lower())
            if not u_clean:
                continue
            if id_low == u_clean:
                return u
            if (id_low in u_clean or u_clean in id_low) and len(id_low) > 3:
                score = 1.0 / (1 + 0.1 * len(str(u).split()))
                if score > best_score:
                    best_score, best = score, u
        return best
    except Exception as e:
        _llog(f"[LLM] identify_unit_value failed: {e}")
        return None


def query_gemini(prompt: str) -> str:
    """
    Generic prose generation. Name kept for back-compat; routes to whichever
    backend is active. Used by interpretation, context, why-columns, etc.
    """
    if BACKEND == "none":
        return ""
    return _chat(
        system="You are an econometrician explaining results to a non-expert. "
               "Be precise, clear, and honest about uncertainty. Never fabricate citations.",
        user=prompt,
        temperature=0.5,
        max_tokens=900,
        model=GEMINI_MODEL_QUALITY if BACKEND == "gemini" else None,
    )
