"""
Domain engine — infers domain from variable names, identifies known economic laws,
and contextualizes R² relative to domain norms.
"""

from __future__ import annotations

from typing import Optional


_DOMAIN_HINTS = [
    (("gdp", "inflation", "interest_rate", "unemployment", "monetary", "cpi", "output"),
     "macroeconomics"),
    (("wage", "income", "employment", "labor", "labour", "minimum_wage", "quit"),
     "labor economics"),
    (("school", "education", "test_score", "literacy", "enrollment"),
     "education"),
    (("health", "mortality", "infant", "obesity", "diabetes", "hospital"),
     "public health"),
    (("calorie", "nutrition", "food", "diet", "bmi"),
     "nutrition / food"),
    (("price", "stock", "return", "volatility", "yield", "spread", "equity", "bond", "vix", "ffr"),
     "finance"),
    (("co2", "emission", "carbon", "temperature", "climate", "pollution"),
     "climate / environment"),
    (("trade", "export", "import", "tariff"),
     "international trade"),
    (("crime", "arrest", "incarceration", "policing"),
     "crime"),
    (("poverty", "inequality", "gini"),
     "inequality"),
    (("housing", "rent", "mortgage", "real_estate"),
     "housing"),
]


def infer_domain(outcome: str, treatment: Optional[str] = None) -> Optional[str]:
    text = " ".join(filter(None, [outcome or "", treatment or ""])).lower()
    for keys, label in _DOMAIN_HINTS:
        if any(k in text for k in keys):
            return label
    return None


# Known law definitions: (outcome_keywords, treatment_keywords, name, description, benchmark_coef)
_KNOWN_LAWS = [
    ({"unemployment"}, {"gdp", "gdp_growth", "output"},
     "Okun's Law",
     "GDP growth and unemployment change are inversely related (~2:1 ratio). "
     "A 1pp GDP growth reduction raises unemployment by ~0.4–0.6pp.",
     "−0.4 to −0.6 (pp unemployment per 1pp GDP growth)"),

    ({"unemployment"}, {"inflation", "cpi"},
     "Phillips Curve",
     "Short-run trade-off between inflation and unemployment. "
     "Higher inflation is associated with lower unemployment (in the short run).",
     "Slope varies by era; NAIRU models give −0.5 to −1.5pp per 1pp inflation"),

    ({"inflation", "cpi"}, {"money_supply", "m1", "m2"},
     "Quantity Theory of Money",
     "Long-run: money supply growth ≈ inflation. "
     "Friedman: 'Inflation is always and everywhere a monetary phenomenon.'",
     "Near 1.0 in long-run cross-country data"),

    ({"inflation", "cpi"}, {"oil", "oil_price", "energy"},
     "Oil–Inflation Pass-through",
     "Supply-side oil shocks raise consumer prices. "
     "Empirical pass-through is 0.3–0.7 (fraction of oil price change passed to CPI).",
     "0.03–0.07pp CPI per 1% oil price change (IV estimates)"),

    ({"return", "stock", "equity"}, {"interest_rate", "ffr", "rate"},
     "Fed–Market Rate Effect",
     "Interest rate increases are associated with lower equity returns "
     "(higher discount rate, tighter financial conditions).",
     "−0.2 to −0.5pp return per 1pp rate increase (3-month horizon)"),

    ({"emissions", "co2"}, {"carbon_price", "carbon_tax", "ets"},
     "Carbon Price Elasticity",
     "Higher carbon prices reduce industrial emissions. "
     "EU ETS panel estimates give an elasticity around −0.2 to −0.4.",
     "−0.2 to −0.4 (% emission reduction per 1% price increase, elasticity)"),

    ({"gdp", "output"}, {"trade", "openness"},
     "Trade–Growth Relationship",
     "Trade openness and income growth are positively correlated. "
     "IV estimates suggest ~0.5–1.5pp GDP per 10pp trade/GDP ratio.",
     "+0.5 to +1.5pp GDP growth per 10pp trade openness"),
]


def identify_known_law(outcome: str, treatment: Optional[str] = None,
                        domain: Optional[str] = None) -> Optional[dict]:
    """
    Returns dict with {name, description, benchmark} if this variable pair matches
    a known economic law, else None.
    """
    if not outcome:
        return None
    o_low = outcome.lower()
    t_low = (treatment or "").lower()

    for out_keys, treat_keys, name, desc, bench in _KNOWN_LAWS:
        out_match = any(k in o_low for k in out_keys)
        if not out_match:
            # Also check reversed roles
            out_match = any(k in t_low for k in out_keys)
            treat_match = any(k in o_low for k in treat_keys)
        else:
            treat_match = any(k in t_low for k in treat_keys)

        if out_match and (not treat_keys or treat_match):
            return {"name": name, "description": desc, "benchmark": bench}
    return None


_DOMAIN_R2_NORMS = {
    "macroeconomics":       (0.15, 0.55, "macro models typically explain 15–55%"),
    "labor economics":      (0.10, 0.50, "labor market regressions typically explain 10–50%"),
    "finance":              (0.02, 0.15, "asset pricing models explain 2–15% — markets are mostly noise"),
    "climate / environment":(0.20, 0.70, "environmental regressions often explain 20–70%"),
    "international trade":  (0.15, 0.60, "gravity-type models typically explain 40–80%"),
    "public health":        (0.10, 0.40, "health outcome models typically explain 10–40%"),
    "education":            (0.10, 0.45, "education outcome models typically explain 10–45%"),
    "housing":              (0.20, 0.70, "housing price regressions typically explain 20–70%"),
    "inequality":           (0.15, 0.50, "inequality regressions typically explain 15–50%"),
}


def contextualize_r2(r2: float, domain: Optional[str]) -> str:
    """Return a sentence contextualizing R² relative to domain norms."""
    if domain is None or domain not in _DOMAIN_R2_NORMS:
        pct = r2 * 100
        if pct < 5:
            return f"R² = {pct:.1f}% — very low explanatory power."
        elif pct < 20:
            return f"R² = {pct:.1f}% — modest explanatory power."
        elif pct < 50:
            return f"R² = {pct:.1f}% — moderate explanatory power."
        else:
            return f"R² = {pct:.1f}% — high explanatory power."

    lo, hi, norm_desc = _DOMAIN_R2_NORMS[domain]
    pct = r2 * 100
    if r2 < lo:
        verdict = "below the typical range"
    elif r2 > hi:
        verdict = "above the typical range — unusually high"
    else:
        verdict = "within the typical range"

    return (
        f"R² = {pct:.1f}% is {verdict} for {domain} "
        f"({norm_desc}; typical {lo*100:.0f}–{hi*100:.0f}%)."
    )
