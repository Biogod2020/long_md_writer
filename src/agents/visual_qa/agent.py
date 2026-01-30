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
from ...core.patcher import StuckDetector

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
        stuck_detector = StuckDetector()

        for section_idx, section_path in enumerate(state.completed_html_sections):
            section_name = Path(section_path).name
            print(f"\n  [VisualQA] 🔍 Processing: html/{section_name}")
            
            iteration = 0
            while True:
                iteration += 1
                print(f"\n    [Iteration {iteration}] Running Visual Critic...")
                
                # Step 1: Prepare preview and take screenshots
                preview_path = prepare_section_preview(
                    section_path,
                    state.workspace_path,
                    "" 
                )
                if not preview_path:
                    break
                
                screenshots = take_screenshots(
                    preview_path,
                    state.workspace_path,
                    headless=self.headless,
                    debug=self.debug
                )
                
                if preview_path.exists():
                    preview_path.unlink()
                
                if not screenshots:
                    break
                
                # Step 2: Critic reviews screenshots
                critique = run_critic(
                    self.client,
                    state,
                    screenshots,
                    debug=self.debug
                )
                
                if critique is None:
                    break
                
                if critique.get("verdict") == "PASS":
                    print(f"    [Critic] ✅ Section PASSED after {iteration} iteration(s).")
                    break
                
                issues = critique.get("issues", [])
                if not issues:
                    break
                
                # 🛠️ Backoff & Retry Logic
                current_content = Path(section_path).read_text(encoding="utf-8")
                combined_advice = "|".join([i.get("problem", "") for i in issues])
                
                if not stuck_detector.check_progress(combined_advice, current_content):
                    print(f"    [VisualQA] ⚠️ 检测到重复修复建议且内容未变化，触发 Backoff 策略...")
                    
                    retry_key = f"vqa_retry_{section_name}"
                    if state.loop_metadata.get(retry_key, False):
                        print(f"    [VisualQA] ❌ 第二次尝试仍卡住，停止该章节迭代。")
                        break
                    
                    state.loop_metadata[retry_key] = True
                    # 增强 Problem 描述
                    for issue in issues:
                        issue["problem"] = f"PREVIOUS ATTEMPT FAILED. Match block not found or ambiguous. YOU MUST include more context in your fix. {issue.get('problem', '')}"
                else:
                    state.loop_metadata[f"vqa_retry_{section_name}"] = False

                print(f"    [Critic] Found {len(issues)} issue(s):")
                
                # Visual Debugging
                issue_debug_paths = {}
                for issue in issues:
                    part_idx = issue.get("location_part", 1) - 1
                    issue_id = issue.get("id", "unknown")
                    if 0 <= part_idx < len(screenshots):
                        debug_path = debug_dir / f"debug_{section_name}_it{iteration}_{issue_id}.jpg"
                        draw_bounding_boxes(screenshots[part_idx], [issue], debug_path)
                        issue_debug_paths[issue_id] = debug_path
                
                # Step 3: Fixer addresses each issue
                fixes_applied = 0
                for issue in issues:
                    issue_id = issue.get("id", "unknown")
                    
                    fix_result = run_fixer(
                        self.client,
                        state,
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
                
                # NOTE: We DON'T break early here if fixes_applied == 0.
                # Let the next iteration detect the stuck state.
                
                if iteration >= 3: # Safety limit
                    break

            total_iterations += iteration

        if any_modified:
            state.vqa_needs_reassembly = True
        else:
            state.vqa_needs_reassembly = False
            
        state.vqa_iterations = total_iterations
        return state