"""
Universal High-Precision Patcher
Refined based on gemini-cli and aider matching strategies.
"""

import re
import json
import subprocess
import sys
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from diff_match_patch import diff_match_patch

class IndentationNormalizer:
    @staticmethod
    def get_indent(line: str) -> str:
        match = re.match(r'^(\s*)', line)
        return match.group(1) if match else ""

class StuckDetector:
    """
    Detects if a QA loop is stuck by tracking progress.
    """
    def __init__(self):
        self.last_hashes = {} # advice_id -> last_content_hash

    def _get_hash(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def check_progress(self, advice_id: str, current_content: str) -> bool:
        """
        Returns True if progress is being made (content changed since last time for this advice).
        Returns False if we are repeating the same advice on the same content.
        """
        c_hash = self._get_hash(current_content)
        
        if advice_id not in self.last_hashes:
            self.last_hashes[advice_id] = c_hash
            return True
            
        if self.last_hashes[advice_id] == c_hash:
            return False # STUCK
            
        self.last_hashes[advice_id] = c_hash
        return True

def apply_native_patch(content: str, search_block: str, replace_block: str) -> Optional[str]:
    """Calls the Node.js bridge to execute gemini-cli logic."""
    bridge_path = Path(__file__).parent / "native_patcher.js"
    if not bridge_path.exists():
        return None
        
    payload = json.dumps({
        "content": content,
        "search": search_block,
        "replace": replace_block
    })
    
    try:
        process = subprocess.Popen(
            ["node", str(bridge_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=payload)
        
        if process.returncode == 0:
            try:
                resp = json.loads(stdout)
                if resp.get("success"):
                    return resp["result"]
            except json.JSONDecodeError:
                pass
        return None
    except Exception as e:
        print(f"  [Patcher] Native bridge error: {e}", file=sys.stderr)
        return None

def apply_fuzzy_fallback(content: str, search_block: str, replace_block: str) -> Optional[str]:
    """Last resort: Fuzzy matching using diff-match-patch to find boundaries."""
    dmp = diff_match_patch()
    # SOTA: Relax threshold slightly for technical content/math formulas
    dmp.Match_Threshold = 0.6 
    dmp.Match_Distance = 1000
    
    # 1. Find the best starting location
    loc = dmp.match_main(content, search_block, 0)
    if loc == -1:
        return None
        
    # 2. Use diff to find where the search_block actually ends in the content
    # We take a significantly larger chunk to ensure we capture the entire match
    margin = max(len(search_block), 100)
    content_chunk = content[loc : loc + len(search_block) + margin]
    diffs = dmp.diff_main(search_block, content_chunk)
    
    # 3. Calculate how much of the content was "consumed" by the search_block
    content_consumed = 0
    search_consumed = 0
    for op, text in diffs:
        if op == 0: # Equal
            content_consumed += len(text)
            search_consumed += len(text)
        elif op == 1: # Insertion in content (extra char in file)
            content_consumed += len(text)
        elif op == -1: # Deletion from content (missing char in file)
            search_consumed += len(text)
            
        if search_consumed >= len(search_block):
            break
            
    # 4. Perform the replacement
    actual_match_end = loc + content_consumed
    
    # Special handling for multiline to preserve indentation if possible
    if "\n" in search_block:
        # Find start of line for the match to determine base indentation
        line_start = content.rfind("\n", 0, loc) + 1 if "\n" in content[:loc] else 0
        current_indent = IndentationNormalizer.get_indent(content[line_start:])
        
        # SOTA: Re-apply indentation to every line of the replacement block
        r_lines = replace_block.splitlines()
        if not r_lines:
            indented_r = ""
        else:
            # Preserve original first-line indentation if it was already provided
            first_line_indent = IndentationNormalizer.get_indent(r_lines[0])
            if first_line_indent == current_indent:
                indented_r = "\n".join(r_lines)
            else:
                indented_r = "\n".join([f"{current_indent}{l.lstrip()}" if l.strip() else "" for l in r_lines])
        
        if replace_block.endswith("\n") and not indented_r.endswith("\n"):
            indented_r += "\n"
            
        return content[:loc] + indented_r + content[actual_match_end:]
    else:
        return content[:loc] + replace_block + content[actual_match_end:]

def apply_smart_patch(content: str, search_block: str, replace_block: str) -> Tuple[str, bool]:
    """Tiered patching strategy."""
    if not search_block:
        return "Search block is empty.", False

    res = apply_native_patch(content, search_block, replace_block)
    if res is not None:
        return res, True
        
    res = apply_fuzzy_fallback(content, search_block, replace_block)
    if res is not None:
        return res, True
        
    return "No unique match found using any patching strategy.", False