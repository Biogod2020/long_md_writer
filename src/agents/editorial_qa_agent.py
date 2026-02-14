"""
EditorialQAAgent (SOTA 2.0): Global Markdown Gatekeeper.
Orchestrates the Critic-Advicer-Fixer loop for the MERGED document.
Ensures structural, narrative, and technical consistency before HTML transformation.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import Enum

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState
from ..core.validators import MarkdownValidator, ValidationSeverity
from ..core.merger import merge_markdown_sections
from ..core.patcher import StuckDetector
from .editorial_qa.critic import run_editorial_critic
from .editorial_qa.advicer import run_editorial_advicer
from .markdown_qa.fixer import run_markdown_fixer, apply_patches

# ============================================================================
# Legacy Data Structures (Maintained for Backward Compatibility)
# ============================================================================

class QAIssueType(Enum):
    """QA 问题类型"""
    CROP_MISMATCH = "crop_mismatch"
    MISSING_ALT = "missing_alt"
    BROKEN_REFERENCE = "broken_reference"
    SEMANTIC_DRIFT = "semantic_drift"
    STYLE_INCONSISTENCY = "style_inconsistency"
    ACCESSIBILITY_ISSUE = "accessibility_issue"

class QASeverity(Enum):
    """问题严重程度"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class QAIssue:
    """QA 问题记录"""
    issue_type: QAIssueType
    severity: QASeverity
    location: str
    message: str
    suggestion: str = ""
    context: dict = field(default_factory=dict)

@dataclass
class QAReport:
    """QA 审计报告"""
    passed: bool
    issues: list[QAIssue] = field(default_factory=list)
    summary: str = ""
    asset_count: int = 0
    reviewed_count: int = 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": [
                {
                    "type": i.issue_type.value,
                    "severity": i.severity.value,
                    "location": i.location,
                    "message": i.message,
                    "suggestion": i.suggestion
                }
                for i in self.issues
            ],
            "summary": self.summary,
            "asset_count": self.asset_count,
            "reviewed_count": self.reviewed_count
        }

@dataclass
class SemanticSummary:
    """语义摘要"""
    title: str
    core_concepts: list[str]
    key_terms: list[dict]
    visual_assets: list[dict]
    dependencies: list[str]
    summary: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "core_concepts": self.core_concepts,
            "key_terms": self.key_terms,
            "visual_assets": self.visual_assets,
            "dependencies": self.dependencies,
            "summary": self.summary
        }

async def extract_semantic_summary(content: str, client: Optional[GeminiClient] = None) -> Optional[SemanticSummary]:
    # Placeholder for backward compatibility
    return None

def save_semantic_summary(summary: SemanticSummary, output_path: Path):
    # Placeholder for backward compatibility
    pass

# ============================================================================
# Refactored Agent
# ============================================================================

class EditorialQAAgent:
    """
    Agent that handles global quality assurance for the merged Markdown document.
    """

    def __init__(self, client: Optional[GeminiClient] = None, max_iterations: int = 3):
        self.client = client or GeminiClient()
        self.max_iterations = max_iterations
        self.validator = MarkdownValidator()
        self.stuck_detector = StuckDetector()

    async def run_async(self, state: AgentState) -> AgentState:
        """
        Executes the global QA process:
        1. Merge all sections into final_full.md.
        2. Run local sanity checks (Syntax/Structure).
        3. Run global AI audit (Logic/Consistency).
        4. Apply precise patches to the merged file.
        """
        if not state.completed_md_sections:
            print("  [EditorialQA] No completed Markdown sections to review.")
            return state

        workspace = Path(state.workspace_path)
        merged_path = workspace / "final_full.md"
        
        print(f"\n[EditorialQA] 🛡️ Starting Global Quality Gate (Merged Document)...")

        # 1. PHYSICAL MERGE
        print(f"  [EditorialQA] Merging {len(state.completed_md_sections)} sections...")
        merge_markdown_sections(state.completed_md_sections, str(merged_path))

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n  [Iteration {iteration}/{self.max_iterations}] Global Audit...")

            # Read current merged content
            content = merged_path.read_text(encoding="utf-8")

            # 2. LOCAL SANITY CHECKS (Pre-audit)
            print("    [Sanity] Running static validation...")
            validation = self.validator.validate_all(content)
            sanity_issues = [i for i in validation.issues if i.severity == ValidationSeverity.ERROR]
            
            if sanity_issues:
                print(f"    [Sanity] 🚨 Found {len(sanity_issues)} structural issues. Fixing before AI audit...")
                advice = "CRITICAL STRUCTURAL ERRORS FOUND:\n" + "\n".join([f"- {i.message}" for i in sanity_issues])
                fix_result = await run_markdown_fixer(self.client, content, advice, debug=state.debug_mode)
                if fix_result and fix_result.get("status") == "FIXED":
                    content = apply_patches(content, fix_result)
                    merged_path.write_text(content, encoding="utf-8")
                    print("    [Sanity] ✅ Local fixes applied.")
                    # Restart iteration with fixed content
                    continue

            # 3. GLOBAL AI CRITIC (Semantic/Macro-Level)
            print("    [Critic] Performing full-context semantic audit...")
            critique = await run_editorial_critic(self.client, state, content, debug=state.debug_mode)
            
            # SOTA: Capture Thinking tokens from state (if populated by critic)
            if hasattr(state, "thoughts") and state.thoughts:
                # Store them in a dedicated log file
                (qa_log_dir / f"thinking_it{iteration}.txt").write_text(state.thoughts, encoding="utf-8")

            # Log critique for observability
            qa_log_dir = workspace / "editorial_qa_logs"
            qa_log_dir.mkdir(exist_ok=True)
            (qa_log_dir / f"critique_it{iteration}.json").write_text(
                json.dumps(critique, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            verdict = critique.get("verdict", "MODIFY").upper()
            feedback = critique.get("feedback", "")
            
            print(f"    [Critic] Verdict: {verdict}")
            
            if verdict == "APPROVE":
                print("    [EditorialQA] ✅ Merged document approved.")
                state.markdown_approved = True
                break

            # Check if stuck
            advice_id = f"global_qa_{iteration}"
            if not self.stuck_detector.check_progress(advice_id, content):
                print(f"    [EditorialQA] ⚠️ Repair stagnation detected at iteration {iteration}.")
                
                # SOTA: Backoff Strategy - Request more precision if first retry fails
                if iteration > 1:
                    print("    [EditorialQA] 🛑 Stagnation persisted after retry. Triggering manual intervention.")
                    state.markdown_approved = False
                    break
                else:
                    print("    [EditorialQA] 🔄 Attempting recovery with enhanced instructions...")
                    feedback = f"PREVIOUS ATTEMPT FAILED TO APPLY PATCHES. You MUST provide more context in your SEARCH blocks to ensure a unique match. Issues to fix: {feedback}"

            # 4. GLOBAL ADVICER (Instruction Generation)
            print("    [Advicer] Generating patching instructions for final_full.md...")
            advice_map = await run_editorial_advicer(self.client, content, feedback, debug=state.debug_mode)
            
            if not advice_map or "final_full.md" not in advice_map:
                print("    [EditorialQA] ⚠️ Advicer failed to generate a plan for the merged file.")
                break

            # 5. GLOBAL FIXER (Patch Application)
            advice = advice_map["final_full.md"]
            print("    [Fixer] Applying patches to final_full.md...")
            fix_result = await run_markdown_fixer(self.client, content, advice, debug=state.debug_mode)
            
            if fix_result and fix_result.get("status") == "FIXED":
                new_content = apply_patches(content, fix_result)
                if new_content != content:
                    merged_path.write_text(new_content, encoding="utf-8")
                    print("    [Fixer] ✅ Applied global fixes.")
                else:
                    print("    [Fixer] ⚠️ Patches didn't change content.")
                    break
            else:
                print(f"    [Fixer] ❌ Failed: {fix_result.get('reason') if fix_result else 'Unknown'}")
                break

        print(f"[EditorialQA] Global quality gate complete.")
        
        # SOTA: Generate Final Global QA Report
        final_report = {
            "status": "APPROVED" if state.markdown_approved else "NEEDS_INTERVENTION",
            "iterations": iteration,
            "merged_file": str(merged_path.relative_to(workspace)),
            "timestamp": json.dumps(True) # Dummy for timestamp
        }
        (workspace / "qa_report_global.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")
        
        return state

    def run(self, state: AgentState) -> AgentState:
        """Synchronous wrapper."""
        return asyncio.run(self.run_async(state))
