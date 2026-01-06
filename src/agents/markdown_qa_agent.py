"""
MarkdownQAAgent: Orchestrates the Critic-Advicer-Fixer loop for Markdown content.
Redesigned to handle large documents and robust feedback loops.
"""

from pathlib import Path
from typing import Optional, List, Dict
import json
import re

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.agents.markdown_qa.critic import run_markdown_critic
from src.agents.markdown_qa.advicer import run_markdown_advicer
from src.agents.markdown_qa.fixer import run_markdown_fixer, apply_patches

class MarkdownQAAgent:
    """
    Agent that handles Markdown quality assurance.
    Workflow:
    1. Critic reviews full content -> VERDICT
    2. If APPROVE -> Finish
    3. If REWRITE -> Flag for rewrite (WriterAgent)
    4. If MODIFY -> Advicer generates specific plan -> Fixer applies patches
    """

    def __init__(self, client: Optional[GeminiClient] = None, max_iterations: int = 3):
        self.client = client or GeminiClient()
        self.max_iterations = max_iterations

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
        verdict = critique.get("verdict", "MODIFY") # Default to modify if undefined
        feedback = critique.get("feedback", "")
        
        print(f"  [MarkdownQA] Verdict: {verdict}")
        
        if verdict == "APPROVE":
            print("  [MarkdownQA] ✅ Content Approved.")
            state.md_qa_needs_revision = False
            state.markdown_approved = True
            return state
            
        elif verdict == "REWRITE":
            print("  [MarkdownQA] 🔄 Triggering Rewrite Loop...")
            print(f"  [MarkdownQA] Feedback: {feedback[:200]}...")
            state.rewrite_needed = True # Flag for edges.py
            state.rewrite_feedback = feedback
            # We do NOT increment iterations heavily here, as Writer will handle it.
            # But the edge will route us away.
            return state
            
        elif verdict == "MODIFY":
            print("  [MarkdownQA] 🛠️ Proceeding to Modification Phase...")
            
            # 4. ADVICER Phase
            file_list = [Path(p).name for p in state.completed_md_sections]
            advice_map = await run_markdown_advicer(
                self.client, 
                merged_content, 
                file_list, 
                feedback, 
                debug=state.debug_mode
            )
            
            if not advice_map:
                print("  [MarkdownQA] Advicer suggested no changes.")
                state.md_qa_needs_revision = False
                return state
                
            print(f"  [MarkdownQA] Advicer produced plan for {len(advice_map)} files.")
            
            # 5. FIXER Phase (Parallel with max 4 concurrent tasks)
            import asyncio
            
            semaphore = asyncio.Semaphore(4)
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
                        Path(res["target_path"]).write_text(new_content, encoding="utf-8")
                        fixes_applied += 1
                        print(f"      ✅ Applied fixes to {res['filename']}")
                    else:
                        print(f"      ⚠️ Patches didn't change content for {res['filename']}")
                else:
                    reason = fix_result.get('reason') if fix_result else "No result"
                    print(f"      ❌ Fixer failed for {res['filename']}: {reason}")
            
            if fixes_applied > 0:
                 state.md_qa_needs_revision = True # Loop back to Critic
            else:
                 print("  [MarkdownQA] No fixes applied effectively.")
                 state.md_qa_needs_revision = False # Stop if we can't fix it
                 
            return state

        else:
            print(f"  [MarkdownQA] Unknown verdict {verdict}.")
            state.md_qa_needs_revision = False
            return state

    def _merge_content(self, state: AgentState) -> str:
        """Helper to merge content for the prompt"""
        merged = []
        for path in state.completed_md_sections:
            p = Path(path)
            merged.append(f"## File: {p.name}\n\n{p.read_text()}")
        return "\n\n".join(merged)
