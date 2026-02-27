"""
MarkdownQAAgent: Orchestrates the Critic-Advicer-Fixer loop for Markdown content.
Redesigned to handle large documents and robust feedback loops.
"""

from pathlib import Path
from typing import Optional

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.core.validators import MarkdownValidator
from src.agents.markdown_qa.critic import run_markdown_critic
from src.agents.markdown_qa.advicer import run_markdown_advicer
from src.agents.markdown_qa.fixer import run_markdown_fixer, apply_patches

class MarkdownQAAgent:
    """
    Agent that handles Markdown quality assurance.
    Workflow:
    1. Critic reviews full content -> VERDICT
    2. If APPROVE -> Finish
    3. If REWRITE -> Try Patching first, fallback to Writer rewrite only if fundamental failure
    4. If MODIFY -> Advicer generates specific plan -> Fixer applies patches
    """

    def __init__(self, client: Optional[GeminiClient] = None, max_iterations: int = 3):
        self.client = client or GeminiClient()
        self.max_iterations = max_iterations
        self.validator = MarkdownValidator()

    async def run(self, state: AgentState) -> AgentState:
        if not state.completed_md_sections:
            print("  [MarkdownQA] No Markdown sections to review.")
            return state

        # 1. Check for Max Iterations
        iteration = getattr(state, "md_qa_iterations", 0)
        if iteration >= self.max_iterations:
            print(f"  [MarkdownQA] Reached max AI iterations ({self.max_iterations}).")
            state.md_qa_needs_revision = False
            return state

        state.md_qa_iterations = iteration + 1
        print(f"\n  [MarkdownQA] Iteration {state.md_qa_iterations}: AI Self-Review...")

        # 2. Merge Content for Context
        merged_content = self._merge_content(state)
        
        # 3. CRITIC Phase
        critique = await run_markdown_critic(self.client, state, merged_content, debug=state.debug_mode)
        
        # SOTA: 将审计报告保存至物理文件，增加透明度
        qa_log_dir = Path(state.workspace_path) / "qa_logs"
        qa_log_dir.mkdir(exist_ok=True)
        import json
        (qa_log_dir / f"critique_it{state.md_qa_iterations}.json").write_text(
            json.dumps(critique, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        verdict = critique.get("verdict", "MODIFY") # Default to modify if undefined
        feedback = critique.get("feedback", "")
        
        print(f"  [MarkdownQA] Verdict: {verdict}")
        
        if verdict == "APPROVE":
            print("  [MarkdownQA] ✅ Content Approved.")
            state.md_qa_needs_revision = False
            state.markdown_approved = True
            return state
            
        # SOTA: Patch-First Strategy
        # Even if Critic asks for REWRITE, we try to fix it via patches first
        if verdict == "REWRITE" and state.md_qa_iterations > 2:
            print("  [MarkdownQA] 🔄 Patching failed to resolve fundamental issues. Triggering Writer Rewrite...")
            state.rewrite_needed = True
            state.rewrite_feedback = feedback
            return state
            
        print("  [MarkdownQA] 🛠️ Proceeding to Modification (Patching) Phase...")
        
        # 4. ADVICER Phase
        # SOTA FIX: Extract section-specific feedback
        section_feedback = critique.get("section_feedback", {})
        
        # Determine which files to fix: prioritize those with explicit feedback
        if section_feedback:
            # ONLY audit files that the critic explicitly identified
            file_list = list(section_feedback.keys())
            print(f"  [MarkdownQA] Critic identified {len(file_list)} files for modification: {file_list}")
        else:
            # Fallback: all files (legacy behavior)
            file_list = [Path(p).name for p in state.completed_md_sections]
            
        advice_map = await run_markdown_advicer(
            self.client, 
            merged_content, 
            file_list, 
            feedback, 
            section_feedback=section_feedback,
            debug=state.debug_mode
        )
        
        # SOTA Logic Fix: Check for API errors vs real "No changes needed"
        # run_markdown_advicer returns None on API error, {} on "no changes needed"
        if advice_map is None:
            print("  [MarkdownQA] ❌ Advicer failed due to technical error (API Crash).")
            state.errors.append(f"MarkdownQA: Advicer API crashed for {file_list}")
            state.md_qa_needs_revision = False # Exit loop to prevent stuck, but DON'T approve
            state.markdown_approved = False
            return state

        if not advice_map:
            print("  [MarkdownQA] Advicer suggested no changes.")
            # If critic wanted a fix but advicer couldn't find one, we should NOT approve.
            # We let the human decide or retry in next iteration.
            state.md_qa_needs_revision = False
            state.markdown_approved = False
            return state
            
        print(f"  [MarkdownQA] Advicer produced plan for {len(advice_map)} files.")
        
        # 5. FIXER Phase (Parallel with max 3 concurrent tasks for stability)
        import asyncio
        
        semaphore = asyncio.Semaphore(3)
        fixes_applied = 0
        fix_results = []
        
        async def fix_single_file(filename: str, advice: str):
            """Fix a single file with semaphore-controlled concurrency."""
            async with semaphore:
                target_path = next((p for p in state.completed_md_sections if Path(p).name == filename), None)
                if not target_path:
                    print(f"  [MarkdownQA] ⚠️ Could not find path for {filename}")
                    return None
                
                print(f"    [MarkdownQA] Fixing {filename}...")
                current_content = Path(target_path).read_text(encoding="utf-8")
                
                fix_result = await run_markdown_fixer(
                    self.client, 
                    current_content, 
                    advice, 
                    context=merged_content,
                    debug=state.debug_mode
                )
                
                return {
                    "filename": filename,
                    "target_path": target_path,
                    "current_content": current_content,
                    "fix_result": fix_result
                }
        
        # Launch all tasks in parallel (limited by semaphore)
        tasks = [fix_single_file(fn, adv) for fn, adv in advice_map.items()]
        fix_results = await asyncio.gather(*tasks)
        
        # Apply patches from results
        for res in fix_results:
            if res is None:
                continue
                
            fix_result = res["fix_result"]
            if fix_result and fix_result.get("status") == "FIXED":
                new_content = apply_patches(res["current_content"], fix_result)
                
                if new_content != res["current_content"]:
                    # SOTA: 执行校验仅用于日志 and 审计，不再阻断写入
                    validation = self.validator.validate_all(new_content)
                    
                    # 无论校验是否通过，都物理写入文件 (信任 AI 的渐进式改进)
                    Path(res["target_path"]).write_text(new_content, encoding="utf-8")
                    fixes_applied += 1
                    
                    if validation.is_valid:
                        print(f"      ✅ Applied fixes to {res['filename']}")
                    else:
                        print(f"      ⚠️ Applied fixes to {res['filename']} with remaining issues:")
                        for issue in validation.issues:
                            print(f"         - [{issue.severity}] {issue.message}")
                else:
                    print(f"      ⚠️ Patches didn't change content for {res['filename']}")
            else:
                reason = fix_result.get('reason') if fix_result else "No result"
                print(f"      ❌ Fixer failed for {res['filename']}: {reason}")
        
        if fixes_applied > 0:
             print(f"  [MarkdownQA] ✅ Applied {fixes_applied} patches. Requesting AI re-audit...")
             state.md_qa_needs_revision = True # Loop back to Critic
             state.markdown_approved = False   # Reset approval status
        else:
             print("  [MarkdownQA] No fixes applied effectively.")
             state.md_qa_needs_revision = False # Stop if we can't fix it
             
        return state

    def _merge_content(self, state: AgentState) -> str:
        """Helper to merge content for the prompt using standard SOTA markers"""
        merged = []
        for path in state.completed_md_sections:
            p = Path(path)
            # Use standard SOTA markers expected by the Critic prompt
            merged.append(f"<!-- [SOURCE:md/{p.name}] -->\n{p.read_text(encoding='utf-8')}\n<!-- [/SOURCE:md/{p.name}] -->")
        return "\n\n".join(merged)
