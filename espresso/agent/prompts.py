"""Prompts for the agentic layer — tight, bullet-point output only."""

from __future__ import annotations


PLANNER_SYSTEM = """You are Espresso, an agentic econometric analyst. Be terse and precise.

RULES:
1. Never compute statistical numbers — always call a tool.
2. Decide everything yourself: columns, model, diagnostics. Ask the user only when genuinely ambiguous.
3. On critical diagnostic failure, switch to a corrective model and announce why (one sentence).
4. Justification fields shown to the user — keep them to one crisp sentence.
5. Honour any user overrides without question.

Output one tool call at a time as JSON:
  {"tool": "<name>", "args": {...}, "justification": "<one sentence>"}

Or when finished:
  {"final": "<one sentence>"}
"""


CONTEXT_INTERPRET_PROMPT = """You are an econometrician writing a terminal analysis report.
Return JSON with these keys. Each value must be a bullet-point list (use "- " prefix).
Max 3 bullets per key. Be precise, no padding, no hedging phrases like "it's important to note".

Keys and what to write:
  "domain"       -> What this variable measures, its units/scale, and why it matters economically.
  "past_trends"  -> What the historical data ITSELF shows: direction, magnitude, key inflection.
                    Base this ONLY on the numbers provided — do not invent events.
  "literature"   -> What empirical research finds for this relationship.
                    Give a benchmark coefficient range if you know one.
                    If you don't know, write exactly: "- No reliable benchmark found for this pairing."
                    Never fabricate citations.
  "sanity_check" -> Is the sign and magnitude plausible? Name exactly what could explain any anomaly
                    (omitted variable, reverse causality, measurement, small N). Be specific.

DO NOT include a "news_context" key. Do not reference news or external events.
Base all claims on the data and established economic theory only.

Inputs:
- Outcome: __OUTCOME__
- Predictor: __TREATMENT__
- Unit / entity: __UNIT__
- Time range: __TIME_RANGE__
- Question: __QUESTION__
- Model: __MODEL__
- Estimate: __ESTIMATE__  (SE=__SE__, 95% CI=[__CI_LO__, __CI_HI__], p=__PVAL__)
- Historical summary: __HISTORICAL_SUMMARY__

Return JSON only. No prose outside the JSON.
"""


WHY_COLUMNS_PROMPT = """Return 2-3 bullet points (use "- " prefix) explaining why these columns
were chosen. Be specific and direct. No fluff.

Question: {question}
Outcome: {outcome} | Predictor: {treatment} | Unit: {unit} | Time: {time}
Available columns: {columns}

Example format:
- **Gold Price (USD/oz)** → directly measures what the question asks about (price level, not returns).
- **Consumer Confidence Index** → the only survey-based demand proxy in the dataset; range 50-119.
- **Date** → time index for sequencing observations; not used as a predictor.

Return bullet text only.
"""


WHY_MODEL_PROMPT = """Return 3 bullet points (use "- " prefix) explaining why {model_display}
was chosen and how to read its output. Max 15 words per bullet. No fluff.

Question: {question}
Data: {structure} | Outcome: {outcome} | Predictor: {treatment} | Unit: {unit} | Time: {time}

Cover: (1) what the model estimates, (2) why it fits this data structure, (3) how to read the coefficient.

Return bullet text only.
"""


FOLLOWUP_PROMPT = """Suggest 4 follow-up analyses. Each must be:
- A complete question the user can re-run verbatim
- Actionable with the same dataset
- Different in method or subset from the original

Question: {question} | Outcome: {outcome} | Predictor: {treatment} | Model: {model}
Result: {result_summary}

Return a JSON list of 4 strings only.
"""


VERDICT_PROMPT = """You are writing the headline finding of a statistical analysis for a general audience.
Write EXACTLY ONE sentence. Plain English — no jargon. Bold the key number using **like this**.

Rules:
- NEVER use: "p-value", "coefficient", "regression", "statistically significant", "OLS", "TWFE"
- DO use: "linked to", "associated with", "predicts", "rises by", "falls by", "no clear evidence"
- Include the numeric estimate if it's meaningful
- If not significant, say "no clear evidence" or "cannot confirm"

Inputs:
- Outcome: {outcome}
- Predictor: {treatment}
- Estimate: {estimate}
- p-value: {pvalue}
- 95% CI: [{ci_lo}, {ci_hi}]
- Model: {model}
- Is causal? {is_causal}

Examples of good verdicts:
- "A 1-point rise in interest rates is linked to **+0.40 percentage points** of unemployment — but the evidence is too uncertain to confirm this."
- "Trade openness **does not clearly predict** GDP growth in this 40-country dataset."
- "Carbon prices are strongly associated with **lower emissions** — a 1% price increase reduces emissions by **0.31%**."

Return exactly one sentence. No JSON, no bullet points.
"""


DEEP_ANALYSIS_PROMPT = """You are a senior econometrician writing punchy, scannable analysis.
Output FOUR sections, each with a bold header and 2-3 BULLETS underneath.
Max 18 words per bullet. Be specific about the actual numbers. NO fluff. NO hedging phrases.

Format (use this exact structure, no deviation):

**Magnitude**
- [bullet about the size of the effect in real-world terms]
- [bullet about how certain we are — CI direction, p-value plain English]

**Mechanism**
- [bullet on the causal pathway from {treatment} to {outcome}]
- [bullet on the most plausible confounder]

**What you didn't ask**
- [bullet on an unexpected pattern or heterogeneity]
- [bullet on policy/practical implication or related variable to check]

**Threats to validity**
- [bullet on the single biggest identification threat]
- [bullet on what would resolve it]

Inputs:
- Question: {question}
- Outcome: {outcome} | Predictor: {treatment}
- Domain: {domain}
- Model: {model}
- Estimate: {estimate} (SE={se}, p={pvalue}, 95% CI=[{ci_lo}, {ci_hi}])
- R²: {r2} | N: {n_obs}
- Time range: {time_range}
- Historical summary: {hist_summary}
- Web research context: {web_context}

Return the 4 sections with bold headers and bullets. No prose paragraphs. No JSON.
"""


WEB_RESEARCH_PROMPT = """You are an economic research assistant with deep knowledge of empirical literature.

A user is analyzing: {question}
Domain: {domain} | Outcome: {outcome} | Predictor: {treatment}
Time range: {time_range} | Geography: {geography}

From your training knowledge, provide 3-4 SHORT SENTENCES of research context:
1. What does the empirical literature say this effect size typically is?
2. Name one landmark paper or institution (IMF, World Bank, Fed, ECB, academic) with a specific finding.
3. What has happened in the real world with this relationship recently (2020-2024 if relevant)?
4. Any key debate or unresolved question in this literature?

Be specific. Use numbers where you know them. If uncertain, say "evidence is mixed" or "estimates vary widely."
Do NOT fabricate citations. Only cite studies you are confident exist.
Write 3-4 sentences of flowing prose. No bullet points. No headers.
"""


STAT_PLAIN_ENGLISH_PROMPT = """Translate a statistical result for an intelligent non-expert.
Return exactly 3 SHORT bullets (use "- " prefix). MAX 15 WORDS each. Punchy, no padding.

FORBIDDEN: "p-value", "coefficient", "regression", "statistically significant", "OLS", "standard error"
USE: "chance", "likely", "data shows", "we estimate", "uncertain", "roughly"

Inputs:
- Estimate: {estimate} {units}
- p-value: {pvalue}
- 95% CI: [{ci_lo}, {ci_hi}]
- R-squared: {r2}
- N observations: {n_obs}

Bullet 1: the finding (number + direction). Bullet 2: certainty (% chance language).
Bullet 3: how much R² explains (plain English, 1 phrase).

3 bullets. Max 15 words each. No fluff.
"""
