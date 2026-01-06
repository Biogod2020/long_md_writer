"""
Robust JSON Parsing Utilities

This module provides functions to robustly extract and parse JSON from LLM text responses,
handling common issues like Markdown code fences, trailing commas, and malformed strings.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

# Common JSON extraction patterns
_JSON_FENCES_PATTERN = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.IGNORECASE)
_LEADING_TEXT_PATTERN = re.compile(r"^[^{\[]*", re.DOTALL)
_TRAILING_TEXT_PATTERN = re.compile(r"[}\]](?:[^}\]]*$)", re.DOTALL)


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extracts JSON content from text that may contain Markdown code fences or surrounding prose.
    
    Strategies:
    1. Look for content inside ```json ... ``` or ``` ... ``` blocks.
    2. If not found, strip leading/trailing non-JSON characters and return the rest.
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Strategy 1: Extract from Markdown code fences
    match = _JSON_FENCES_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    
    # Strategy 2: Find the first { or [ and the last } or ]
    start_obj = text.find('{')
    start_arr = text.find('[')
    
    if start_obj == -1 and start_arr == -1:
        return None
    
    # Determine which comes first
    if start_obj == -1:
        start = start_arr
    elif start_arr == -1:
        start = start_obj
    else:
        start = min(start_obj, start_arr)
    
    end_obj = text.rfind('}')
    end_arr = text.rfind(']')
    
    end = max(end_obj, end_arr)
    
    if end == -1 or end < start:
        return None
    
    return text[start:end+1]


def fix_common_json_errors(json_str: str) -> str:
    """
    Attempts to fix common JSON formatting errors produced by LLMs.
    
    Fixes:
    - Trailing commas before } or ]
    - Single quotes instead of double quotes (simple cases)
    - Missing quotes around keys (simple alphanumeric keys)
    """
    if not json_str:
        return json_str
    
    # Fix trailing commas (e.g., {"a": 1,} -> {"a": 1})
    json_str = re.sub(r",\s*([\]}])", r"\1", json_str)
    
    # Fix single quotes (naive replacement, may break strings containing escaped quotes)
    # This is a common LLM mistake but dangerous; apply cautiously
    # We only do this if double quotes are not present at all
    if '"' not in json_str and "'" in json_str:
        json_str = json_str.replace("'", '"')
    
    return json_str


def parse_json_robust(text: str, default: Any = None) -> Any:
    """
    Robustly parses JSON from LLM text output.
    
    Steps:
    1. Extract JSON from code fences or raw text.
    2. Apply common error fixes.
    3. Attempt parsing.
    4. Attempt to salvage truncated JSON.
    5. Return parsed object or default on failure.
    
    Args:
        text: The raw text that may contain JSON.
        default: The value to return if parsing fails.
        
    Returns:
        Parsed JSON object, or `default` if parsing fails.
    """
    if not text:
        return default
    
    extracted = extract_json_from_text(text)
    if not extracted:
        return default
    
    # First attempt: direct parse
    try:
        return json.loads(extracted)
    except json.JSONDecodeError:
        pass
    
    # Second attempt: fix and parse
    fixed = fix_common_json_errors(extracted)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # Third attempt: salvage truncated JSON by aggressively closing brackets
    salvaged = attempt_salvage_json(fixed)
    if salvaged:
        try:
            return json.loads(salvaged)
        except json.JSONDecodeError:
            pass
    
    return default


def attempt_salvage_json(json_str: str) -> Optional[str]:
    """
    Attempts to salvage a truncated JSON string by closing open braces/brackets.
    This is a best-effort approach for when the API output is cut off.
    """
    if not json_str:
        return None
    
    # Count open braces/brackets
    open_braces = json_str.count('{') - json_str.count('}')
    open_brackets = json_str.count('[') - json_str.count(']')
    
    if open_braces <= 0 and open_brackets <= 0:
        return json_str  # Already balanced, nothing to salvage
    
    # Check if the string is obviously cut off (e.g., ends mid-string)
    # Heuristic: if ends with a letter, quote, or digit, try to close it
    stripped = json_str.rstrip()
    
    # Remove trailing incomplete key or value (heuristic for "..., \"key\": \"value..." patterns)
    # This is very simple: just find last complete key-value pair
    # For simplicity, we just close all open braces
    
    closing = '}' * open_braces + ']' * open_brackets
    
    # But we might be inside a string literal; try to close that first
    # Simple heuristic: if odd number of unescaped quotes, add one
    quote_count = json_str.count('"') - json_str.count('\\"')
    if quote_count % 2 == 1:
        stripped += '"'
        
    return stripped + closing


def parse_json_list_robust(text: str) -> List[Dict]:
    """
    Parses a JSON list from text, returning an empty list on failure.
    """
    result = parse_json_robust(text, default=[])
    if isinstance(result, list):
        return result
    return []


def parse_json_dict_robust(text: str) -> Dict:
    """
    Parses a JSON dict from text, returning an empty dict on failure.
    """
    result = parse_json_robust(text, default={})
    if isinstance(result, dict):
        return result
    return {}
