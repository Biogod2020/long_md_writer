"""
VisualQAAgent: Dual-agent architecture for visual inspection and code fixes.

Architecture:
- Critic: Analyzes screenshots → returns issue checklist
- Fixer: Takes ONE issue → generates code fix
- Loop until all sections PASS or no more fixes can be applied
"""

import re
import json
from pathlib import Path
from typing import Optional, List, Dict

from ...core.gemini_client import GeminiClient
from ...core.types import AgentState

from .screenshot import take_screenshots, prepare_section_preview
from .critic import run_critic
from .fixer import run_fixer, apply_fix
from .utils import draw_bounding_boxes

class VisualQAAgent:
    """Agent that performs visual inspection and automated repairs."""

    def __init__(
        self, 
        client: Optional[GeminiClient] = None, 
        debug: bool = False, 
        headless: bool = True
    ):
        self.client = client or GeminiClient()
        self.debug = debug
        self.headless = headless

    def run(self, state: AgentState) -> AgentState:
        """Execute visual QA using Critic-Fixer dual-agent architecture."""
        if not state.completed_html_sections:
            print("  [VisualQA] No HTML sections to check.")
            return state

        print(f"  [VisualQA] Starting Critic-Fixer Loop...")

        any_modified = False
        workspace = Path(state.workspace_path)
        debug_dir = workspace / "critic_debug"
        debug_dir.mkdir(exist_ok=True)
        
        style_mapping_path = workspace / "style_mapping.json"

        total_iterations = 0
        for section_idx, section_path in enumerate(state.completed_html_sections):
            section_name = Path(section_path).name
            print(f"\n  [VisualQA] 🔍 Processing: html/{section_name}")
            
            iteration = 0
            while True:  # No limit for testing
                iteration += 1
                print(f"\n    [Iteration {iteration}] Running Visual Critic...")
                
                # Step 1: Prepare preview and take screenshots
                preview_path = prepare_section_preview(
                    section_path, 
                    state.workspace_path,
                    ""  # Not using template
                )
                if not preview_path:
                    print(f"    [Critic] ⚠️ Failed to create preview. Skipping section.")
                    break
                
                screenshots = take_screenshots(
                    preview_path, 
                    state.workspace_path,
                    headless=self.headless,
                    debug=self.debug
                )
                
                # Cleanup preview
                if preview_path.exists():
                    preview_path.unlink()
                
                if not screenshots:
                    print(f"    [Critic] ⚠️ Failed to capture screenshots. Skipping section.")
                    break
                
                # Step 2: Critic reviews screenshots (Purely vision-based)
                critique = run_critic(
                    self.client,
                    screenshots,
                    debug=self.debug
                )
                
                if critique is None:
                    print(f"    [Critic] ⚠️ Error during critique. Moving to next section.")
                    break
                
                if critique.get("verdict") == "PASS":
                    print(f"    [Critic] ✅ Section PASSED after {iteration} iteration(s).")
                    break
                
                issues = critique.get("issues", [])
                if not issues:
                    print(f"    [Critic] ✅ No issues found. PASSED.")
                    break
                
                print(f"    [Critic] Found {len(issues)} issue(s):")
                
                # Visual Debugging: Local program highlights issues on screenshots
                issue_debug_paths = {}
                for issue in issues:
                    part_idx = issue.get("location_part", 1) - 1
                    issue_id = issue.get("id", "unknown")
                    if 0 <= part_idx < len(screenshots):
                        debug_path = debug_dir / f"debug_{section_name}_it{iteration}_{issue_id}.jpg"
                        draw_bounding_boxes(screenshots[part_idx], [issue], debug_path)
                        issue_debug_paths[issue_id] = debug_path
                        print(f"      - [{issue.get('severity', '?')}] {issue.get('problem', 'No description')[:80]}")
                        print(f"        (Debug: locator box saved to critic_debug/{debug_path.name})")
                
                # Step 3: Fixer addresses each issue
                fixes_applied = 0
                for issue in issues:
                    issue_id = issue.get("id", "unknown")
                    print(f"\n    [Fixer] Addressing: {issue_id}")
                    
                    fix_result = run_fixer(
                        self.client,
                        issue,
                        section_path,
                        state.workspace_path,
                        style_mapping_path=str(style_mapping_path),
                        debug_image_path=issue_debug_paths.get(issue_id),
                        debug=self.debug
                    )
                    
                    if fix_result and fix_result.get("status") == "FIXED":
                        applied = apply_fix(fix_result, state.workspace_path)
                        if applied:
                            fixes_applied += 1
                            any_modified = True
                            print(f"    [Fixer] ✅ Applied fix to {fix_result.get('target_file')}")
                    else:
                        reason = fix_result.get("reason", "Unknown") if fix_result else "No response"
                        print(f"    [Fixer] ⏭️ Skipped: {reason}")
                
                if fixes_applied == 0:
                    print(f"    [Iteration {iteration}] No fixes applied. Breaking to avoid infinite loop.")
                    break
                
                print(f"    [Iteration {iteration}] Applied {fixes_applied} fix(es). Re-rendering...")

            total_iterations += iteration

        if any_modified:
            print(f"\n  [VisualQA] Files were modified. Requesting re-assembly.")
            state.vqa_needs_reassembly = True
        else:
            print(f"\n  [VisualQA] All sections processed. No modifications needed.")
            state.vqa_needs_reassembly = False
            
        state.vqa_iterations = total_iterations
        return state
