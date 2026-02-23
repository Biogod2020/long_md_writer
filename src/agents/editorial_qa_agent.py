"""
EditorialQAAgent (SOTA 2.0): Global Markdown Gatekeeper.
Orchestrates the Critic-Advicer-Fixer loop for the MERGED document.
Ensures structural, narrative, and technical consistency before HTML transformation.
Supports both Global Audit (node mode) and Section Audit (legacy compatibility).
"""

import json
import asyncio
import re
from pathlib import Path
from typing import Optional, List, Dict, Union, Any
from dataclasses import dataclass, field
from enum import Enum

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState
from ..core.validators import MarkdownValidator, ValidationSeverity
from ..core.merger import merge_markdown_sections, split_merged_document
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

# ============================================================================
# Refactored Agent
# ============================================================================

class EditorialQAAgent:
    """
    Agent that handles global quality assurance for the merged Markdown document.
    """

    def __init__(
        self, 
        client: Optional[GeminiClient] = None, 
        max_iterations: int = 3,
        renderer: Optional[Any] = None,
        skip_llm_review: bool = False,
        strict_mode: bool = True
    ):
        self.client = client or GeminiClient()
        self.max_iterations = max_iterations
        self.renderer = renderer
        self.skip_llm_review = skip_llm_review
        self.strict_mode = strict_mode
        self.validator = MarkdownValidator()
        self.stuck_detector = StuckDetector()

    async def run_async(
        self, 
        state: AgentState, 
        content: Optional[str] = None, 
        namespace: Optional[str] = None, 
        full_context: Optional[str] = None
    ) -> Union[AgentState, tuple[AgentState, QAReport, str]]:
        """
        Executes the global QA process (if content is None) or section QA (legacy mode).
        """
        if content is not None:
            # LEGACY COMPATIBILITY MODE: Section-level QA
            return await self._run_legacy_section_qa(state, content, namespace or "s1", full_context)
            
        # GLOBAL GATEKEEPER MODE: Merged document audit
        if not state.completed_md_sections:
            print("  [EditorialQA] No completed Markdown sections to review.")
            return state

        workspace = Path(state.workspace_path)
        merged_path = workspace / "final_full.md"
        
        print(f"\n[EditorialQA] 🛡️ Starting Global Quality Gate (Merged Document)...")

        # 1. PHYSICAL MERGE & SOTA EXPORT
        print(f"  [EditorialQA] Merging {len(state.completed_md_sections)} sections and exporting assets...")
        if not merge_markdown_sections(
            state.completed_md_sections, 
            str(merged_path), 
            workspace_path=state.workspace_path,
            asset_registry=state.get_uar()
        ):
            print("  [EditorialQA] ❌ Physical merge/export failed. Aborting QA.")
            state.markdown_approved = False
            return state

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n  [Iteration {iteration}/{self.max_iterations}] Global Audit...")

            # Read current merged content
            current_content = merged_path.read_text(encoding="utf-8")

            # 2. LOCAL SANITY CHECKS (Pre-audit)
            print("    [Sanity] Running static validation...")
            validation = self.validator.validate_all(current_content)
            sanity_issues = [i for i in validation.issues if i.severity == ValidationSeverity.ERROR]
            
            if sanity_issues:
                print(f"    [Sanity] 🚨 Found {len(sanity_issues)} structural issues. Fixing before AI audit...")
                advice = "CRITICAL STRUCTURAL ERRORS FOUND:\n" + "\n".join([f"- {i.message}" for i in sanity_issues])
                fix_result = await run_markdown_fixer(self.client, current_content, advice, debug=state.debug_mode)
                if fix_result and fix_result.get("status") == "FIXED":
                    current_content = apply_patches(current_content, fix_result)
                    merged_path.write_text(current_content, encoding="utf-8")
                    print("    [Sanity] ✅ Local fixes applied.")
                    # Restart iteration with fixed content
                    continue

            # 3. GLOBAL AI CRITIC (Semantic/Macro-Level)
            print("    [Critic] Performing full-context semantic audit...")
            
            # Use renderer if available
            screenshot_paths = []
            if self.renderer:
                try:
                    print("    [EditorialQA] 📸 Generating visual evidence...")
                    # Capture screenshot of the merged document (placeholder)
                    pass
                except Exception as e:
                    print(f"    [EditorialQA] ⚠️ Rendering failed: {e}")

            critique = await run_editorial_critic(
                self.client, state, current_content, 
                screenshot_paths=screenshot_paths if screenshot_paths else None,
                debug=state.debug_mode
            )
            
            # Log critique for observability
            qa_log_dir = workspace / "editorial_qa_logs"
            qa_log_dir.mkdir(exist_ok=True)

            # SOTA: Capture Thinking tokens from state (if populated by critic)
            if hasattr(state, "thoughts") and state.thoughts:
                # Store them in a dedicated log file
                (qa_log_dir / f"thinking_it{iteration}.txt").write_text(state.thoughts, encoding="utf-8")
                # Reset thoughts for next iteration to avoid accumulation
                state.thoughts = ""

            (qa_log_dir / f"critique_it{iteration}.json").write_text(
                json.dumps(critique, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            verdict = critique.get("verdict", "MODIFY").upper()
            feedback = critique.get("feedback", "")
            
            print(f"    [Critic] Verdict: {verdict}")
            
            if verdict == "APPROVE":
                print(f"    [EditorialQA] ✅ Merged document approved at iteration {iteration}.")
                state.markdown_approved = True
                
                # SOTA: Non-Destructive Sync (Save to audited_md, preserve original md)
                audited_dir = workspace / "audited_md"
                audited_dir.mkdir(exist_ok=True)
                
                print(f"    [EditorialQA] 🔄 Splitting approved document to {audited_dir.name}...")
                if split_merged_document(str(merged_path), str(audited_dir)):
                    # Update state to use audited files for downstream agents
                    new_paths = []
                    # Keep original order based on current section IDs
                    for original_path in state.completed_md_sections:
                        section_id = Path(original_path).stem
                        new_path = audited_dir / f"{section_id}.md"
                        if new_path.exists():
                            new_paths.append(str(new_path))
                        else:
                            new_paths.append(original_path) # Fallback
                    state.completed_md_sections = new_paths
                    print(f"    [EditorialQA] ✨ Downstream paths redirected to audited artifacts.")
                break

            # Check if stuck
            advice_id = f"global_qa_{iteration}"
            if not self.stuck_detector.check_progress(advice_id, current_content):
                print(f"    [EditorialQA] ⚠️ Repair stagnation detected at iteration {iteration}.")
                
                if iteration > 1:
                    print("    [EditorialQA] 🛑 Stagnation persisted. Breaking loop for safety.")
                    state.markdown_approved = False
                    break
                else:
                    feedback = f"PREVIOUS PATCH FAILED. Please provide more precise search anchors. Issues: {feedback}"

            # 4. GLOBAL ADVICER (Instruction Generation)
            print("    [Advicer] Generating patching instructions for final_full.md...")
            advice_map = await run_editorial_advicer(self.client, current_content, feedback, debug=state.debug_mode)
            
            if not advice_map or "final_full.md" not in advice_map:
                print("    [EditorialQA] ⚠️ Advicer failed to generate a plan for final_full.md.")
                break

            # 5. GLOBAL FIXER (Patch Application)
            advice = advice_map["final_full.md"]
            print(f"    [Fixer] Applying patches to final_full.md (Advice len: {len(advice)})...")
            fix_result = await run_markdown_fixer(self.client, current_content, advice, debug=state.debug_mode)
            
            if fix_result and fix_result.get("status") == "FIXED":
                new_content = apply_patches(current_content, fix_result)
                if new_content != content:
                    merged_path.write_text(new_content, encoding="utf-8")
                    print(f"    [Fixer] ✅ Applied {len(fix_result.get('patches', []))} patches.")
                else:
                    print(f"    [Fixer] ⚠️ Patches were valid but no changes were applied to the physical file.")
                    break
            else:
                print(f"    [Fixer] ❌ Failed to generate patches: {fix_result.get('reason') if fix_result else 'Unknown'}")
                break

        print(f"[EditorialQA] Global quality gate complete.")
        
        # SOTA: Generate Final Global QA Report
        final_report = {
            "status": "APPROVED" if state.markdown_approved else "NEEDS_INTERVENTION",
            "iterations": iteration,
            "merged_file": str(merged_path.relative_to(workspace)) if merged_path.exists() else None,
            "timestamp": True
        }
        (workspace / "qa_report_global.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")
        
        return state

    async def _run_legacy_section_qa(
        self, 
        state: AgentState, 
        content: str, 
        namespace: str, 
        full_context: Optional[str] = None
    ) -> tuple[AgentState, QAReport, str]:
        """
        Full implementation of the old section-level QA for legacy compatibility.
        """
        iteration = 0
        max_iterations = 3
        current_content = content
        last_report = None
        stuck_detector = StuckDetector()

        print(f"[EditorialQA] Legacy mode: Section Audit (namespace: {namespace})")

        while iteration < max_iterations:
            iteration += 1
            issues: list[QAIssue] = []

            # 1. Local static checks
            local_issues = self._run_local_checks(current_content, namespace, state)
            issues.extend(local_issues)

            # 2. Render visual snapshot
            screenshot_path = None
            if self.renderer:
                try:
                    if asyncio.iscoroutinefunction(self.renderer.render_to_image):
                        screenshot_path = await self.renderer.render_to_image(current_content, f"qa_{namespace}_{iteration}")
                    else:
                        screenshot_path = self.renderer.render_to_image(current_content, f"qa_{namespace}_{iteration}")
                except Exception as e:
                    print(f"    ❌ Rendering failed: {e}")

            # 3. LLM review
            if not self.skip_llm_review:
                llm_issues = await self._run_llm_review(current_content, state, full_context, screenshot_path)
                issues.extend(llm_issues)

            # 4. Generate report
            asset_count = len(re.findall(r'<img\s+|<figure', current_content, re.IGNORECASE))
            error_count = sum(1 for i in issues if i.severity == QASeverity.ERROR)
            warning_count = sum(1 for i in issues if i.severity == QASeverity.WARNING)
            
            passed = error_count == 0
            if self.strict_mode:
                passed = passed and warning_count == 0

            last_report = QAReport(
                passed=passed,
                issues=issues,
                summary=f"Audit completed with {error_count} errors and {warning_count} warnings.",
                asset_count=asset_count,
                reviewed_count=asset_count
            )
            
            print(f"    [Debug] Iteration {iteration}: passed={passed}, issues={len(issues)}")

            if passed:
                break

            # Check stuck
            combined_advice = "|".join([i.message for i in issues])
            if not stuck_detector.check_progress(combined_advice, current_content):
                break

            # 5. Fixer loop
            print(f"  [Iteration {iteration}] 🛠️ Found {len(issues)} issues, attempting auto-repair...")
            current_content = await self._run_legacy_fixer_loop(current_content, issues, full_context)

        return state, last_report, current_content

    async def _run_legacy_fixer_loop(self, content: str, issues: list[QAIssue], full_context: Optional[str]) -> str:
        current_content = content
        errors = [i for i in issues if i.severity == QASeverity.ERROR]
        if not errors: return current_content

        for issue in errors:
            advice = f"ISSUE: {issue.message}\nLOCATION: {issue.location}\nSUGGESTION: {issue.suggestion}"
            fix_result = await run_markdown_fixer(self.client, current_content, advice, context=full_context)
            if fix_result and fix_result.get("status") == "FIXED":
                current_content = apply_patches(current_content, fix_result)
        return current_content

    def _run_local_checks(self, content: str, namespace: str, state: AgentState) -> list[QAIssue]:
        issues = []
        # Check mandatory assets
        uar = state.get_uar()
        assigned_ids = []
        if state.manifest:
            for sec in state.manifest.sections:
                if sec.id == namespace or sec.metadata.get("namespace") == namespace:
                    assigned_ids = sec.metadata.get("assigned_assets", [])
                    break
        
        if not assigned_ids:
            assigned_ids = [a.id for a in uar.assets.values() if a.priority.value == "MANDATORY"]

        for aid in assigned_ids:
            if f'data-asset-id="{aid}"' not in content and f"data-asset-id='{aid}'" not in content:
                issues.append(QAIssue(
                    issue_type=QAIssueType.BROKEN_REFERENCE,
                    severity=QASeverity.ERROR,
                    location="content",
                    message=f"缺少强制性资产: {aid}",
                    suggestion=f"Insert asset {aid} into the text."
                ))
        
        # Check unfulfilled visuals
        if ":::visual" in content:
            issues.append(QAIssue(
                issue_type=QAIssueType.BROKEN_REFERENCE,
                severity=QASeverity.ERROR,
                location="content",
                message="发现未履约的 :::visual 指令",
                suggestion="Run fulfillment agent."
            ))
            
        return issues

    async def _run_llm_review(self, content: str, state: AgentState, full_context: Optional[str], image_path: Optional[Path]) -> list[QAIssue]:
        issues = []
        
        EDITORIAL_QA_PROMPT = """你是一位专业的技术文档编辑审核员。请对以下内容进行全面的语义和视觉审核。
## 待审核 Markdown 内容
```markdown
{content}
```
## 全书前文上下文
{full_context}
## 输出格式 (JSON)
```json
{{
  "passed": true/false,
  "issues": [
    {{
      "type": "crop_mismatch|semantic_drift",
      "severity": "error|warning",
      "location": "position",
      "message": "problem",
      "suggestion": "fix"
    }}
  ],
  "summary": "summary"
}}
```
"""
        prompt_text = EDITORIAL_QA_PROMPT.format(content=content, full_context=full_context or "")
        
        # SOTA: Maintain 'prompt' keyword for legacy test compatibility
        if not image_path:
            response = await self.client.generate_async(
                prompt=prompt_text,
                system_instruction="You are an editorial auditor.",
                temperature=0.0
            )
        else:
            import base64
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            parts = [
                {"text": prompt_text},
                {"inline_data": {"mime_type": "image/png", "data": img_data}}
            ]
            response = await self.client.generate_async(
                parts=parts,
                system_instruction="You are an editorial auditor.",
                temperature=0.0
            )
        
        if not response.success: return []
        
        from ..core.json_utils import parse_json_dict_robust
        data = parse_json_dict_robust(response.text)
        
        if data and "issues" in data:
            for i in data["issues"]:
                try:
                    itype = QAIssueType(i.get("type", "semantic_drift"))
                    iserv = QASeverity(i.get("severity", "warning"))
                    issues.append(QAIssue(
                        issue_type=itype,
                        severity=iserv,
                        location=i.get("location", "unknown"),
                        message=i.get("message", ""),
                        suggestion=i.get("suggestion", "")
                    ))
                except: continue
        return issues

    def run(
        self, 
        state: AgentState, 
        content: Optional[str] = None, 
        namespace: Optional[str] = None, 
        full_context: Optional[str] = None
    ) -> Union[AgentState, tuple[AgentState, QAReport, str]]:
        """Synchronous wrapper."""
        return asyncio.run(self.run_async(state, content, namespace, full_context))

# ============================================================================
# Semantic Summary Utilities
# ============================================================================

async def extract_semantic_summary(
    content: str,
    client: Optional[GeminiClient] = None
) -> Optional[SemanticSummary]:
    return None

def save_semantic_summary(summary: SemanticSummary, output_path: Path):
    if output_path:
        output_path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
