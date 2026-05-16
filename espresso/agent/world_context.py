"""
World context engine — identifies real-world events that intersect the dataset's time range
and annotates them with actual data-driven observations.

LLM (Sonnet) is used when available; KNOWN_EVENTS fallback covers most common domains.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Curated event dictionary (domain → list of (year, event, effect))
# ---------------------------------------------------------------------------

KNOWN_EVENTS: dict[str, list[tuple]] = {
    "macroeconomics": [
        (1997, "Asian Financial Crisis",       "currency crises, contagion across emerging markets"),
        (2000, "Dot-com bust",                 "tech sector collapse, mild recession in developed economies"),
        (2007, "Global housing bubble peak",   "mortgage credit boom peak, precursor to GFC"),
        (2008, "Global Financial Crisis",      "credit supply collapse, GDP contraction, unemployment surge"),
        (2009, "Great Recession trough",       "deepest post-war global contraction, G20 stimulus response"),
        (2010, "European sovereign debt crisis began", "peripheral euro-zone spreads, austerity measures"),
        (2012, "Euro crisis peak",             "Spain/Italy borrowing costs surged, ECB 'whatever it takes'"),
        (2015, "China growth slowdown",        "commodity prices fell, EM currencies depreciated"),
        (2020, "COVID-19 pandemic",            "historic demand shock, global GDP fell ~3.5%, fiscal expansion"),
        (2021, "Post-COVID rebound",           "fastest GDP recovery since WWII, supply-chain inflation"),
        (2022, "Post-COVID inflation surge",   "CPI hit multi-decade highs, central banks hiked aggressively"),
    ],
    "labor economics": [
        (1980, "Volcker disinflation",         "Fed rate hikes to 20%, unemployment rose to ~10%"),
        (2000, "Tech boom labor market peak",  "lowest US unemployment in decades"),
        (2008, "Great Recession job losses",   "largest peacetime unemployment spike, ~8.5M US jobs lost"),
        (2010, "Jobless recovery",             "GDP recovered but hiring lagged, 'scars' in long-term unemployment"),
        (2015, "US full employment approached","unemployment fell below 5% for first time post-GFC"),
        (2020, "COVID labor shock",            "22M US jobs lost in March-April 2020, sectoral displacement"),
        (2021, "Great Resignation",            "record quit rates, wage acceleration, labor supply tightened"),
        (2022, "Labor market tightening",      "wage growth at 40-year high, vacancy-to-unemployment ratio record"),
    ],
    "finance": [
        (1997, "Asian currency crisis",        "baht devaluation, contagion, IMF bailouts"),
        (1998, "LTCM collapse / Russia default","liquidity freeze, Fed emergency rate cut"),
        (2000, "Dot-com crash",                "NASDAQ -78% peak-to-trough over 2 years"),
        (2007, "Sub-prime crisis began",       "structured credit unraveled, Bear Stearns hedge funds failed"),
        (2008, "Lehman collapse",              "global credit freeze, equities -50%, VIX hit 80"),
        (2020, "COVID market crash",           "fastest bear market in history, then fastest V-recovery"),
        (2022, "Fed hiking cycle",             "fastest rate increases since 1980, bonds -15%, equities -20%"),
    ],
    "climate / environment": [
        (1997, "Kyoto Protocol adopted",       "first binding GHG reduction commitments by industrialized nations"),
        (2005, "EU ETS launched",              "world's first major carbon trading scheme"),
        (2009, "Copenhagen Climate Conference","failed to reach binding global agreement"),
        (2011, "Fukushima nuclear disaster",   "Japan and Germany reversed nuclear policy, fossil demand rose"),
        (2015, "Paris Agreement",              "195-nation commitment to limit warming to 1.5-2°C"),
        (2021, "COP26 Glasgow",                "methane pledge, coal phase-down, enhanced NDC commitments"),
        (2022, "EU energy crisis",             "gas prices x10, accelerated renewables but short-term coal rebound"),
    ],
    "international trade": [
        (1995, "WTO established",              "replaced GATT, rules-based global trade system"),
        (2001, "China WTO accession",          "massive export surge, 'China shock' to manufacturing jobs"),
        (2008, "Trade finance freeze",         "global trade fell 12% — fastest contraction in 70 years"),
        (2016, "Brexit vote",                  "UK-EU trade uncertainty, sterling -15%"),
        (2018, "US-China trade war began",     "tariffs on $360B goods, supply chain rerouting"),
        (2020, "COVID trade shock",            "goods trade -6%, services -20%, supply chains fractured"),
        (2022, "Russia-Ukraine war",           "commodity prices spiked, energy and food trade rerouted"),
    ],
    "housing": [
        (2000, "Housing boom began",           "low rates and relaxed lending standards fueled price surge"),
        (2006, "US housing peak",              "prices peaked, then fell 30% peak-to-trough"),
        (2008, "Foreclosure crisis",           "millions of US homeowners underwater, banks insolvent"),
        (2012, "Housing recovery began",       "prices bottomed, institutional investors entered"),
        (2020, "COVID housing boom",           "low rates + remote work drove prices +20% in 2 years"),
        (2022, "Housing correction",           "rates rose, affordability collapsed, prices fell in many markets"),
    ],
    "inequality": [
        (2000, "Tech boom inequality",         "top-end wages surged, lower-skill wages stagnated"),
        (2008, "GFC wealth destruction",       "household net worth fell -$13T, bottom quintile hit hardest"),
        (2020, "COVID K-shaped recovery",      "high-skill workers recovered fast; service workers did not"),
        (2021, "Stimulus wealth effects",      "asset price inflation boosted top decile disproportionately"),
    ],
    "education": [
        (2008, "GFC enrollment surge",         "university enrollment rose as labor market weakened"),
        (2020, "COVID school closures",        "1.6B students affected, learning loss estimated"),
        (2021, "Post-COVID enrollment drop",   "community college enrollment fell sharply"),
    ],
    "public health": [
        (2003, "SARS outbreak",                "first major 21st-century pandemic scare, Asia focus"),
        (2008, "GFC health spending cuts",     "austerity reduced public health capacity"),
        (2009, "H1N1 flu pandemic",            "first WHO pandemic declaration since 1968"),
        (2014, "West Africa Ebola outbreak",   "regional epidemic, tested global health preparedness"),
        (2020, "COVID-19 pandemic",            "millions of excess deaths, healthcare system strain globally"),
    ],
}

# Domain aliases (map detected domain to the key in KNOWN_EVENTS)
_DOMAIN_ALIAS = {
    "labor economics": "labor economics",
    "macroeconomics": "macroeconomics",
    "finance": "finance",
    "climate / environment": "climate / environment",
    "international trade": "international trade",
    "housing": "housing",
    "inequality": "inequality",
    "education": "education",
    "public health": "public health",
}


# ---------------------------------------------------------------------------
# LLM prompt (used when Anthropic key available + Sonnet)
# ---------------------------------------------------------------------------

WORLD_EVENTS_PROMPT = """You are an economic historian with deep knowledge of global events.

Given this analysis context:
- Domain: {domain}
- Outcome variable: {outcome}
- Predictor variable: {treatment}
- Time period covered by data: {time_start} to {time_end}
- Frequency: {frequency}

List up to 5 major real-world events or regime changes during this period that economists
know materially affected this domain. Be specific: name the event, give the year, and state
in one phrase how it affected the outcome or predictor.

STRICT RULES:
- Only include events you are HIGHLY CONFIDENT occurred in the relevant domain and time period
- Do NOT invent events or approximate causality
- Only include events within the time range {time_start} to {time_end}
- If fewer than 3 confident events exist, return only those
- Never fabricate citations or statistics

Return ONLY valid JSON, no prose:
[{{"year": 2008, "event": "Global Financial Crisis", "effect": "credit collapse, unemployment surge"}}]
"""


def _llm_world_events(domain: str, outcome: str, treatment: str,
                       time_start: int, time_end: int, frequency: str) -> Optional[list]:
    """Call LLM (Sonnet preferred) for world events. Returns list or None."""
    try:
        from llm import query_gemini
        prompt = WORLD_EVENTS_PROMPT.format(
            domain=domain, outcome=outcome, treatment=treatment,
            time_start=time_start, time_end=time_end, frequency=frequency,
        )
        raw = query_gemini(prompt, system="You are an economic historian. Return only valid JSON arrays.")
        if not raw:
            return None
        # Find JSON array in response
        import re
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict) and "year" in e and "event" in e]
        return None
    except Exception:
        return None


def _fallback_world_events(domain: str, time_start: int, time_end: int) -> list:
    """Use KNOWN_EVENTS dict filtered to the time range."""
    alias = _DOMAIN_ALIAS.get(domain, domain)
    events = KNOWN_EVENTS.get(alias, [])
    return [
        {"year": year, "event": event, "effect": effect}
        for year, event, effect in events
        if time_start <= year <= time_end
    ]


def _annotate_events_with_data(events: list, df: pd.DataFrame,
                                outcome_col: Optional[str],
                                time_col: Optional[str]) -> list:
    """Add data_note to each event: what the actual data shows around that year."""
    if not outcome_col or not time_col:
        return events
    if outcome_col not in df.columns or time_col not in df.columns:
        return events

    annotated = []
    try:
        sub = df[[time_col, outcome_col]].copy()
        sub[time_col] = pd.to_numeric(sub[time_col], errors="coerce")
        sub[outcome_col] = pd.to_numeric(sub[outcome_col], errors="coerce")
        sub = sub.dropna()

        overall_mean = sub[outcome_col].mean()
        overall_std = sub[outcome_col].std() or 1.0

        for ev in events:
            year = ev.get("year")
            if year is None:
                annotated.append(ev)
                continue
            # Look at the event year and 1-2 years after
            window = sub[sub[time_col].between(year, year + 2)]
            if window.empty:
                annotated.append(ev)
                continue
            val = window[outcome_col].mean()
            z = (val - overall_mean) / overall_std
            direction = "above" if val > overall_mean else "below"
            pct_dev = abs(val - overall_mean) / (abs(overall_mean) + 0.001) * 100
            note = (
                f"{outcome_col} averaged {val:.3g} "
                f"({pct_dev:.0f}% {direction} sample mean) "
                f"in {year}–{year+2}"
            )
            annotated.append({**ev, "data_note": note})
    except Exception:
        return events
    return annotated


def get_world_events(df: pd.DataFrame, domain: str, outcome: str, treatment: str,
                     time_col: Optional[str]) -> list:
    """
    Main entry point. Returns a list of dicts:
      [{"year": int, "event": str, "effect": str, "data_note": str}, ...]
    """
    # Infer time range
    time_start, time_end = 1900, 2100
    if time_col and time_col in df.columns:
        try:
            t = pd.to_numeric(df[time_col], errors="coerce").dropna()
            if not t.empty:
                time_start = int(t.min())
                time_end = int(t.max())
        except Exception:
            pass

    if time_end - time_start < 3:
        return []

    # Infer frequency
    frequency = "annual" if time_end - time_start <= len(df) * 2 else "sub-annual"

    # Try LLM first, fall back to dict
    events = _llm_world_events(domain, outcome, treatment, time_start, time_end, frequency)
    if not events:
        events = _fallback_world_events(domain, time_start, time_end)

    # Add data annotations
    events = _annotate_events_with_data(events, df, outcome, time_col)
    return events
