#!/usr/bin/env python3
"""Deterministic validator for the DSH-native long-writer workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
CHUNK = re.compile(
    r"<!-- longwriter:chunk ([A-Za-z0-9_-]+) section=([A-Za-z0-9_-]+):start -->\n"
    r"([\s\S]*?)\n<!-- longwriter:chunk \1:end -->"
)
CHUNK_START = re.compile(
    r"<!-- longwriter:chunk ([A-Za-z0-9_-]+) section=([A-Za-z0-9_-]+):start -->"
)
CHUNK_END = re.compile(r"<!-- longwriter:chunk ([A-Za-z0-9_-]+):end -->")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
REMOTE = re.compile(r"^(?:https?:)?//", re.I)
PLACEHOLDER_PATTERNS = [
    re.compile(r"\b(?:TODO|TBD|FIXME)\b", re.I),
    re.compile(r"\?\?\?"),
    re.compile(r":::visual\b"),
    re.compile(r"\[(?:citation needed|placeholder|insert [^\]]+)\]", re.I),
    re.compile(r"(?:待补充|待完善|占位符)"),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def count_words(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]", text))
    without_cjk = re.sub(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]", " ", text)
    latin = len(re.findall(r"[\w]+(?:['’\-][\w]+)*", without_cjk, flags=re.UNICODE))
    return cjk + latin


def safe_local(workspace: Path, raw: str, *, base: Path | None = None) -> Path | None:
    value = raw.strip().strip("<>").split(maxsplit=1)[0]
    if not value or value.startswith("#") or REMOTE.match(value) or ":" in value.split("/", 1)[0]:
        return None
    root = workspace.resolve()
    candidate = ((base or root) / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() and not candidate.is_symlink() else None


def check(code: str, passed: bool, message: str, **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "passed": bool(passed),
        "message": message,
        "details": details,
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def section_marker(section_id: str, edge: str) -> str:
    return f"<!-- longwriter:section {section_id}:{edge} -->"


def validate(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    checks: list[dict[str, Any]] = []
    project_path = workspace / "project.json"
    article_path = workspace / "article.md"
    manifest_path = workspace / "assets" / "manifest.json"

    checks.append(check("project.exists", project_path.is_file() and not project_path.is_symlink(), "project.json must exist"))
    checks.append(check("article.exists", article_path.is_file() and not article_path.is_symlink(), "article.md must exist"))
    checks.append(check("assets.manifest_exists", manifest_path.is_file() and not manifest_path.is_symlink(), "assets/manifest.json must exist"))
    if not project_path.is_file() or not article_path.is_file() or not manifest_path.is_file():
        return build_result(workspace, checks, {})

    try:
        project = load_json(project_path)
    except Exception as exc:
        checks.append(check("project.json", False, f"project.json is invalid: {exc}"))
        return build_result(workspace, checks, {})
    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        checks.append(check("assets.manifest_json", False, f"asset manifest is invalid: {exc}"))
        manifest = {}

    article_bytes = article_path.read_bytes()
    article = article_bytes.decode("utf-8")
    sections = project.get("sections") if isinstance(project, dict) else None
    project_valid = (
        isinstance(project, dict)
        and project.get("schema_version") == 1
        and isinstance(project.get("title"), str)
        and bool(project.get("title", "").strip())
        and isinstance(project.get("objective"), str)
        and bool(project.get("objective", "").strip())
        and isinstance(sections, list)
        and bool(sections)
    )
    checks.append(check("project.schema", project_valid, "project.json must use schema_version 1 and define title, objective, and sections"))
    if not project_valid:
        return build_result(workspace, checks, {"article_sha256": sha256_bytes(article_bytes)})

    normalized_sections: list[dict[str, Any]] = []
    section_ids: list[str] = []
    for index, section in enumerate(sections):
        valid = (
            isinstance(section, dict)
            and isinstance(section.get("id"), str)
            and bool(SAFE_ID.fullmatch(section["id"]))
            and isinstance(section.get("title"), str)
            and bool(section["title"].strip())
            and isinstance(section.get("objective"), str)
            and bool(section["objective"].strip())
            and isinstance(section.get("target_words"), int)
            and not isinstance(section.get("target_words"), bool)
            and section["target_words"] > 0
        )
        checks.append(check(f"project.section.{index}", valid, f"section {index} must define a safe id, title, objective, and positive target_words"))
        if valid:
            normalized_sections.append(section)
            section_ids.append(section["id"])
    checks.append(check("project.section_ids_unique", len(section_ids) == len(set(section_ids)), "section ids must be unique"))

    chunks = list(CHUNK.finditer(article))
    chunk_starts = list(CHUNK_START.finditer(article))
    chunk_ends = list(CHUNK_END.finditer(article))
    checks.append(check(
        "article.chunk_markers",
        len(chunks) == len(chunk_starts) == len(chunk_ends),
        "chunk markers must be balanced and well formed",
        parsed=len(chunks),
        starts=len(chunk_starts),
        ends=len(chunk_ends),
    ))
    chunk_ids = [match.group(1) for match in chunks]
    checks.append(check("article.chunk_ids_unique", len(chunk_ids) == len(set(chunk_ids)), "chunk ids must be unique"))
    checks.append(check("article.has_chunks", bool(chunks), "article must contain at least one committed chunk"))

    total_words = 0
    target_words = 0
    section_metrics: list[dict[str, Any]] = []
    quality = project.get("quality_contract") if isinstance(project.get("quality_contract"), dict) else {}
    minimum_section_ratio = quality.get("minimum_section_ratio", 0.75)
    minimum_total_ratio = quality.get("minimum_total_ratio", 0.75)
    if not isinstance(minimum_section_ratio, (int, float)) or isinstance(minimum_section_ratio, bool):
        minimum_section_ratio = 0.75
    if not isinstance(minimum_total_ratio, (int, float)) or isinstance(minimum_total_ratio, bool):
        minimum_total_ratio = 0.75

    region_bounds: dict[str, tuple[int, int]] = {}
    for section in normalized_sections:
        section_id = section["id"]
        start_marker = section_marker(section_id, "start")
        end_marker = section_marker(section_id, "end")
        start = article.find(start_marker)
        end = article.find(end_marker)
        markers_valid = start >= 0 and end > start and article.find(start_marker, start + 1) < 0 and article.find(end_marker, end + 1) < 0
        checks.append(check(f"article.section.{section_id}.markers", markers_valid, f"section {section_id} requires one ordered marker pair"))
        if not markers_valid:
            continue
        region_bounds[section_id] = (start, end)
        region = article[start + len(start_marker):end]
        heading = bool(re.search(rf"^##\s+{re.escape(section['title'])}\s*$", region, re.M | re.I))
        checks.append(check(f"article.section.{section_id}.heading", heading, f"section {section_id} requires its planned H2 heading"))
        prose = re.sub(r"<!-- longwriter:[^>]+-->", " ", region)
        prose = re.sub(r"^##\s+.*$", " ", prose, flags=re.M)
        words = count_words(prose)
        target = section["target_words"]
        ratio = words / target
        total_words += words
        target_words += target
        checks.append(check(
            f"article.section.{section_id}.length",
            ratio >= minimum_section_ratio,
            f"section {section_id} has {words} words; requires at least {int(target * minimum_section_ratio)}",
            words=words,
            target=target,
            ratio=ratio,
        ))
        section_metrics.append({"id": section_id, "words": words, "target": target, "ratio": round(ratio, 3)})

    unknown_sections = sorted({match.group(2) for match in chunks} - set(section_ids))
    checks.append(check("article.chunk_sections_known", not unknown_sections, "every chunk must belong to a planned section", unknown_sections=unknown_sections))
    misplaced: list[str] = []
    for match in chunks:
        section_id = match.group(2)
        bounds = region_bounds.get(section_id)
        if bounds is None or not (bounds[0] < match.start() < match.end() < bounds[1]):
            misplaced.append(match.group(1))
    checks.append(check("article.chunk_placement", not misplaced, "chunks must be physically contained in their declared sections", chunk_ids=misplaced))

    total_ratio = total_words / target_words if target_words else 0.0
    checks.append(check(
        "article.total_length",
        total_ratio >= minimum_total_ratio,
        f"article has {total_words} words; requires at least {int(target_words * minimum_total_ratio)}",
        words=total_words,
        target=target_words,
        ratio=total_ratio,
    ))
    placeholder_hits = sorted({pattern.pattern for pattern in PLACEHOLDER_PATTERNS if pattern.search(article)})
    checks.append(check("article.placeholders", not placeholder_hits, "article may not contain unresolved placeholders or visual directives", patterns=placeholder_hits))

    entries = manifest.get("assets") if isinstance(manifest, dict) else None
    manifest_valid = isinstance(manifest, dict) and manifest.get("schema_version") == 2 and isinstance(entries, list)
    checks.append(check("assets.manifest_schema", manifest_valid, "asset manifest requires schema_version 2 and an assets array"))
    registered: dict[str, dict[str, Any]] = {}
    if manifest_valid:
        for index, entry in enumerate(entries):
            required = {"id", "source", "path", "caption", "alt_text", "provenance", "licence", "used_in", "sha256"}
            fields_valid = isinstance(entry, dict) and required <= set(entry)
            checks.append(check(f"assets.entry.{index}.fields", fields_valid, f"asset entry {index} is incomplete"))
            if not fields_valid:
                continue
            relative = str(entry["path"]).replace("\\", "/")
            target = safe_local(workspace, relative)
            local = relative.startswith("assets/") and relative != "assets/manifest.json" and target is not None
            checks.append(check(f"assets.entry.{index}.path", local, f"asset entry {index} must reference a local file under assets/"))
            if target is None:
                continue
            registered[relative] = entry
            checks.append(check(
                f"assets.entry.{index}.sha256",
                isinstance(entry.get("sha256"), str) and entry["sha256"] == sha256_file(target),
                f"asset entry {index} hash must match the physical file",
            ))
            checks.append(check(
                f"assets.entry.{index}.provenance",
                bool(str(entry.get("provenance", "")).strip()) and bool(str(entry.get("licence", "")).strip()),
                f"asset entry {index} requires provenance and licence",
            ))

    physical = {
        path.relative_to(workspace).as_posix()
        for path in (workspace / "assets").rglob("*")
        if path.is_file() and not path.is_symlink() and path != manifest_path
    }
    checks.append(check("assets.registration", physical <= set(registered), "every physical asset must be registered", unregistered=sorted(physical - set(registered))))

    broken_images: list[str] = []
    remote_images: list[str] = []
    unregistered_images: list[str] = []
    for match in MARKDOWN_IMAGE.finditer(article):
        raw = match.group(1).strip().strip("<>").split(maxsplit=1)[0]
        if REMOTE.match(raw) or raw.startswith(("data:", "file:", "javascript:")):
            remote_images.append(raw)
            continue
        target = safe_local(workspace, raw, base=article_path.parent)
        if target is None:
            broken_images.append(raw)
            continue
        relative = target.relative_to(workspace).as_posix()
        if relative not in registered:
            unregistered_images.append(relative)
    checks.append(check("assets.no_remote_images", not remote_images, "article images must not use remote or active URLs", images=sorted(set(remote_images))))
    checks.append(check("assets.references_resolve", not broken_images, "every article image reference must resolve", images=sorted(set(broken_images))))
    checks.append(check("assets.references_registered", not unregistered_images, "every referenced asset must be registered", images=sorted(set(unregistered_images))))

    metrics = {
        "article_sha256": sha256_bytes(article_bytes),
        "word_count": total_words,
        "target_words": target_words,
        "completion_ratio": round(total_ratio, 3),
        "chunk_count": len(chunks),
        "asset_count": len(physical),
        "sections": section_metrics,
    }
    return build_result(workspace, checks, metrics)


def build_result(workspace: Path, checks: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    passed_count = sum(1 for item in checks if item["passed"])
    score = round(100.0 * passed_count / len(checks), 2) if checks else 0.0
    return {
        "schema_version": 1,
        "passed": bool(checks) and all(item["passed"] for item in checks),
        "score": score,
        "workspace": str(workspace),
        "checks": checks,
        "failures": [item for item in checks if not item["passed"]],
        "metrics": metrics,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate(args.workspace)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"passed={result['passed']} score={result['score']}")
        for failure in result["failures"]:
            print(f"- {failure['code']}: {failure['message']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
