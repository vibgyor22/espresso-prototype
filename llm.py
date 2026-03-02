import json
import google.genai as genai
import os
from dotenv import load_dotenv
import ssl
import time
import random

# Load the API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize client with SSL verification handling
try:
    # Set a reasonable timeout (60 seconds for API calls)
    import socket
    socket.setdefaulttimeout(60)
    client = genai.Client(api_key=api_key)
    print("[LLM] Gemini client initialized successfully")
except Exception as e:
    print(f"Warning: Client initialization issue: {e}")
    print("Retrying with lenient SSL context...")
    try:
        # Create lenient SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        socket.setdefaulttimeout(60)
        client = genai.Client(api_key=api_key)
        print("[LLM] Gemini client initialized with lenient SSL")
    except Exception as e2:
        print(f"Error: Could not initialize Gemini client: {e2}")
        client = None

# This is the instruction we give to Gemini
SYSTEM_PROMPT = """You are a JSON extractor. Extract analytical intent from questions and output ONLY valid JSON.

Instructions:
- Extract: question_type (causal_effect or forecast), outcome, treatment, time, unit, unit_value, forecast_periods
- Look for time-related words: year, month, date, period, time, when, temporal
- Look for unit/group words: country, region, state, entity, group, unit, subject
- Extract "unit" as the TYPE (e.g., "country", "region", "company")
- Extract "unit_value" as the SPECIFIC entity (e.g., "India", "Finland", "United States") OR description (e.g., "most happy country in europe", "largest economy")
- For forecast questions: extract the NUMBER of periods to forecast (e.g., "next 10 years" -> forecast_periods: 10)
- If forecast_periods not specified, use 10 as default
- If not explicitly mentioned, infer from context
- Use null ONLY if truly impossible to extract

Example 1: "What is the effect of interest rates on unemployment?"
{"question_type": "causal_effect", "outcome": "unemployment", "treatment": "interest_rate", "time": "year", "unit": "country", "unit_value": null, "forecast_periods": null}

Example 2: "What is the forecast of unemployment for India for the next 10 years?"
{"question_type": "forecast", "outcome": "unemployment", "treatment": null, "time": "year", "unit": "country", "unit_value": "India", "forecast_periods": 10}

Example 3: "forecast gdp for the most happy country in europe next 5 years"
{"question_type": "forecast", "outcome": "gdp", "treatment": null, "time": "year", "unit": "country", "unit_value": "most happy country in europe", "forecast_periods": 5}

Example 4: "How will sales change next quarter?"
{"question_type": "forecast", "outcome": "sales", "treatment": null, "time": "quarter", "unit": null, "unit_value": null, "forecast_periods": 1}

Output JSON only, no other text:"""


def _generate_with_retry(model, contents, config=None, max_retries=5):
    """
    Call Gemini with retry/backoff to handle 429s and transient failures.
    """
    if not client:
        raise RuntimeError("Gemini client not initialized")

    base_delay = 2.0
    max_delay = 30.0

    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            msg = str(e).lower()
            is_rate_limit = "429" in msg or "rate" in msg or "resource_exhausted" in msg or "too many requests" in msg
            is_transient = is_rate_limit or "timeout" in msg or "temporarily" in msg or "unavailable" in msg

            if attempt == max_retries or not is_transient:
                raise

            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0, 0.5)
            sleep_for = delay + jitter
            print(f"[LLM] Transient error (attempt {attempt}/{max_retries}). Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)

def parse_question(text):
    """
    This function sends your question to Gemini and gets back
    a structured understanding of what you're asking
    """
    if not client:
        print("[ERROR] Gemini client not initialized")
        return None
        
    try:
        print(f"[LLM] Parsing question: {text[:50]}...")
        response = _generate_with_retry(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\n\nQuestion: {text}\n\nRespond with JSON only:",
            config={
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 40
            }
        )
        
        content = response.text.strip()
        print(f"[LLM] Raw response: {content[:100]}...")
        
        # Try to extract JSON if there's extra text
        if "{" in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            content = content[start:end]
        
        result = json.loads(content)
        print(f"[LLM] Parsed intent: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] Error calling Gemini for parse_question: {e}")
        import traceback
        traceback.print_exc()
        return None


def map_columns(intent, column_samples):
    """
    Given an `intent` (from parse_question) and a dict of `column_samples`
    (as returned by `get_column_samples`), ask Gemini to map the logical fields
    (outcome, treatment, time, unit) to the actual column names in the dataset.

    `column_samples` should be a dict: {column_name: [sample_value_strs...]}

    Returns a dict mapping each field to a column name or null.
    Example: {"outcome": "unemployment", "treatment": "interest_rate", "time": "year", "unit": "country"}
    """
    if not client:
        print("[ERROR] Gemini client not initialized")
        return {"outcome": None, "treatment": None, "time": None, "unit": None}
        
    try:
        print(f"[LLM] Mapping columns for intent: {intent}")
        
        # Build a concise description of columns and a few sample values
        cols_text_lines = []
        for col, samples in column_samples.items():
            sample_preview = ", ".join(samples[:5]) if samples else ""
            cols_text_lines.append(f"- {col}: {sample_preview}")
        cols_text = "\n".join(cols_text_lines)

        # Ask the LLM to decide whether the dataset is 'indicator-style' (one row per series and year columns)
        # or a regular column-per-variable table, and to return a single mapping that includes
        # whether to pivot and how to identify variables.
        # The LLM should return JSON with this schema (only JSON):
        # {
        #   "outcome": {"type":"column"|"indicator","value":"<column name or indicator value>"},
        #   "treatment": {"type":"column"|"indicator","value":"<column name or indicator value>"},
        #   "time": {"type":"column","value":"<column name>"} OR {"type":"years","value":["1980","1981"]},
        #   "unit": {"type":"column","value":"<column name>"},
        #   "pivot": true|false,
        #   "indicator_column": "<column name>" or null,
        #   "year_columns": ["1980","1981",...] or null,
        #   "notes": "brief explanation"
        # }

        prompt = (
            "You are given a dataset's column names and sample values. Decide whether this dataset "
            "is 'indicator-style' (one row per series with year columns) or a regular tidy table. "
            "Return a single JSON object describing how to map the user's intent variables to the dataset.\n\n"
            f"Columns and samples:\n{cols_text}\n\n"
            f"User intent: {json.dumps(intent)}\n\n"
            "CRITICAL: If the dataset has an 'indicator' or 'series' column with many values, "
            "map outcome/treatment to EXACT indicator/series values that you can see in the samples. "
            "DO NOT invent or imagine indicator names. Only use names that appear in the column samples.\n\n"
            "RESPONSE FORMAT (JSON only):\n"
            "{\n"
            "  \"outcome\": {\"type\": \"column|indicator\", \"value\": \"...\"},\n"
            "  \"treatment\": {\"type\": \"column|indicator\", \"value\": \"...\"},\n"
            "  \"time\": {\"type\": \"column|years\", \"value\": \"<column name>\" or [list of year columns]},\n"
            "  \"unit\": {\"type\": \"column\", \"value\": \"<column name>\"},\n"
            "  \"pivot\": true|false,\n"
            "  \"indicator_column\": \"<column name>\" or null,\n"
            "  \"year_columns\": [list of year-like columns] or null,\n"
            "  \"notes\": \"short explanation\"\n"
            "}\n\n"
            "Be conservative: if you think the dataset must be pivoted to extract time series, set \"pivot\": true and return the indicator column and year columns.\n"
            "Only output valid JSON matching the schema."
        )

        print("[LLM] Sending column mapping request to Gemini...")
        response = _generate_with_retry(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 40
            }
        )

        content = response.text.strip()
        print(f"[LLM] Mapping response received: {content[:100]}...")
        
        if "{" in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            content = content[start:end]

        mapping = json.loads(content)
        print(f"[LLM] Column mapping complete: {list(mapping.keys())}")
        return mapping
    except Exception as e:
        print(f"[ERROR] Error mapping columns with Gemini: {e}")
        import traceback
        traceback.print_exc()
        return {"outcome": None, "treatment": None, "time": None, "unit": None}

def identify_unit_value(unit_description, unit_column_name, df):
    """
    Identify the specific unit value from the data based on a description.
    
    Args:
        unit_description: Description or name of the unit (e.g., "India", "most happy country in europe")
        unit_column_name: Name of the unit column in the dataframe
        df: The dataframe containing the data
        
    Returns:
        The actual unit value from the dataframe, or None if not found
    """
    if not client or not unit_description or not unit_column_name:
        return None
    
    try:
        # Get unique unit values from the dataframe
        all_units = df[unit_column_name].dropna().unique().tolist()
        
        # Smart sampling: if description appears to be an exact name, prioritize units with partial matches
        potential_matches = [u for u in all_units if unit_description.lower() in str(u).lower()]
        
        if potential_matches:
            # Include matches first, then fill with other units
            unique_units = potential_matches[:50] + [u for u in all_units if u not in potential_matches][:50]
        else:
            # No obvious matches, use first 100
            unique_units = all_units[:100]
        
        prompt = f"""You are given a list of {unit_column_name} values from a dataset.
Your task is to identify which specific value matches the description: "{unit_description}"

Available {unit_column_name} values:
{', '.join(str(u) for u in unique_units)}

Rules:
- If the description is an exact match or close match to one of the values, return that value
- If the description is a characteristic (e.g., "most happy country in europe"), use your knowledge to identify the best match
- For "most happy country in europe", return "Finland" (if it exists in the list)
- For "largest economy", return "United States" (if it exists in the list)
- Return ONLY the exact value from the list, nothing else
- If no match can be made, return "NOT_FOUND"

Output only the matched value:"""
        
        print(f"[LLM] Identifying unit: '{unit_description}'...")
        response = _generate_with_retry(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 40
            }
        )
        
        identified_unit = response.text.strip()
        print(f"[LLM] Identified unit: '{identified_unit}'")
        
        # Verify the identified unit exists in the data (check all units, not just first 100)
        if identified_unit in all_units:
            return identified_unit
        elif identified_unit != "NOT_FOUND":
            # Try case-insensitive exact match
            for unit in all_units:
                if str(unit).lower() == identified_unit.lower():
                    return unit
            
            # Extract key country name (ignore "People's Republic of", "Kingdom of", etc.)
            identified_lower = identified_unit.lower()
            # Common prefixes/suffixes to ignore
            ignore_phrases = ['people\'s republic of', 'republic of', 'kingdom of', 'special administrative region', 
                            'the', 'province of', 'commonwealth of', 'state of']
            
            # Try to find main country name
            identified_clean = identified_lower
            for phrase in ignore_phrases:
                identified_clean = identified_clean.replace(phrase, '').strip(' ,')
            
            # Now try fuzzy matching with cleaned names
            best_match = None
            best_score = 0
            
            for unit in all_units:
                unit_lower = str(unit).lower()
                unit_clean = unit_lower
                for phrase in ignore_phrases:
                    unit_clean = unit_clean.replace(phrase, '').strip(' ,')
                
                # Check if clean names match
                if identified_clean and unit_clean:
                    # Exact match on cleaned names
                    if identified_clean == unit_clean:
                        print(f"[LLM] Fuzzy matched '{identified_unit}' to '{unit}' (cleaned name match)")
                        return unit
                    
                    # Check overlap
                    if (identified_clean in unit_clean or unit_clean in identified_clean) and len(identified_clean) > 3:
                        # Prefer shorter unit names (avoid administrative regions)
                        if 'special administrative region' not in unit_lower:
                            score = 1.0 / (1 + 0.1 * len(unit.split()))
                            if score > best_score:
                                best_score = score
                                best_match = unit
            
            if best_match:
                print(f"[LLM] Fuzzy matched '{identified_unit}' to '{best_match}'")
                return best_match
        
        return None
    except Exception as e:
        print(f"[ERROR] Error identifying unit: {e}")
        return None


def query_gemini(prompt):
    """
    Send a prompt to Gemini and get back a text response.
    Used for interpretation and explanation generation.
    
    Args:
        prompt: String prompt to send to Gemini
        
    Returns:
        String response from Gemini
    """
    try:
        response = _generate_with_retry(
            model="gemini-2.5-pro",
            contents=prompt,
            config={
                "temperature": 0.7,  # More natural, conversational responses
                "top_p": 0.95,
                "top_k": 40
            }
        )
        return response.text.strip() if response and response.text else ""
    except Exception as e:
        print(f"Error querying Gemini: {e}")
        return ""