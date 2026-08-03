"""Control-plane state, isolation, promotion, and approval primitives."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from .browser_probe import render_browser_evidence
from .codex_runtime import OpenAICodexExecutor, TaskExecutor
from .input_safety import materialize_inputs, restore_input_permissions, sanitize_job_id
from .models import (
    CodexTaskResult,
    CodexTaskSpec,
    JobState,
    QualityReport,
    STAGE_ORDER,
    StageName,
    StageStatus,
    WorkflowMode,
    WorkflowRequest,
    WorkflowResult,
    WorkflowStatus,
)
from .quality import quality_report_for_stage, workspace_digest
from .state_store import JobLock, StateStore
from .workspace_guard import MutationAudit, WorkspaceMutationGuard

ApprovalHandler = Callable[[str, QualityReport], bool | Awaitable[bool]]
BrowserRenderer = Callable[[Path], Awaitable[dict[str, Any]]]


class StageFailed(RuntimeError):
    def __init__(self, stage: StageName, report: QualityReport) -> None:
        self.stage = stage; self.report = report
        super().__init__(f"{stage.value} failed: {report.feedback_text()}")


class ApprovalDeclined(RuntimeError):
    pass


def copy_file(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"unsafe source file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as target, source.open("rb") as origin:
            shutil.copyfileobj(origin, target, length=1024 * 1024)
            target.flush(); os.fsync(target.fileno())
        shutil.copystat(source, temporary_path, follow_symlinks=False)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists(): return
    if source.is_symlink() or not source.is_dir(): raise ValueError(f"unsafe source tree: {source}")
    for path in source.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"unsafe item in source tree: {path}")
    if destination.exists(): shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)


def replace_tree(source: Path, destination: Path) -> None:
    incoming = destination.parent / f".{destination.name}.incoming-{os.getpid()}"
    backup = destination.parent / f".{destination.name}.backup-{os.getpid()}"
    shutil.rmtree(incoming, ignore_errors=True); shutil.rmtree(backup, ignore_errors=True)
    copy_tree(source, incoming)
    try:
        if destination.exists(): os.replace(destination, backup)
        os.replace(incoming, destination); shutil.rmtree(backup, ignore_errors=True)
    except Exception:
        if destination.exists() and not backup.exists(): shutil.rmtree(destination, ignore_errors=True)
        if backup.exists(): os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(incoming, ignore_errors=True); shutil.rmtree(backup, ignore_errors=True)


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
    else: path.unlink(missing_ok=True)


class PublicationWorkflowBase:
    def __init__(
        self,
        *,
        executor: TaskExecutor | None = None,
        approval_handler: ApprovalHandler | None = None,
        browser_renderer: BrowserRenderer = render_browser_evidence,
    ) -> None:
        self._executor = executor; self._approval_handler = approval_handler
        self._browser_renderer = browser_renderer
        self.request: WorkflowRequest | None = None; self.workspace: Path | None = None
        self.store: StateStore | None = None; self.state: JobState | None = None
        self.task_root: Path | None = None

    @property
    def executor(self) -> TaskExecutor:
        if self._executor is None:
            assert self.request is not None
            self._executor = OpenAICodexExecutor(
                orchestrator_model=self.request.orchestrator_model,
                codex_model=self.request.codex_model,
                event_sink=lambda event: self.store.append_event(**event) if self.store else None,
            )
        return self._executor

    async def run(self, request: WorkflowRequest) -> WorkflowResult:
        self.request = request
        job_id = sanitize_job_id(request.job_id)
        output_base = request.output_base.resolve(); output_base.mkdir(parents=True, exist_ok=True)
        workspace = output_base / job_id
        with JobLock(output_base, job_id):
            if request.force_restart and workspace.exists(): shutil.rmtree(workspace)
            workspace.mkdir(parents=True, exist_ok=True)
            self.workspace = workspace; self.store = StateStore(workspace)
            self.task_root = output_base / ".magnum-tasks" / job_id; self.task_root.mkdir(parents=True, exist_ok=True)
            try: return await self._run_locked(job_id)
            except ApprovalDeclined as exc:
                self.state.status = WorkflowStatus.CANCELLED; self.state.errors.append(str(exc)); self.store.save(self.state)
                return self._result()
            except Exception as exc:
                if self.state is not None:
                    self.state.status = WorkflowStatus.FAILED
                    self.state.errors.append(f"{type(exc).__name__}: {exc}"); self.store.save(self.state)
                return self._result(extra_error=f"{type(exc).__name__}: {exc}")
            finally: shutil.rmtree(self.task_root, ignore_errors=True)

    async def _run_locked(self, job_id: str) -> WorkflowResult:
        assert self.request and self.workspace and self.store
        _, input_digest = materialize_inputs(self.request, self.workspace)
        loaded = self.store.load() if self.request.resume else None
        self.state = loaded or JobState(
            job_id=job_id,
            workspace=str(self.workspace),
            mode=self.request.mode,
            user_intent=self.request.user_intent,
            baseline_workspace=str(self.request.baseline_workspace.resolve()) if self.request.baseline_workspace else None,
        )
        if self.state.mode != self.request.mode: raise ValueError("cannot resume with a different output mode")
        if self.state.input_digest and self.state.input_digest != input_digest:
            self._invalidate_from(StageName.PLAN, remove_artifacts=True)
            self.state.plan_approved = False; self.state.plan_approved_digest = None
            self.state.final_approved = False; self.state.final_approved_digest = None
            self.store.append_event("input_changed", previous=self.state.input_digest, current=input_digest)
        self.state.user_intent = self.request.user_intent; self.state.input_digest = input_digest
        self.state.status = WorkflowStatus.RUNNING; self.state.errors = []
        for stage in STAGE_ORDER: self.state.record(stage)
        self.store.save(self.state)
        await self._run_stages()
        self.state.current_stage = None; self.state.status = WorkflowStatus.PASSED; self.store.save(self.state)
        return self._result()

    async def _run_stages(self) -> None:
        raise NotImplementedError

    def _result(self, extra_error: str | None = None) -> WorkflowResult:
        workspace = self.workspace or Path("."); state = self.state
        errors = list(state.errors if state else [])
        if extra_error and extra_error not in errors: errors.append(extra_error)
        return WorkflowResult(
            job_id=state.job_id if state else (self.request.job_id or "unknown"),
            status=state.status if state else WorkflowStatus.FAILED,
            workspace_path=str(workspace),
            final_markdown_path=str(workspace / "final.md") if (workspace / "final.md").is_file() else None,
            final_html_path=str(workspace / "final.html") if (workspace / "final.html").is_file() else None,
            quality_report_path=state.record(StageName.QA).last_quality_report_path if state else None,
            baseline_comparison_path=str(workspace / ".magnum" / "baseline_comparison.json") if (workspace / ".magnum" / "baseline_comparison.json").is_file() else None,
            errors=errors,
        )

    def _stage_input_digest(self, stage: StageName) -> str:
        assert self.state and self.workspace and self.request
        if stage == StageName.PLAN: return self.state.input_digest or ""
        patterns = {
            StageName.DRAFT: ["inputs/manifest.json", "project_brief.md", "plan.json"],
            StageName.ASSETS: ["inputs/manifest.json", "project_brief.md", "plan.json", "drafts/**"],
            StageName.PUBLISH: ["plan.json", "md/**", "assets/**"],
            StageName.QA: ["plan.json", "md/**", "assets/**", "final.md", "final.html"],
        }[stage]
        value = workspace_digest(self.workspace, patterns)
        if stage == StageName.QA and self.request.baseline_workspace:
            value = hashlib.sha256((value + str(self.request.baseline_workspace.resolve())).encode()).hexdigest()
        return value

    @staticmethod
    def artifact_patterns(stage: StageName, mode: WorkflowMode) -> list[str]:
        patterns = {
            StageName.PLAN: ["project_brief.md", "plan.json"], StageName.DRAFT: ["drafts/**"],
            StageName.ASSETS: ["md/**", "assets/**"], StageName.PUBLISH: ["final.md"],
            StageName.QA: ["md/**", "assets/**", "final.md", "qa/**", "qa_report.json"],
        }[stage]
        if mode == WorkflowMode.HTML and stage in {StageName.PUBLISH, StageName.QA}: patterns.append("final.html")
        return patterns

    def stage_reusable(self, stage: StageName) -> bool:
        assert self.state and self.workspace and self.request
        record = self.state.record(stage)
        if record.status != StageStatus.PASSED or record.input_digest != self._stage_input_digest(stage): return False
        if not quality_report_for_stage(self.workspace, stage, self.request.mode).passed: return False
        return record.artifact_digest == workspace_digest(self.workspace, self.artifact_patterns(stage, self.request.mode))

    def _invalidate_from(self, stage: StageName, *, remove_artifacts: bool) -> None:
        assert self.state and self.workspace
        for target in STAGE_ORDER[STAGE_ORDER.index(stage):]:
            record = self.state.record(target); record.status = StageStatus.PENDING
            record.input_digest = None; record.artifact_digest = None; record.error = None
        if stage != StageName.QA: self.state.final_approved = False; self.state.final_approved_digest = None
        if not remove_artifacts: return
        paths = {
            StageName.PLAN: ["project_brief.md", "plan.json", "drafts", "md", "assets", "final.md", "final.html", "qa", "qa_report.json"],
            StageName.DRAFT: ["drafts", "md", "assets", "final.md", "final.html", "qa", "qa_report.json"],
            StageName.ASSETS: ["md", "assets", "final.md", "final.html", "qa", "qa_report.json"],
            StageName.PUBLISH: ["final.md", "final.html", "qa", "qa_report.json"], StageName.QA: ["qa", "qa_report.json"],
        }[stage]
        for relative in paths: remove_path(self.workspace / relative)

    def prepare(self, stage: StageName, attempt: int, name: str) -> Path:
        assert self.task_root and self.workspace
        staging = self.task_root / stage.value / f"attempt-{attempt:02d}" / name
        shutil.rmtree(staging, ignore_errors=True); staging.mkdir(parents=True)
        inputs = {
            StageName.PLAN: ["inputs"], StageName.DRAFT: ["inputs", "project_brief.md", "plan.json"],
            StageName.ASSETS: ["inputs", "project_brief.md", "plan.json", "drafts"],
            StageName.PUBLISH: ["inputs", "project_brief.md", "plan.json", "md", "assets"],
            StageName.QA: ["inputs", "project_brief.md", "plan.json", "drafts", "md", "assets", "final.md", "final.html", "qa"],
        }[stage]
        for relative in inputs:
            source = self.workspace / relative; target = staging / relative
            if source.is_dir() and not source.is_symlink(): copy_tree(source, target)
            elif source.is_file() and not source.is_symlink(): copy_file(source, target)
        (staging / "AGENTS.md").write_text(
            "# Bounded publication task\nNever modify inputs/, AGENTS.md, or files outside allowed paths. Never create symlinks or invent evidence.\n",
            encoding="utf-8",
        )
        restore_input_permissions(staging); return staging

    async def execute_task(self, task: CodexTaskSpec, attempt: int) -> tuple[CodexTaskResult, MutationAudit]:
        assert self.store
        self.store.append_event("codex_task_started", task_id=task.task_id, stage=task.stage.value)
        with WorkspaceMutationGuard(task.workspace, task.allowed_paths) as guard:
            result = await self.executor.execute(task); result, audit = guard.finish(result, task.required_outputs)
        restore_input_permissions(task.workspace)
        path = self.store.stage_result_path(task.stage.value, attempt, task.task_id)
        StateStore.atomic_write_json(path, {"task": task.task_id, "result": result.model_dump(mode="json"), "filesystem_audit": audit.__dict__})
        self.store.append_event("codex_task_finished", task_id=task.task_id, stage=task.stage.value, status=result.status, changed_files=result.changed_files, unresolved_issues=result.unresolved_issues)
        return result, audit

    def save_report(self, report: QualityReport, attempt: int) -> None:
        assert self.store and self.state
        path = self.store.quality_report_path(report.stage.value, attempt)
        StateStore.atomic_write_json(path, report.model_dump(mode="json"))
        self.state.record(report.stage).last_quality_report_path = str(path.relative_to(self.workspace))

    def mark_passed(self, stage: StageName, attempt: int, report: QualityReport) -> None:
        assert self.state and self.store and self.workspace and self.request
        record = self.state.record(stage); record.status = StageStatus.PASSED; record.attempts = attempt
        record.finished_at = datetime.now(timezone.utc); record.error = None
        record.input_digest = self._stage_input_digest(stage)
        record.artifact_digest = workspace_digest(self.workspace, self.artifact_patterns(stage, self.request.mode))
        self.save_report(report, attempt); self.store.save(self.state)
        self.store.append_event("stage_passed", stage=stage.value, score=report.score)

    async def approval(self, kind: str, report: QualityReport) -> None:
        assert self.request and self.state and self.store and self.workspace
        digest = workspace_digest(self.workspace, ["plan.json", "project_brief.md"] if kind == "plan" else ["final.md", "final.html", "assets/**", "qa/**", "qa_report.json"])
        flag = self.state.plan_approved if kind == "plan" else self.state.final_approved
        saved = self.state.plan_approved_digest if kind == "plan" else self.state.final_approved_digest
        if flag and saved == digest: return
        if self.request.auto_approve: approved = True
        elif self._approval_handler is not None:
            value = self._approval_handler(kind, report); approved = await value if inspect.isawaitable(value) else bool(value)
        elif sys.stdin.isatty():
            approved = (await __import__("asyncio").to_thread(input, f"Approve {kind} gate ({report.score:.1f})? [y/N]: ")).strip().casefold() in {"y", "yes"}
        else: raise ApprovalDeclined(f"{kind} approval required; use --auto-approve or provide a handler")
        if not approved: raise ApprovalDeclined(f"{kind} approval declined")
        if kind == "plan": self.state.plan_approved = True; self.state.plan_approved_digest = digest
        else: self.state.final_approved = True; self.state.final_approved_digest = digest
        self.store.save(self.state); self.store.append_event("approval_granted", kind=kind, digest=digest)
