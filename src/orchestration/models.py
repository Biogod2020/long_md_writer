"""Typed contracts for the OpenAI Agents SDK + Codex publication workflow.

The control plane persists only durable workflow metadata. Manuscript content,
assets, reports, and browser evidence remain ordinary workspace files so Codex
can inspect them directly and deterministic validators can verify them without
trusting model self-reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowMode(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"


class StageName(str, Enum):
    PLAN = "plan"
    DRAFT = "draft"
    ASSETS = "assets"
    PUBLISH = "publish"
    QA = "qa"


STAGE_ORDER: tuple[StageName, ...] = (
    StageName.PLAN,
    StageName.DRAFT,
    StageName.ASSETS,
    StageName.PUBLISH,
    StageName.QA,
)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CheckSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    passed: bool
    severity: CheckSeverity = CheckSeverity.ERROR
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: StageName
    passed: bool
    score: float = Field(ge=0, le=100)
    checks: list[CheckResult] = Field(default_factory=list)
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=utc_now)

    @property
    def errors(self) -> list[CheckResult]:
        return [
            check
            for check in self.checks
            if not check.passed and check.severity == CheckSeverity.ERROR
        ]

    @property
    def warnings(self) -> list[CheckResult]:
        return [
            check
            for check in self.checks
            if not check.passed and check.severity == CheckSeverity.WARNING
        ]

    def feedback_text(self) -> str:
        failures = [check for check in self.checks if not check.passed]
        if not failures:
            return "All deterministic checks passed."
        return "\n".join(
            f"- [{check.severity.value.upper()}] {check.code}: {check.message}"
            for check in failures
        )


class CodexTaskResult(BaseModel):
    """Structured result required from every bounded Codex workspace task."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "partial", "failed"]
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


class CodexTaskSpec(BaseModel):
    """One task delegated by the Agents SDK manager to a Codex agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    task_id: str
    stage: StageName
    workspace: Path
    prompt: str
    allowed_paths: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    local_images: list[Path] = Field(default_factory=list)
    allow_network: bool = False
    sandbox_mode: Literal["read-only", "workspace-write"] = "workspace-write"
    persist_session: bool = False
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium"
    idle_timeout_seconds: float = Field(default=900.0, ge=30.0, le=7200.0)


class PlanSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    estimated_words: int = Field(ge=150, le=30_000)
    required_evidence: list[str] = Field(default_factory=list)
    visual_opportunities: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not re.fullmatch(
            r"[A-Za-z0-9_\-\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+",
            value,
        ):
            raise ValueError(
                "section id may contain only letters, digits, CJK characters, '-' and '_'"
            )
        return value


class QualityContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    minimum_section_coverage: float = Field(default=1.0, ge=0.95, le=1.0)
    minimum_word_ratio: float = Field(default=0.8, ge=0.75, le=1.5)
    require_zero_broken_assets: Literal[True] = True
    require_zero_unresolved_visual_directives: Literal[True] = True
    require_zero_placeholders: Literal[True] = True
    minimum_quality_score: float = Field(default=85.0, ge=85.0, le=100.0)


class PublicationPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int = 2
    project_title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    language: str = Field(default="zh-CN", min_length=2)
    objectives: list[str] = Field(min_length=1)
    sections: list[PlanSection] = Field(min_length=1)
    quality_contract: QualityContract = Field(default_factory=QualityContract)

    @field_validator("sections")
    @classmethod
    def unique_section_ids(cls, sections: list[PlanSection]) -> list[PlanSection]:
        ids = [section.id for section in sections]
        if len(ids) != len(set(ids)):
            raise ValueError("section ids must be unique")
        return sections


class StageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StageName
    status: StageStatus = StageStatus.PENDING
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_digest: str | None = None
    artifact_digest: str | None = None
    last_result_path: str | None = None
    last_quality_report_path: str | None = None
    error: str | None = None


class WorkflowRequest(BaseModel):
    """User-facing workflow request.

    Large inline source text is excluded from durable request serialization and
    materialized into ``workspace/inputs`` before model execution.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    user_intent: str = Field(min_length=1)
    output_base: Path = Path("./workspace")
    job_id: str | None = None
    mode: WorkflowMode = WorkflowMode.HTML
    reference_files: list[Path] = Field(default_factory=list)
    assets_dir: Path | None = None
    inline_reference_materials: str = Field(default="", exclude=True)
    auto_approve: bool = False
    resume: bool = True
    force_restart: bool = False
    allow_network: bool = False
    max_stage_attempts: int = Field(default=3, ge=1, le=8)
    draft_concurrency: int = Field(default=3, ge=1, le=12)
    baseline_workspace: Path | None = None
    debug: bool = False
    orchestrator_model: str = "gpt-5.6-luna"
    codex_model: str = "gpt-5.3-codex"
    trace_include_sensitive_data: bool = False

    @model_validator(mode="after")
    def validate_paths(self) -> "WorkflowRequest":
        if self.assets_dir is not None and not self.assets_dir.exists():
            raise ValueError(f"assets_dir does not exist: {self.assets_dir}")
        missing = [str(path) for path in self.reference_files if not path.is_file()]
        if missing:
            raise ValueError(f"reference files do not exist: {missing}")
        if self.baseline_workspace is not None:
            if self.baseline_workspace.is_symlink():
                raise ValueError("baseline_workspace may not be a symlink")
            if not self.baseline_workspace.is_dir():
                raise ValueError(
                    f"baseline_workspace is not a directory: {self.baseline_workspace}"
                )
        return self


class JobState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 3
    job_id: str
    workspace: str
    mode: WorkflowMode
    user_intent: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    current_stage: StageName | None = None
    stages: dict[str, StageRecord] = Field(default_factory=dict)
    plan_approved: bool = False
    plan_approved_digest: str | None = None
    final_approved: bool = False
    final_approved_digest: str | None = None
    input_manifest_path: str = "inputs/manifest.json"
    input_digest: str | None = None
    baseline_workspace: str | None = None
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def record(self, stage: StageName) -> StageRecord:
        key = stage.value
        if key not in self.stages:
            self.stages[key] = StageRecord(name=stage)
        return self.stages[key]


class BaselineComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    baseline_workspace: str
    candidate_workspace: str
    baseline_metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    candidate_metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    regressions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: WorkflowStatus
    workspace_path: str
    final_markdown_path: str | None = None
    final_html_path: str | None = None
    quality_report_path: str | None = None
    baseline_comparison_path: str | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status == WorkflowStatus.PASSED
