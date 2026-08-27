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
import xml.etree.ElementTree as ET

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
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


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def svg_text_labels(path: Path) -> tuple[list[str], str | None]:
    """Extract direct rendered-text content without resolving XML entities."""
    try:
        raw = path.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            return [], "DOCTYPE or entity declarations are not permitted"
        root = ET.fromstring(raw)
        if root.tag.rsplit("}", 1)[-1].lower() != "svg":
            return [], "root is not svg"
        labels: list[str] = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1].lower() != "text":
                continue
            label = " ".join("".join(node.itertext()).split())
            if label:
                labels.append(label)
        return labels, None
    except Exception as exc:
        return [], str(exc)


def is_png(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


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

    raw_visual_contract = project.get("visual_contract", {"schema_version": 1, "figures": []})
    visual_contract_valid = (
        isinstance(raw_visual_contract, dict)
        and raw_visual_contract.get("schema_version", 1) == 1
        and isinstance(raw_visual_contract.get("figures", []), list)
        and len(raw_visual_contract.get("figures", [])) <= 100
    )
    checks.append(check(
        "project.visual_contract",
        visual_contract_valid,
        "visual_contract must use schema_version 1 with a figures array",
    ))
    visual_figures: list[dict[str, Any]] = []
    if visual_contract_valid:
        for index, figure in enumerate(raw_visual_contract.get("figures", [])):
            raw_labels = figure.get("required_labels", []) if isinstance(figure, dict) else None
            normalized_labels = [item.strip() for item in raw_labels] if isinstance(raw_labels, list) and all(nonempty_text(item) for item in raw_labels) else []
            valid = (
                isinstance(figure, dict)
                and isinstance(figure.get("id"), str)
                and bool(SAFE_ID.fullmatch(figure["id"]))
                and figure.get("section_id") in section_ids
                and nonempty_text(figure.get("kind"))
                and nonempty_text(figure.get("purpose"))
                and isinstance(raw_labels, list)
                and len(raw_labels) <= 40
                and len(normalized_labels) == len(raw_labels)
                and len(set(normalized_labels)) == len(normalized_labels)
                and ("review_required" not in figure or isinstance(figure.get("review_required"), bool))
            )
            checks.append(check(
                f"project.visual_figure.{index}",
                valid,
                f"visual figure {index} must define a safe id, planned section, kind, purpose, unique required labels, and optional boolean review_required",
            ))
            if valid:
                visual_figures.append({
                    "id": figure["id"],
                    "section_id": figure["section_id"],
                    "kind": figure["kind"].strip(),
                    "purpose": figure["purpose"].strip(),
                    "required_labels": normalized_labels,
                    "review_required": figure.get("review_required", True),
                })
    visual_ids = [figure["id"] for figure in visual_figures]
    checks.append(check(
        "project.visual_figure_ids_unique",
        len(visual_ids) == len(set(visual_ids)),
        "visual figure ids must be unique",
    ))

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
    preflights = manifest.get("visual_preflights", []) if isinstance(manifest, dict) else []
    reviews = manifest.get("visual_reviews", []) if isinstance(manifest, dict) else []
    preflights_valid = isinstance(preflights, list)
    reviews_valid = isinstance(reviews, list)
    checks.append(check("assets.visual_preflights_schema", preflights_valid, "visual_preflights must be an array when present"))
    checks.append(check("assets.visual_reviews_schema", reviews_valid, "visual_reviews must be an array when present"))
    if not manifest_valid:
        entries = []
    if not preflights_valid:
        preflights = []
    if not reviews_valid:
        reviews = []

    registered: dict[str, dict[str, Any]] = {}
    registered_by_id: dict[str, dict[str, Any]] = {}
    registered_targets: dict[str, Path] = {}
    for index, entry in enumerate(entries):
        required = {"id", "source", "path", "caption", "alt_text", "provenance", "licence", "used_in", "sha256"}
        fields_valid = (
            isinstance(entry, dict)
            and required <= set(entry)
            and isinstance(entry.get("id"), str)
            and bool(SAFE_ID.fullmatch(entry["id"]))
            and isinstance(entry.get("path"), str)
            and all(nonempty_text(entry.get(field)) for field in ("source", "caption", "alt_text", "provenance", "licence"))
            and isinstance(entry.get("used_in"), list)
            and all(nonempty_text(item) for item in entry.get("used_in", []))
            and valid_sha256(entry.get("sha256"))
        )
        checks.append(check(f"assets.entry.{index}.fields", fields_valid, f"asset entry {index} is incomplete or malformed"))
        if not fields_valid:
            continue
        relative = entry["path"].replace("\\", "/")
        target = safe_local(workspace, relative)
        local = relative.startswith("assets/") and relative != "assets/manifest.json" and target is not None
        checks.append(check(f"assets.entry.{index}.path", local, f"asset entry {index} must reference a local file under assets/"))
        if target is None:
            continue
        registered[relative] = entry
        registered_by_id[entry["id"]] = entry
        registered_targets[entry["id"]] = target
        checks.append(check(
            f"assets.entry.{index}.sha256",
            entry["sha256"] == sha256_file(target),
            f"asset entry {index} hash must match the physical file",
        ))
        checks.append(check(
            f"assets.entry.{index}.provenance",
            bool(entry["provenance"].strip()) and bool(entry["licence"].strip()),
            f"asset entry {index} requires provenance and licence",
        ))
    asset_ids = [entry.get("id") for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str)]
    asset_paths = [entry.get("path") for entry in entries if isinstance(entry, dict) and isinstance(entry.get("path"), str)]
    checks.append(check("assets.entry_ids_unique", len(asset_ids) == len(set(asset_ids)), "asset ids must be unique"))
    checks.append(check("assets.entry_paths_unique", len(asset_paths) == len(set(asset_paths)), "asset paths must be unique"))

    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        asset_id = entry["id"]
        derivative = entry.get("derivative_of")
        mermaid_render = str(entry.get("provenance", "")).startswith("agent_generated:mermaid-cli@")
        if derivative is None:
            if mermaid_render:
                checks.append(check(
                    f"assets.mermaid.{asset_id}.source_binding",
                    False,
                    f"Mermaid SVG {asset_id} requires a hash-bound retained Mermaid source",
                ))
            continue
        fields_valid = (
            isinstance(derivative, dict)
            and isinstance(derivative.get("asset_id"), str)
            and bool(SAFE_ID.fullmatch(derivative["asset_id"]))
            and valid_sha256(derivative.get("asset_sha256"))
            and nonempty_text(derivative.get("purpose"))
        )
        checks.append(check(
            f"assets.derivative.{asset_id}.fields",
            fields_valid,
            f"asset derivative {asset_id} is incomplete or malformed",
        ))
        parent = registered_by_id.get(derivative.get("asset_id")) if fields_valid else None
        binding_valid = (
            parent is not None
            and derivative.get("asset_id") != asset_id
            and parent.get("sha256") == derivative.get("asset_sha256")
        )
        checks.append(check(
            f"assets.derivative.{asset_id}.binding",
            binding_valid,
            f"asset derivative {asset_id} must bind a registered parent and its current hash",
        ))
        if mermaid_render:
            mermaid_binding = (
                binding_valid
                and derivative.get("purpose") == "rendered_from_mermaid_source"
                and str(parent.get("path", "")).startswith("assets/mermaid/")
                and str(parent.get("path", "")).endswith(".mmd")
                and str(parent.get("provenance", "")).startswith("agent_generated:mermaid-source@")
            )
            checks.append(check(
                f"assets.mermaid.{asset_id}.source_binding",
                mermaid_binding,
                f"Mermaid SVG {asset_id} must derive from a retained assets/mermaid/*.mmd source",
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
    section_images: dict[str, list[str]] = {section_id: [] for section_id in section_ids}
    image_sections: dict[str, list[str]] = {}
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
        for section_id, bounds in region_bounds.items():
            if bounds[0] < (match.start() or 0) < bounds[1]:
                section_images[section_id].append(relative)
                image_sections.setdefault(relative, []).append(section_id)
    checks.append(check("assets.no_remote_images", not remote_images, "article images must not use remote or active URLs", images=sorted(set(remote_images))))
    checks.append(check("assets.references_resolve", not broken_images, "every article image reference must resolve", images=sorted(set(broken_images))))
    checks.append(check("assets.references_registered", not unregistered_images, "every referenced asset must be registered", images=sorted(set(unregistered_images))))

    figures_by_id = {figure["id"]: figure for figure in visual_figures}
    bound_unknown = sorted({
        str(entry.get("visual_plan_id"))
        for entry in entries
        if isinstance(entry, dict) and entry.get("visual_plan_id") is not None and entry.get("visual_plan_id") not in figures_by_id
    })
    checks.append(check("assets.visual_plan_bindings_known", not bound_unknown, "every asset visual_plan_id must name a planned figure", visual_plan_ids=bound_unknown))

    preflight_by_id: dict[str, dict[str, Any]] = {}
    preflight_binding: dict[str, bool] = {}
    for index, receipt in enumerate(preflights):
        required = {"id", "asset_id", "asset_sha256", "visual_plan_id", "preview_asset_id", "preview_sha256", "metric_mode", "renderer", "passed", "issues", "warnings", "created_at"}
        fields_valid = (
            isinstance(receipt, dict)
            and required <= set(receipt)
            and isinstance(receipt.get("id"), str)
            and bool(SAFE_ID.fullmatch(receipt["id"]))
            and isinstance(receipt.get("asset_id"), str)
            and isinstance(receipt.get("preview_asset_id"), str)
            and valid_sha256(receipt.get("asset_sha256"))
            and valid_sha256(receipt.get("preview_sha256"))
            and isinstance(receipt.get("visual_plan_id"), str)
            and nonempty_text(receipt.get("metric_mode"))
            and nonempty_text(receipt.get("renderer"))
            and isinstance(receipt.get("passed"), bool)
            and isinstance(receipt.get("issues"), list)
            and isinstance(receipt.get("warnings"), list)
            and all(nonempty_text(item) for item in receipt.get("issues", []))
            and all(nonempty_text(item) for item in receipt.get("warnings", []))
            and nonempty_text(receipt.get("created_at"))
        )
        checks.append(check(f"assets.visual_preflight.{index}.fields", fields_valid, f"visual preflight {index} is incomplete or malformed"))
        if not fields_valid:
            continue
        source = registered_by_id.get(receipt["asset_id"])
        preview = registered_by_id.get(receipt["preview_asset_id"])
        plan = figures_by_id.get(receipt["visual_plan_id"])
        derivative = preview.get("derivative_of") if isinstance(preview, dict) else None
        binding_valid = (
            source is not None
            and preview is not None
            and plan is not None
            and source.get("sha256") == receipt["asset_sha256"]
            and source.get("visual_plan_id") == plan["id"]
            and str(source.get("path", "")).startswith("assets/svg/")
            and str(source.get("path", "")).endswith(".svg")
            and preview.get("sha256") == receipt["preview_sha256"]
            and str(preview.get("path", "")).startswith("assets/reviews/")
            and str(preview.get("path", "")).endswith(".png")
            and is_png(registered_targets.get(receipt["preview_asset_id"]))
            and isinstance(derivative, dict)
            and derivative.get("asset_id") == receipt["asset_id"]
            and derivative.get("asset_sha256") == receipt["asset_sha256"]
            and derivative.get("purpose") == "svg-preview"
        )
        checks.append(check(f"assets.visual_preflight.{index}.binding", binding_valid, f"visual preflight {index} must bind the current planned SVG and preview hashes"))
        preflight_by_id[receipt["id"]] = receipt
        preflight_binding[receipt["id"]] = binding_valid
    preflight_ids = list(preflight_by_id)
    checks.append(check("assets.visual_preflight_ids_unique", len(preflight_ids) == len(preflights), "visual preflight ids must be unique and valid"))

    review_by_id: dict[str, dict[str, Any]] = {}
    review_binding: dict[str, bool] = {}
    for index, receipt in enumerate(reviews):
        required = {"id", "asset_id", "asset_sha256", "visual_plan_id", "preflight_id", "preview_asset_id", "preview_sha256", "reviewer", "verdict", "summary", "findings", "checked_labels", "reviewed_at"}
        fields_valid = (
            isinstance(receipt, dict)
            and required <= set(receipt)
            and isinstance(receipt.get("id"), str)
            and bool(SAFE_ID.fullmatch(receipt["id"]))
            and isinstance(receipt.get("asset_id"), str)
            and isinstance(receipt.get("preflight_id"), str)
            and isinstance(receipt.get("preview_asset_id"), str)
            and valid_sha256(receipt.get("asset_sha256"))
            and valid_sha256(receipt.get("preview_sha256"))
            and isinstance(receipt.get("visual_plan_id"), str)
            and nonempty_text(receipt.get("reviewer"))
            and receipt.get("verdict") in {"pass", "fail"}
            and nonempty_text(receipt.get("summary"))
            and isinstance(receipt.get("findings"), list)
            and isinstance(receipt.get("checked_labels"), list)
            and all(nonempty_text(item) for item in receipt.get("findings", []))
            and all(nonempty_text(item) for item in receipt.get("checked_labels", []))
            and nonempty_text(receipt.get("reviewed_at"))
        )
        checks.append(check(f"assets.visual_review.{index}.fields", fields_valid, f"visual review {index} is incomplete or malformed"))
        if not fields_valid:
            continue
        preflight = preflight_by_id.get(receipt["preflight_id"])
        plan = figures_by_id.get(receipt["visual_plan_id"])
        source = registered_by_id.get(receipt["asset_id"])
        preview = registered_by_id.get(receipt["preview_asset_id"])
        binding_valid = (
            preflight is not None
            and preflight_binding.get(receipt["preflight_id"], False)
            and preflight.get("passed") is True
            and plan is not None
            and source is not None
            and preview is not None
            and receipt["asset_sha256"] == preflight.get("asset_sha256") == source.get("sha256")
            and receipt["visual_plan_id"] == preflight.get("visual_plan_id") == plan["id"]
            and receipt["preview_asset_id"] == preflight.get("preview_asset_id") == preview.get("id")
            and receipt["preview_sha256"] == preflight.get("preview_sha256") == preview.get("sha256")
        )
        checks.append(check(f"assets.visual_review.{index}.binding", binding_valid, f"visual review {index} must bind a passing preflight and current asset hashes"))
        review_by_id[receipt["id"]] = receipt
        review_binding[receipt["id"]] = binding_valid
    review_ids = list(review_by_id)
    checks.append(check("assets.visual_review_ids_unique", len(review_ids) == len(reviews), "visual review ids must be unique and valid"))

    for figure in visual_figures:
        figure_id = figure["id"]
        bound_assets = [entry for entry in registered_by_id.values() if entry.get("visual_plan_id") == figure_id]
        plan_assets_by_id = {entry.get("id"): entry for entry in bound_assets}
        successors: dict[str, list[str]] = {entry_id: [] for entry_id in plan_assets_by_id}
        revision_links_valid = bool(bound_assets)
        for entry in bound_assets:
            predecessor = entry.get("supersedes_asset_id")
            if predecessor is None:
                continue
            if not isinstance(predecessor, str) or predecessor not in plan_assets_by_id:
                revision_links_valid = False
                continue
            successors[predecessor].append(entry["id"])
        roots = [entry for entry in bound_assets if entry.get("supersedes_asset_id") is None]
        tips = [entry for entry in bound_assets if not successors.get(entry.get("id"), [])]
        if any(len(value) > 1 for value in successors.values()) or len(roots) != 1 or len(tips) != 1:
            revision_links_valid = False
        if revision_links_valid and tips:
            visited: set[str] = set()
            cursor = tips[0]
            while cursor and cursor.get("id") not in visited:
                visited.add(cursor["id"])
                predecessor = cursor.get("supersedes_asset_id")
                cursor = plan_assets_by_id.get(predecessor) if predecessor else None
            if len(visited) != len(bound_assets) or cursor is not None:
                revision_links_valid = False
        checks.append(check(
            f"visual.figure.{figure_id}.revision_chain",
            revision_links_valid,
            f"visual figure {figure_id} requires one acyclic append-only SVG revision chain with one current candidate",
            asset_ids=[entry.get("id") for entry in bound_assets],
        ))
        checks.append(check(
            f"visual.figure.{figure_id}.asset",
            revision_links_valid and len(tips) == 1,
            f"visual figure {figure_id} must resolve to exactly one current registered SVG asset",
            asset_ids=[entry.get("id") for entry in bound_assets],
        ))
        if not revision_links_valid or len(tips) != 1:
            continue
        asset = tips[0]
        for retired in bound_assets:
            if retired is asset:
                continue
            retired_uses = image_sections.get(retired.get("path", ""), [])
            checks.append(check(
                f"visual.figure.{figure_id}.retired_asset.{retired.get('id')}.unreferenced",
                not retired_uses,
                f"retired SVG candidate {retired.get('id')} may not remain referenced in article.md",
                sections=retired_uses,
            ))
        asset_path = asset.get("path", "")
        svg_asset = asset_path.startswith("assets/svg/") and asset_path.endswith(".svg")
        checks.append(check(f"visual.figure.{figure_id}.svg_asset", svg_asset, f"visual figure {figure_id} must bind an assets/svg/*.svg asset"))
        checks.append(check(
            f"visual.figure.{figure_id}.declared_section",
            figure["section_id"] in asset.get("used_in", []),
            f"visual figure {figure_id} asset must declare its planned section in used_in",
        ))
        uses = image_sections.get(asset_path, [])
        checks.append(check(
            f"visual.figure.{figure_id}.article_reference",
            figure["section_id"] in uses,
            f"visual figure {figure_id} SVG must be referenced in its planned article section",
            sections=uses,
        ))
        checks.append(check(
            f"visual.figure.{figure_id}.article_reference_scope",
            set(uses) <= {figure["section_id"]},
            f"visual figure {figure_id} SVG may not be referenced outside its planned section",
            sections=uses,
        ))
        target = registered_targets.get(asset.get("id"))
        labels, label_error = svg_text_labels(target) if target is not None and svg_asset else ([], "registered SVG is unavailable")
        checks.append(check(
            f"visual.figure.{figure_id}.required_labels",
            label_error is None and all(label in labels for label in figure["required_labels"]),
            f"visual figure {figure_id} SVG must contain every required label",
            missing=[label for label in figure["required_labels"] if label not in labels],
            parse_error=label_error,
        ))
        passing_preflights = [
            receipt for receipt in preflights
            if isinstance(receipt, dict)
            and preflight_binding.get(receipt.get("id"), False)
            and receipt.get("passed") is True
            and receipt.get("asset_id") == asset.get("id")
            and receipt.get("asset_sha256") == asset.get("sha256")
            and receipt.get("visual_plan_id") == figure_id
            and receipt.get("metric_mode") == "coretext"
        ]
        checks.append(check(
            f"visual.figure.{figure_id}.preflight",
            bool(passing_preflights),
            f"visual figure {figure_id} requires a passing CoreText-backed hash-bound geometry preflight",
        ))
        if figure["review_required"]:
            passing_reviews = [
                receipt for receipt in reviews
                if isinstance(receipt, dict)
                and review_binding.get(receipt.get("id"), False)
                and receipt.get("verdict") == "pass"
                and receipt.get("asset_id") == asset.get("id")
                and receipt.get("asset_sha256") == asset.get("sha256")
                and receipt.get("visual_plan_id") == figure_id
                and set(figure["required_labels"]) <= set(receipt.get("checked_labels", []))
            ]
            checks.append(check(
                f"visual.figure.{figure_id}.review",
                bool(passing_reviews),
                f"visual figure {figure_id} requires a passing review of its retained PNG preview",
            ))

    metrics = {
        "article_sha256": sha256_bytes(article_bytes),
        "word_count": total_words,
        "target_words": target_words,
        "completion_ratio": round(total_ratio, 3),
        "chunk_count": len(chunks),
        "asset_count": len(physical),
        "visual_figure_count": len(visual_figures),
        "visual_preflight_count": len(preflights),
        "visual_review_count": len(reviews),
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
