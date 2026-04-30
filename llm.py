"""
LLM interface for Espresso (Gemini).

Responsibilities:
  - parse_question    : NL question → structured intent JSON
  - map_columns       : intent + column samples → column mapping
  - identify_unit_value : fuzzy-match a unit description to a data value
  - query_gemini      : generic text generation for interpretation
"""

import json
import google.genai as genai
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

try:
    client = genai.Client(api_key=api_key)
    print("[LLM] Gemini client initialized")
except Exception as e:
    print(f"[LLM] Warning: could not initialize Gemini client: {e}")
    client = None


# ---------------------------------------------------------------------------
# System prompts
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

"What was the effect of the 2008 crisis (starting 2008) on bank lending?"
{"question_type":"causal_effect","outcome":"bank_lending","treatment":"crisis","time":"year","unit":"country","unit_value":null,"forecast_periods":null,"pre_period":2007}

"How will GDP change in the most innovative country in Europe over 5 years?"
{"question_type":"forecast","outcome":"gdp","treatment":null,"time":"year","unit":"country","unit_value":"most innovative country in europe","forecast_periods":5,"pre_period":null}

Output JSON only:"""


# ---------------------------------------------------------------------------
# Shared retry helper
# ---------------------------------------------------------------------------

def _generate_with_retry(model, contents, config=None, max_retries=5):
    """Exponential backoff retry for transient Gemini errors (429, timeouts)."""
    if not client:
        raise RuntimeError("Gemini client not initialized")

    base_delay, max_delay = 2.0, 30.0

    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            msg = str(e).lower()
            is_transient = any(kw in msg for kw in [
                '429', 'rate', 'resource_exhausted', 'too many requests',
                'timeout', 'temporarily', 'unavailable'
            ])
            if attempt == max_retries or not is_transient:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            sleep_for = delay + random.uniform(0, 0.5)
            print(f"[LLM] Transient error (attempt {attempt}/{max_retries}). "
                  f"Retrying in {sleep_for:.1f}s…")
            time.sleep(sleep_for)


def _extract_json(text):
    """Extract the first {...} block from a string."""
    if '{' in text:
        start = text.index('{')
        end = text.rindex('}') + 1
        return text[start:end]
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_question(text):
    """
    Parse a natural-language research question into a structured intent dict.

    Returns a dict with keys: question_type, outcome, treatment, time, unit,
    unit_value, forecast_periods, pre_period — or None on failure.
    """
    if not client:
        print("[ERROR] Gemini client not initialized")
        return None
    try:
        print(f"[LLM] Parsing question: {text[:60]}…")
        resp = _generate_with_retry(
            model="gemini-2.5-flash",
            contents=f"{PARSE_PROMPT}\n\nQuestion: {text}\n\nJSON:",
            config={"temperature": 0.1, "top_p": 0.9, "top_k": 40}
        )
        raw = _extract_json(resp.text.strip())
        result = json.loads(raw)
        print(f"[LLM] Intent: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] parse_question failed: {e}")
        return None


def map_columns(intent, column_samples):
    """
    Map intent fields to actual dataset column names.

    `column_samples` : {column_name: [sample_value_str, ...]}

    Returns a mapping dict (see prompt schema below).
    """
    if not client:
        return {"outcome": None, "treatment": None, "time": None, "unit": None}
    try:
        print(f"[LLM] Mapping columns…")
        cols_text = "\n".join(
            f"- {col}: {', '.join(samples[:5])}"
            for col, samples in column_samples.items()
        )

        prompt = (
            "You are given a dataset's column names and sample values. "
            "Decide whether this dataset is 'indicator-style' (one row per series "
            "with year columns) or a regular tidy table. "
            "Return a single JSON object describing how to map the user's intent variables.\n\n"
            f"Columns and samples:\n{cols_text}\n\n"
            f"User intent: {json.dumps(intent)}\n\n"
            "CRITICAL: If the dataset has an indicator/series column with many values, "
            "map outcome/treatment to EXACT indicator values visible in the samples. "
            "DO NOT invent indicator names.\n\n"
            "RESPONSE FORMAT (JSON only):\n"
            "{\n"
            "  \"outcome\": {\"type\": \"column|indicator\", \"value\": \"...\"},\n"
            "  \"treatment\": {\"type\": \"column|indicator\", \"value\": \"...\"},\n"
            "  \"time\": {\"type\": \"column|years\", \"value\": \"<col>\" or [year_list]},\n"
            "  \"unit\": {\"type\": \"column\", \"value\": \"<col>\"},\n"
            "  \"pivot\": true|false,\n"
            "  \"indicator_column\": \"<col>\" or null,\n"
            "  \"year_columns\": [list] or null,\n"
            "  \"notes\": \"short explanation\"\n"
            "}\n\n"
            "Only output valid JSON matching the schema."
        )

        resp = _generate_with_retry(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"temperature": 0.1, "top_p": 0.9, "top_k": 40}
        )
        mapping = json.loads(_extract_json(resp.text.strip()))
        print(f"[LLM] Column mapping: {list(mapping.keys())}")
        return mapping
    except Exception as e:
        print(f"[ERROR] map_columns failed: {e}")
        return {"outcome": None, "treatment": None, "time": None, "unit": None}


def identify_unit_value(unit_description, unit_column_name, df):
    """
    Resolve a unit description (exact name or phrase) to a value in the data.

    e.g. "most innovative country in europe" → "Switzerland"
    """
    if not client or not unit_description or not unit_column_name:
        return None
    try:
        all_units = df[unit_column_name].dropna().unique().tolist()

        # Prioritise units that partially match the description
        low_desc = unit_description.lower()
        matches = [u for u in all_units if low_desc in str(u).lower()]
        sample = (matches[:50] + [u for u in all_units if u not in matches][:50])

        prompt = (
            f"You are given a list of {unit_column_name} values from a dataset.\n"
            f"Identify which specific value matches: \"{unit_description}\"\n\n"
            f"Available values:\n{', '.join(str(u) for u in sample)}\n\n"
            "Rules:\n"
            "- Return the EXACT value from the list that best matches.\n"
            "- Use your world knowledge for descriptive phrases "
            "(e.g. 'most happy country in europe' → 'Finland').\n"
            "- Return only the matched value — no explanation.\n"
            "- If no match is possible, return NOT_FOUND.\n\n"
            "Matched value:"
        )

        resp = _generate_with_retry(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"temperature": 0.1, "top_p": 0.9, "top_k": 40}
        )
        identified = resp.text.strip()
        print(f"[LLM] Identified unit: '{identified}'")

        if identified in all_units:
            return identified
        if identified == "NOT_FOUND":
            return None

        # Fuzzy fallback: case-insensitive + prefix stripping
        id_low = identified.lower()
        ignore = [
            "people's republic of", "republic of", "kingdom of",
            "special administrative region", "the ", "province of",
            "commonwealth of", "state of "
        ]
        def strip_prefix(s):
            for p in ignore:
                s = s.replace(p, '').strip(' ,')
            return s

        id_clean = strip_prefix(id_low)
        best, best_score = None, 0.0
        for u in all_units:
            u_clean = strip_prefix(str(u).lower())
            if not u_clean:
                continue
            if id_clean == u_clean:
                return u
            if (id_clean in u_clean or u_clean in id_clean) and len(id_clean) > 3:
                if 'special administrative region' not in str(u).lower():
                    score = 1.0 / (1 + 0.1 * len(str(u).split()))
                    if score > best_score:
                        best_score = score
                        best = u
        if best:
            print(f"[LLM] Fuzzy matched '{identified}' → '{best}'")
            return best
        return None

    except Exception as e:
        print(f"[ERROR] identify_unit_value failed: {e}")
        return None


def query_gemini(prompt):
    """
    Generic Gemini call for interpretation / explanation text.

    Uses gemini-2.5-pro for higher quality prose.
    """
    try:
        resp = _generate_with_retry(
            model="gemini-2.5-pro",
            contents=prompt,
            config={"temperature": 0.7, "top_p": 0.95, "top_k": 40},
            max_retries=1
        )
        return resp.text.strip() if resp and resp.text else ""
    except Exception as e:
        msg = str(e).lower()
        if "quota" in msg or "429" in msg or "resource_exhausted" in msg:
            print("[LLM] Interpretation quota reached; using local statistical summary.")
        else:
            print(f"[LLM] Interpretation unavailable; using local statistical summary ({type(e).__name__}).")
        return ""
