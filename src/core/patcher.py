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
    # SOTA: Stricter threshold (0.0=exact, 1.0=anything)
    dmp.Match_Threshold = 0.4 
    dmp.Match_Distance = 100000 # Increased from 1000 to find better matches in larger files
    
    # 1. Find the best starting location
    loc = dmp.match_main(content, search_block, 0)
    if loc == -1:
        return None
        
    # 2. Find precise boundaries using diff
    margin = max(len(search_block), 100)
    match_region = content[loc : loc + len(search_block) + margin]
    diffs = dmp.diff_main(search_block, match_region)
    
    content_consumed = 0
    search_consumed = 0
    for op, text in diffs:
        if op == 0: # Equal
            content_consumed += len(text)
            search_consumed += len(text)
        elif op == 1: # Insertion in content
            content_consumed += len(text)
        elif op == -1: # Deletion from content
            search_consumed += len(text)
        if search_consumed >= len(search_block):
            break
            
    actual_match_end = loc + content_consumed
    matched_content = content[loc:actual_match_end]

    # 3. Verify quality of the match
    diffs_for_score = dmp.diff_main(search_block, matched_content)
    levenshtein = dmp.diff_levenshtein(diffs_for_score)
    similarity = 1 - (levenshtein / max(len(search_block), len(matched_content), 1))
    
    if similarity < 0.7:
        return None
    
    # 4. Handle indentation for multiline blocks
    if "\n" in search_block:
        line_start = content.rfind("\n", 0, loc) + 1 if "\n" in content[:loc] else 0
        target_base_indent = IndentationNormalizer.get_indent(content[line_start:])
        
        search_lines = search_block.splitlines()
        search_base_indent = IndentationNormalizer.get_indent(search_lines[0]) if search_lines else ""
        
        r_lines = replace_block.splitlines()
        indented_lines = []
        
        for line in r_lines:
            if not line.strip():
                indented_lines.append("")
                continue
            
            line_indent = IndentationNormalizer.get_indent(line)
            if line_indent.startswith(search_base_indent):
                relative_indent = line_indent[len(search_base_indent):]
                indented_lines.append(f"{target_base_indent}{relative_indent}{line.lstrip()}")
            else:
                indented_lines.append(f"{target_base_indent}{line.lstrip()}")
        
        indented_r = "\n".join(indented_lines)
        if replace_block.endswith("\n"):
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