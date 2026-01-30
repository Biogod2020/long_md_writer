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
from typing import Tuple, Optional, Dict, Set
from diff_match_patch import diff_match_patch

class IndentationNormalizer:
    @staticmethod
    def get_indent(line: str) -> str:
        import re
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
    """Last resort: Fuzzy matching using diff-match-patch."""
    dmp = diff_match_patch()
    dmp.Match_Threshold = 0.5
    loc = dmp.match_main(content, search_block, 0)
    
    if loc != -1:
        if "\n" in search_block:
            start_l = content.rfind("\n", 0, loc) + 1 if "\n" in content[:loc] else 0
            end_l = content.find("\n", loc + len(search_block))
            if end_l == -1: end_l = len(content)
            else: end_l += 1
            
            indent = IndentationNormalizer.get_indent(content[start_l:])
            r_lines = replace_block.splitlines()
            indented_r = "".join([f"{indent}{l}\n" if l.strip() else "\n" for l in r_lines])
            return content[:start_l] + indented_r + content[end_l:]
        else:
            return content[:loc] + replace_block + content[loc + len(search_block):]
    return None

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