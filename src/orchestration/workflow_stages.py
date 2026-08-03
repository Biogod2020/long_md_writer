"""Coarse publication stages for the deterministic workflow control plane."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import json
import shutil

from .models import CodexTaskSpec, PublicationPlan, QualityReport, STAGE_ORDER, StageName, StageStatus, WorkflowMode
from .prompts import assets_prompt, draft_prompt, plan_prompt, publish_prompt, qa_audit_prompt, qa_repair_prompt, qa_verify_prompt
from .quality import assets_report, compare_baseline, draft_report, publish_report, qa_report, quality_report_for_stage
from .state_store import StateStore
from .workflow_base import StageFailed, copy_file, replace_tree


class PublicationStagesMixin:
    async def _run_stages(self) -> None:
        for stage in STAGE_ORDER:
            self.state.current_stage = stage; self.store.save(self.state)
            if self.stage_reusable(stage):
                self.store.append_event("stage_reused", stage=stage.value); continue
            self._invalidate_from(stage, remove_artifacts=False)
            if stage == StageName.PLAN:
                report = await self.run_simple_stage(stage, plan_prompt); await self.approval("plan", report)
            elif stage == StageName.DRAFT: await self.run_draft_stage()
            elif stage == StageName.ASSETS: await self.run_simple_stage(stage, assets_prompt)
            elif stage == StageName.PUBLISH: await self.run_simple_stage(stage, publish_prompt)
            elif stage == StageName.QA:
                report = await self.run_qa_stage(); await self.approval("final", report)

    async def run_simple_stage(
        self,
        stage: StageName,
        prompt_builder: Callable[[WorkflowMode, QualityReport | None], str],
    ) -> QualityReport:
        previous: QualityReport | None = None
        for attempt in range(1, self.request.max_stage_attempts + 1):
            record = self.state.record(stage); record.status = StageStatus.RUNNING; record.attempts = attempt
            record.started_at = datetime.now(timezone.utc); self.store.save(self.state)
            staging = self.prepare(stage, attempt, "task")
            allowed = {
                StageName.PLAN: ["project_brief.md", "plan.json"],
                StageName.ASSETS: ["md/**", "assets/**"],
                StageName.PUBLISH: ["final.md"] + (["final.html"] if self.request.mode == WorkflowMode.HTML else []),
            }[stage]
            required = {
                StageName.PLAN: ["project_brief.md", "plan.json"],
                StageName.ASSETS: ["assets/asset-manifest.json"],
                StageName.PUBLISH: ["final.md"] + (["final.html"] if self.request.mode == WorkflowMode.HTML else []),
            }[stage]
            task = CodexTaskSpec(
                task_id=f"{stage.value}-{attempt}", stage=stage, workspace=staging,
                prompt=prompt_builder(self.request.mode, previous), allowed_paths=allowed,
                required_outputs=required,
                allow_network=self.request.allow_network if stage == StageName.ASSETS else False,
                reasoning_effort="high",
            )
            result, audit = await self.execute_task(task, attempt)
            report = quality_report_for_stage(staging, stage, self.request.mode)
            if result.status == "completed" and audit.passed and report.passed:
                if stage == StageName.PLAN:
                    copy_file(staging / "project_brief.md", self.workspace / "project_brief.md")
                    copy_file(staging / "plan.json", self.workspace / "plan.json")
                elif stage == StageName.ASSETS:
                    replace_tree(staging / "md", self.workspace / "md")
                    replace_tree(staging / "assets", self.workspace / "assets")
                elif stage == StageName.PUBLISH:
                    copy_file(staging / "final.md", self.workspace / "final.md")
                    if self.request.mode == WorkflowMode.HTML:
                        copy_file(staging / "final.html", self.workspace / "final.html")
                canonical = quality_report_for_stage(self.workspace, stage, self.request.mode)
                self.mark_passed(stage, attempt, canonical); return canonical
            previous = report; self.save_report(report, attempt)
        record = self.state.record(stage); record.status = StageStatus.FAILED
        record.error = previous.feedback_text() if previous else "stage failed"; self.store.save(self.state)
        raise StageFailed(stage, previous or quality_report_for_stage(self.workspace, stage, self.request.mode))

    async def run_draft_stage(self) -> QualityReport:
        plan = PublicationPlan.model_validate_json((self.workspace / "plan.json").read_text(encoding="utf-8"))
        semaphore = asyncio.Semaphore(self.request.draft_concurrency)
        last_report: QualityReport | None = None
        for attempt in range(1, self.request.max_stage_attempts + 1):
            record = self.state.record(StageName.DRAFT); record.status = StageStatus.RUNNING; record.attempts = attempt
            self.store.save(self.state)

            async def write(section):
                async with semaphore:
                    staging = self.prepare(StageName.DRAFT, attempt, section.id)
                    relative = f"drafts/{section.id}.md"
                    task = CodexTaskSpec(
                        task_id=f"draft-{section.id}-{attempt}", stage=StageName.DRAFT,
                        workspace=staging, prompt=draft_prompt(section, self.request.mode),
                        allowed_paths=[relative], required_outputs=[relative], reasoning_effort="high",
                    )
                    result, audit = await self.execute_task(task, attempt)
                    return section.id, staging, result, audit, draft_report(staging, section_id=section.id)

            outcomes = await asyncio.gather(*(write(section) for section in plan.sections))
            if all(result.status == "completed" and audit.passed and report.passed for _, _, result, audit, report in outcomes):
                incoming = self.task_root / "draft-collection"
                shutil.rmtree(incoming, ignore_errors=True); incoming.mkdir(parents=True)
                for section_id, staging, *_ in outcomes:
                    copy_file(staging / "drafts" / f"{section_id}.md", incoming / f"{section_id}.md")
                replace_tree(incoming, self.workspace / "drafts")
                canonical = draft_report(self.workspace)
                if canonical.passed:
                    self.mark_passed(StageName.DRAFT, attempt, canonical); return canonical
            last_report = draft_report(self.workspace); self.save_report(last_report, attempt)
        raise StageFailed(StageName.DRAFT, last_report or draft_report(self.workspace))

    async def run_qa_stage(self) -> QualityReport:
        previous: QualityReport | None = None
        for attempt in range(1, self.request.max_stage_attempts + 1):
            record = self.state.record(StageName.QA); record.status = StageStatus.RUNNING; record.attempts = attempt
            self.store.save(self.state)
            staging = self.prepare(StageName.QA, attempt, "qa")
            audit_task = CodexTaskSpec(
                task_id=f"qa-audit-{attempt}", stage=StageName.QA, workspace=staging,
                prompt=qa_audit_prompt(self.request.mode, previous),
                allowed_paths=["qa/audit-findings.json"], required_outputs=["qa/audit-findings.json"],
                persist_session=False, reasoning_effort="xhigh",
            )
            audit_result, audit_fs = await self.execute_task(audit_task, attempt)
            audit_data = {}
            try: audit_data = json.loads((staging / "qa" / "audit-findings.json").read_text(encoding="utf-8"))
            except Exception: pass
            needs_repair = (
                bool(audit_data.get("critical_issues"))
                or not assets_report(staging, self.request.mode).passed
                or not publish_report(staging, self.request.mode).passed
            )
            if audit_result.status == "completed" and audit_fs.passed and needs_repair:
                repair_task = CodexTaskSpec(
                    task_id=f"qa-repair-{attempt}", stage=StageName.QA, workspace=staging,
                    prompt=qa_repair_prompt(self.request.mode, previous),
                    allowed_paths=["md/**", "assets/**", "final.md"] + (["final.html"] if self.request.mode == WorkflowMode.HTML else []),
                    required_outputs=["final.md"] + (["final.html"] if self.request.mode == WorkflowMode.HTML else []),
                    persist_session=False, reasoning_effort="xhigh",
                )
                await self.execute_task(repair_task, attempt)
            if self.request.mode == WorkflowMode.HTML:
                await self._browser_renderer(staging)
            verify_task = CodexTaskSpec(
                task_id=f"qa-verify-{attempt}", stage=StageName.QA, workspace=staging,
                prompt=qa_verify_prompt(self.request.mode, previous), allowed_paths=["qa_report.json"],
                required_outputs=["qa_report.json"],
                local_images=[path for path in (staging / "qa" / "render-desktop.png", staging / "qa" / "render-mobile.png") if path.is_file()],
                persist_session=False, reasoning_effort="xhigh",
            )
            verify_result, verify_fs = await self.execute_task(verify_task, attempt)
            report = qa_report(staging, self.request.mode)
            if verify_result.status == "completed" and verify_fs.passed and report.passed:
                for directory in ("md", "assets", "qa"):
                    if (staging / directory).is_dir(): replace_tree(staging / directory, self.workspace / directory)
                for filename in ("final.md", "final.html", "qa_report.json"):
                    if (staging / filename).is_file(): copy_file(staging / filename, self.workspace / filename)
                canonical = qa_report(self.workspace, self.request.mode)
                if self.request.baseline_workspace:
                    comparison = compare_baseline(self.workspace, self.request.baseline_workspace)
                    StateStore.atomic_write_json(self.workspace / ".magnum" / "baseline_comparison.json", comparison.model_dump(mode="json"))
                    if not comparison.passed:
                        previous = canonical.model_copy(update={"passed": False, "score": min(canonical.score, 60.0)})
                        continue
                self.mark_passed(StageName.QA, attempt, canonical); return canonical
            previous = report; self.save_report(report, attempt)
        raise StageFailed(StageName.QA, previous or qa_report(self.workspace, self.request.mode))
