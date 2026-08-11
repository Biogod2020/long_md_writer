"""Shared deterministic quality helpers and baseline comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

from .models import (
    BaselineComparison,
    CheckResult,
    CheckSeverity,
    PublicationPlan,
    QualityReport,
    StageName,
    WorkflowMode,
)

WORD = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
PLACEHOLDER = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bFIXME\b|\[\s*(?:insert|placeholder|citation needed)[^\]]*\]|lorem ipsum)",
    re.I,
)
VISUAL = re.compile(r":::visual\s*(\{.*?\})\s*.*?:::", re.S)
REMOTE = re.compile(r"^(?:https?:)?//", re.I)
ACTIVE_SCHEME = re.compile(r"^(?:javascript|vbscript|file):", re.I)
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(code: str, passed: bool, message: str, *, severity: CheckSeverity = CheckSeverity.ERROR, **details: Any) -> CheckResult:
    return CheckResult(code=code, passed=passed, severity=severity, message=message, details=details)


def build_report(stage: StageName, checks: list[CheckResult], metrics: dict[str, Any] | None = None) -> QualityReport:
    errors = sum(1 for item in checks if not item.passed and item.severity == CheckSeverity.ERROR)
    warnings = sum(1 for item in checks if not item.passed and item.severity == CheckSeverity.WARNING)
    return QualityReport(
        stage=stage,
        passed=errors == 0,
        score=max(0.0, 100.0 - errors * 18.0 - warnings * 4.0),
        checks=checks,
        metrics=metrics or {},
    )


def count_words(text: str) -> int:
    return len(WORD.findall(text))


def placeholder_count(text: str) -> int:
    return len(PLACEHOLDER.findall(text))


def safe_local(workspace: Path, raw: str, *, base: Path | None = None) -> Path | None:
    value = unquote(raw.strip())
    parsed = urlparse(value)
    if not value or value.startswith("#") or parsed.scheme or value.startswith("//"):
        return None
    candidate = ((base or workspace) / parsed.path).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError:
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def load_plan(workspace: Path) -> tuple[PublicationPlan | None, str | None]:
    path = workspace / "plan.json"
    if not path.is_file() or path.is_symlink():
        return None, "plan.json is missing or unsafe"
    try:
        return PublicationPlan.model_validate(read_json(path)), None
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return None, f"invalid plan.json: {exc}"


def visual_directives(text: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for match in VISUAL.finditer(text):
        try:
            values.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            values.append({"invalid": match.group(1)[:200]})
    return values


def markdown_refs(text: str) -> list[str]:
    refs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)", text)
    refs.extend(re.findall(r"<img\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", text, re.I))
    return refs


def workspace_digest(workspace: Path, patterns: Iterable[str]) -> str:
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in workspace.glob(pattern) if path.is_file() and not path.is_symlink())
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(workspace).as_posix()):
        relative = path.relative_to(workspace).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big")); digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def canonical_markdown(workspace: Path) -> str:
    for name in ("final.md", "final_full.md"):
        path = workspace / name
        if path.is_file() and not path.is_symlink():
            return path.read_text(encoding="utf-8", errors="replace")
    md_dir = workspace / "md"
    if not md_dir.is_dir():
        return ""
    return "\n\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(md_dir.glob("*.md"))
        if path.is_file() and not path.is_symlink()
    )


def publication_metrics(workspace: Path) -> dict[str, float | int | str | bool]:
    text = canonical_markdown(workspace)
    assets = workspace / "assets"
    physical_assets = (
        sum(1 for path in assets.rglob("*") if path.is_file() and path.name != "asset-manifest.json")
        if assets.is_dir()
        else 0
    )
    broken = 0
    for path in (workspace / "md").glob("*.md") if (workspace / "md").is_dir() else []:
        for raw in markdown_refs(path.read_text(encoding="utf-8", errors="replace")):
            if safe_local(workspace, raw, base=path.parent) is None:
                broken += 1
    score = 100 - min(60, placeholder_count(text) * 15 + text.count(":::visual") * 15 + broken * 20)
    return {
        "word_count": count_words(text),
        "placeholder_count": placeholder_count(text),
        "unresolved_visual_directives": text.count(":::visual"),
        "physical_asset_count": physical_assets,
        "broken_assets": broken,
        "has_html": (workspace / "final.html").is_file(),
        "quality_score": max(0, score),
    }


def compare_baseline(candidate: Path, baseline: Path) -> BaselineComparison:
    candidate = candidate.resolve(); baseline = baseline.resolve()
    base = publication_metrics(baseline); new = publication_metrics(candidate)
    regressions: list[str] = []
    if int(base["word_count"]) and int(new["word_count"]) < int(int(base["word_count"]) * 0.8):
        regressions.append(f"content volume regressed from {base['word_count']} to {new['word_count']} words")
    for metric, label in (
        ("placeholder_count", "placeholders"),
        ("unresolved_visual_directives", "unresolved visual directives"),
        ("broken_assets", "broken assets"),
    ):
        if int(new[metric]) > int(base[metric]):
            regressions.append(f"{label} increased from {base[metric]} to {new[metric]}")
    if int(base["physical_asset_count"]) > 0 and int(new["physical_asset_count"]) == 0:
        regressions.append("all visual assets were lost")
    if int(new["quality_score"]) < int(base["quality_score"]):
        regressions.append(f"quality score regressed from {base['quality_score']} to {new['quality_score']}")
    return BaselineComparison(
        passed=not regressions,
        baseline_workspace=str(baseline),
        candidate_workspace=str(candidate),
        baseline_metrics=base,
        candidate_metrics=new,
        regressions=regressions,
    )
