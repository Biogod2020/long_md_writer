"""
Robust JSON Parsing Utilities

This module provides functions to robustly extract and parse JSON from LLM text responses,
handling common issues like Markdown code fences, trailing commas, and malformed strings.
"""

import json
import re
from typing import Any, Dict, List, Optional

# Common JSON extraction patterns
_JSON_FENCES_PATTERN = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.IGNORECASE)
_LEADING_TEXT_PATTERN = re.compile(r"^[^{\[]*", re.DOTALL)
_TRAILING_TEXT_PATTERN = re.compile(r"[}\]](?:[^}\]]*$)", re.DOTALL)


def extract_json_balanced(text: str) -> Optional[str]:
    """
    SOTA 2.0 Balanced Bracket Extractor.
    Extracts the first complete JSON object/array by tracking bracket balance
    and ignoring content within string literals.
    """
    if not text:
        return None
    
    start_idx = -1
    for i, char in enumerate(text):
        if char in '{[':
            start_idx = i
            break
            
    if start_idx == -1:
        return None
        
    stack = []
    in_string = False
    escape = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if char == '"' and not escape:
            in_string = not in_string
            
        if not in_string:
            if char in '{[':
                stack.append(char)
            elif char in '}]':
                if not stack: return None # Unbalanced
                opening = stack.pop()
                if (opening == '{' and char != '}') or (opening == '[' and char != ']'):
                    return None # Mismatched
                
                if not stack:
                    return text[start_idx:i+1]
        
        if char == '\\' and not escape:
            escape = True
        else:
            escape = False
            
    return None


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extracts JSON content from text that may contain Markdown code fences, 
    nested <thought> blocks, or surrounding prose.
    """
    if not text:
        return None
    
    # 1. Clean up <thought> blocks first to prevent interference
    text = re.sub(r'<thought>[\s\S]*?</thought>', '', text).strip()
    
    # 2. Strategy 1: Find ALL Markdown code fences and try the last one first
    matches = list(_JSON_FENCES_PATTERN.finditer(text))
    if matches:
        for match in reversed(matches):
            content = match.group(1).strip()
            if content: 
                # Check if it's a complete JSON within the fence
                balanced = extract_json_balanced(content)
                if balanced: return balanced
    
    # 3. Strategy 2: Use balanced extraction on the whole text
    return extract_json_balanced(text)


def fix_common_json_errors(json_str: str) -> str:
    """
    Attempts to fix common JSON formatting errors produced by LLMs.
    Specifically targets trailing commas, unescaped newlines, and raw LaTeX backslashes.
    """
    if not json_str:
        return json_str
    
    # A. Fix trailing commas (e.g., {"a": 1,} -> {"a": 1})
    json_str = re.sub(r",\s*([\]}])", r"\1", json_str)
    
    # B. SOTA: Handle unescaped newlines inside JSON strings
    def replace_newlines(match):
        return match.group(0).replace('\n', '\\n').replace('\r', '\\r')
    
    json_str = re.sub(r'"([^"\\]|\\.)*"', replace_newlines, json_str)
    
    # C. SOTA: Advanced LaTeX Backslash Cleaner
    # Matches a backslash that is NOT part of a standard JSON escape sequence
    # Standard: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    def safe_backslash_replace(match):
        s = match.group(0)
        inner = s[1:-1]
        
        # 1. Protect existing double backslashes (the only way to have a literal backslash in valid JSON)
        step1 = inner.replace('\\\\', '\x01\x01')
        
        # 2. Protect other valid escape sequences: \", \/, \b, \f, \n, \r, \t, \uXXXX
        def protect_valid(m):
            return f"\x02{m.group(1)}"
        step2 = re.sub(r'\\(["/bfnrt]|u[0-9a-fA-F]{4})', protect_valid, step1)
        
        # 3. Any remaining naked backslashes were NOT intended to be escaped (e.g. malformed LaTeX).
        # Double them now.
        step3 = step2.replace('\\', '\\\\')
        
        # 4. Restore placeholders to standard backslashes
        fixed_inner = step3.replace('\x01', '\\').replace('\x02', '\\')
        
        return f'"{fixed_inner}"'

    # Only apply to content inside double quotes
    json_str = re.sub(r'"[\s\S]*?"', safe_backslash_replace, json_str)

    # D. Fix missing quotes around boolean values or nulls if they are capitalized
    json_str = re.sub(r':\s*True\b', ': true', json_str)
    json_str = re.sub(r':\s*False\b', ': false', json_str)
    json_str = re.sub(r':\s*None\b', ': null', json_str)
    
    return json_str

def attempt_salvage_json(json_str: str) -> Optional[str]:
    """
    SOTA 2.0 Aggressive Salvage logic.
    Closes all unclosed structures and handles mid-string truncation.
    """
    if not json_str:
        return None
    
    json_str = json_str.strip()
    
    # Handle mid-string truncation (e.g., "feedback": "The text is...)
    # If the last character is not a structural marker or digit/bool, 
    # and we have an odd number of quotes, close the quote.
    quote_count = json_str.count('"') - json_str.count('\\"')
    if quote_count % 2 == 1:
        json_str += '"'
    
    # Count open braces/brackets
    open_braces = json_str.count('{') - json_str.count('}')
    open_brackets = json_str.count('[') - json_str.count(']')
    
    if open_braces <= 0 and open_brackets <= 0:
        return json_str  # Already balanced
    
    # Append closing characters in reverse order of typical nesting
    # This is a heuristic but highly effective for LLM outputs
    closing = ""
    if open_brackets > 0:
        closing += ']' * open_brackets
    if open_braces > 0:
        closing += '}' * open_braces
        
    return json_str + closing


def parse_json_robust(text: str, default: Any = None) -> Any:
    """
    Robustly parses JSON from LLM text output.
    
    Steps:
    1. Extract JSON from code fences or raw text.
    2. Apply common error fixes (trailing commas, LaTeX backslashes).
    3. Attempt parsing.
    4. Attempt to salvage truncated JSON (closing brackets).
    5. Return parsed object or default on failure.
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
    
    # Second attempt: fix common formatting errors and parse
    fixed = fix_common_json_errors(extracted)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # Third attempt: salvage truncated JSON by aggressively closing structures
    salvaged = attempt_salvage_json(fixed)
    if salvaged:
        try:
            return json.loads(salvaged)
        except json.JSONDecodeError:
            pass
    
    return default

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
