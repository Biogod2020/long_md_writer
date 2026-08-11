"""Planning, drafting, and asset quality gates."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .models import CheckResult, CheckSeverity, QualityReport, StageName, WorkflowMode
from .quality_common import (
    build_report,
    check,
    count_words,
    load_plan,
    markdown_refs,
    placeholder_count,
    safe_local,
    sha256_file,
    visual_directives,
)


def plan_report(workspace: Path, mode: WorkflowMode) -> QualityReport:
    del mode
    checks: list[CheckResult] = []
    brief = workspace / "project_brief.md"
    plan, error = load_plan(workspace)
    checks.append(check("plan.brief_exists", brief.is_file() and not brief.is_symlink(), "project_brief.md must exist"))
    checks.append(check("plan.brief_substantive", brief.is_file() and count_words(brief.read_text(encoding="utf-8")) >= 40, "project brief must be substantive"))
    checks.append(check("plan.schema", plan is not None, error or "plan schema is valid"))
    if plan is not None:
        checks.append(check("plan.sections", len(plan.sections) >= 1, "plan must contain sections"))
        checks.append(check("plan.targets", all(section.estimated_words >= 150 for section in plan.sections), "section targets must be meaningful"))
        checks.append(check("plan.contract", plan.quality_contract.minimum_quality_score >= 85, "quality contract must remain strict"))
    return build_report(StageName.PLAN, checks, {"section_count": len(plan.sections) if plan else 0})


def draft_report(workspace: Path, *, section_id: str | None = None) -> QualityReport:
    plan, error = load_plan(workspace)
    checks: list[CheckResult] = [check("draft.plan", plan is not None, error or "plan is valid")]
    if plan is None:
        return build_report(StageName.DRAFT, checks)
    sections = [item for item in plan.sections if section_id is None or item.id == section_id]
    checks.append(check("draft.section_known", bool(sections), "requested section must exist in plan"))
    total_words = 0
    for section in sections:
        path = workspace / "drafts" / f"{section.id}.md"
        exists = path.is_file() and not path.is_symlink()
        checks.append(check(f"draft.{section.id}.exists", exists, f"drafts/{section.id}.md must exist"))
        if not exists:
            continue
        text = path.read_text(encoding="utf-8")
        words = count_words(text); total_words += words
        minimum = max(150, int(section.estimated_words * 0.75))
        checks.append(check(f"draft.{section.id}.length", words >= minimum, f"section has {words} words; requires at least {minimum}"))
        checks.append(check(
            f"draft.{section.id}.heading",
            bool(re.search(rf"^##\s+{re.escape(section.title)}\s*$", text, re.M | re.I)),
            "draft needs its planned H2 heading",
            severity=CheckSeverity.WARNING,
        ))
        checks.append(check(f"draft.{section.id}.placeholders", placeholder_count(text) == 0, "draft may not contain placeholders"))
        checks.append(check(f"draft.{section.id}.visual_json", all("invalid" not in value for value in visual_directives(text)), "visual directives must contain valid JSON"))
    return build_report(StageName.DRAFT, checks, {"word_count": total_words, "section_count": len(sections)})


def _asset_file_safe(path: Path) -> bool:
    suffix = path.suffix.casefold()
    if suffix == ".svg":
        text = path.read_text(encoding="utf-8", errors="replace")
        return not re.search(
            r"<(?:script|foreignObject|iframe|object|embed)\b|\bon\w+\s*=|(?:href|xlink:href)\s*=\s*['\"](?:https?:|//|javascript:|file:)",
            text,
            re.I,
        )
    if suffix in {".mmd", ".mermaid"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return not re.search(r"\bclick\b|https?://|javascript:", text, re.I)
    return True


def assets_report(workspace: Path, mode: WorkflowMode) -> QualityReport:
    del mode
    checks: list[CheckResult] = []
    plan, error = load_plan(workspace)
    checks.append(check("assets.plan", plan is not None, error or "plan is valid"))
    md_dir = workspace / "md"
    manifest_path = workspace / "assets" / "asset-manifest.json"
    checks.append(check("assets.md_dir", md_dir.is_dir() and not md_dir.is_symlink(), "md/ must exist"))
    checks.append(check("assets.manifest", manifest_path.is_file() and not manifest_path.is_symlink(), "asset manifest must exist"))
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            checks.append(check("assets.manifest_json", False, f"invalid asset manifest: {exc}"))
    entries = manifest.get("assets", []) if isinstance(manifest, dict) else []
    checks.append(check("assets.manifest_schema", isinstance(entries, list) and manifest.get("schema_version") == 2, "asset manifest schema_version 2 is required"))
    registered: set[str] = set()
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        prefix = f"assets.entry.{index}"
        required = {"id", "source", "path", "caption", "alt_text", "provenance", "licence", "used_in"}
        checks.append(check(prefix + ".fields", isinstance(entry, dict) and required <= set(entry), "asset entry is incomplete"))
        if not isinstance(entry, dict) or "path" not in entry:
            continue
        relative = str(entry["path"]).replace("\\", "/")
        path = safe_local(workspace, relative)
        checks.append(check(prefix + ".path", relative.startswith("assets/") and path is not None, "asset path must be local under assets/"))
        if path is None:
            continue
        registered.add(path.relative_to(workspace).as_posix())
        checks.append(check(prefix + ".active_content", _asset_file_safe(path), "asset must not contain active external content"))
        checks.append(check(prefix + ".sha256", isinstance(entry.get("sha256"), str) and entry["sha256"] == sha256_file(path), "asset hash must bind the physical file"))
        checks.append(check(prefix + ".provenance", bool(str(entry.get("provenance", "")).strip()) and bool(str(entry.get("licence", "")).strip()), "asset provenance and licence are required"))

    expected = {section.id for section in plan.sections} if plan else set()
    present: set[str] = set(); referenced: set[str] = set(); broken: list[str] = []; unresolved = 0
    if md_dir.is_dir():
        for path in sorted(md_dir.glob("*.md")):
            if path.is_symlink():
                checks.append(check("assets.md_symlink", False, f"symlinked markdown rejected: {path.name}")); continue
            present.add(path.stem)
            text = path.read_text(encoding="utf-8"); unresolved += text.count(":::visual")
            for raw in markdown_refs(text):
                local = safe_local(workspace, raw, base=path.parent)
                if local is None: broken.append(f"{path.name}: {raw}")
                else: referenced.add(local.relative_to(workspace).as_posix())
    checks.append(check("assets.section_coverage", not expected or expected <= present, "md/ must contain every planned section"))
    checks.append(check("assets.no_directives", unresolved == 0, f"{unresolved} unresolved visual directives remain"))
    checks.append(check("assets.references", not broken, "all image references must resolve locally", broken=broken))
    physical = {
        path.relative_to(workspace).as_posix()
        for path in (workspace / "assets").rglob("*")
        if path.is_file() and path.name != "asset-manifest.json"
    } if (workspace / "assets").is_dir() else set()
    checks.append(check("assets.registration", physical <= registered, "every physical asset must be registered", unregistered=sorted(physical - registered)))
    checks.append(check("assets.referenced_registration", referenced <= registered, "every referenced visual must be registered", unregistered=sorted(referenced - registered)))
    return build_report(StageName.ASSETS, checks, {
        "asset_count": len(physical),
        "unresolved_visual_directives": unresolved,
        "broken_assets": len(broken),
    })
