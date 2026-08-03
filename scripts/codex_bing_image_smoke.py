#!/usr/bin/env python3
"""Credentialed ASSETS-stage smoke test using Bing Images through Codex."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from PIL import Image

from src.orchestration.codex_runtime import OpenAICodexExecutor
from src.orchestration.models import CodexTaskSpec, StageName, WorkflowMode
from src.orchestration.quality_content import assets_report
from src.orchestration.workspace_guard import WorkspaceMutationGuard


QUERY = "12 lead ECG electrode placement diagram site:commons.wikimedia.org"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_fixture(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)
    (workspace / "inputs").mkdir(parents=True)
    (workspace / "drafts").mkdir(parents=True)
    (workspace / "AGENTS.md").write_text(
        "# Bounded test\n"
        "Write only md/** and assets/**. Never modify inputs, drafts, plan.json, "
        "project_brief.md, or AGENTS.md. Never create symlinks. Do not hotlink. "
        "Record the source page, original image URL, licence, and SHA-256.\n",
        encoding="utf-8",
    )
    (workspace / "inputs" / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "files": []}, indent=2),
        encoding="utf-8",
    )
    (workspace / "project_brief.md").write_text(
        "Create one local, attributable medical-education image for an ECG guide.\n",
        encoding="utf-8",
    )
    (workspace / "plan.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "project_title": "Bing image smoke",
                "audience": "medical students",
                "language": "en",
                "objectives": ["test local image sourcing"],
                "sections": [
                    {
                        "id": "ecg",
                        "title": "ECG electrode placement",
                        "objective": "show standard 12-lead electrode placement",
                        "estimated_words": 200,
                        "required_evidence": [],
                        "visual_opportunities": ["electrode placement diagram"],
                    }
                ],
                "quality_contract": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (workspace / "drafts" / "ecg.md").write_text(
        "## ECG electrode placement\n\n"
        "A local diagram should illustrate standard precordial lead positions.\n\n"
        ":::visual {\"id\":\"ecg-bing\",\"action\":\"SEARCH_WEB\","
        "\"reason\":\"real-world educational diagram\","
        "\"description\":\"standard 12-lead ECG chest electrode placement\"}\n:::\n",
        encoding="utf-8",
    )


def build_prompt() -> str:
    return f"""
You are testing the network-enabled ASSETS path. Read AGENTS.md, plan.json, and
drafts/ecg.md. Use Bing Images explicitly with this exact query:

{QUERY}

Select a medically accurate image from Wikimedia Commons or another source with an
explicit reusable licence. Open the source page and verify the licence. Download the
original image into assets/; do not save a Bing thumbnail and do not hotlink.

Create md/ecg.md with a local image reference and no unresolved :::visual block.
Create assets/asset-manifest.json with schema_version 2 and one assets entry. It must
contain id, source, path, caption, alt_text, provenance, licence, used_in, sha256,
search_engine="bing", search_query, bing_search_url, source_page_url, and
original_image_url. The sha256 value must match the physical image. Write only md/**
and assets/**. Validate the downloaded file as an image before returning the required
structured result.
""".strip()


def validate_outputs(workspace: Path) -> dict[str, Any]:
    manifest_path = workspace / "assets" / "asset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("assets", [])
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("asset manifest contains no entries")
    entry = entries[0]
    if str(entry.get("search_engine", "")).casefold() != "bing":
        raise RuntimeError("manifest does not record Bing as the search engine")
    if entry.get("search_query") != QUERY:
        raise RuntimeError("manifest does not preserve the exact Bing query")
    bing_url = str(entry.get("bing_search_url", ""))
    if "bing.com/images/search" not in bing_url:
        raise RuntimeError("manifest lacks a Bing Images search URL")
    source_page = str(entry.get("source_page_url", ""))
    original_url = str(entry.get("original_image_url", ""))
    if not source_page.startswith(("http://", "https://")):
        raise RuntimeError("manifest lacks a valid source-page URL")
    if not original_url.startswith(("http://", "https://")):
        raise RuntimeError("manifest lacks a valid original-image URL")

    relative = str(entry.get("path", ""))
    if not relative.startswith("assets/"):
        raise RuntimeError("manifest asset path is not local under assets/")
    asset_path = workspace / relative
    with Image.open(asset_path) as image:
        image.verify()
    physical_sha = _sha256(asset_path)
    if entry.get("sha256") != physical_sha:
        raise RuntimeError("manifest SHA-256 does not match the physical image")

    report = assets_report(workspace, WorkflowMode.MARKDOWN)
    if not report.passed:
        raise RuntimeError(report.feedback_text())
    return {
        "entry": entry,
        "asset_bytes": asset_path.stat().st_size,
        "assets_quality_score": report.score,
        "asset_sha256": physical_sha,
    }


async def run(output: Path) -> dict[str, Any]:
    prepare_fixture(output)
    executor = OpenAICodexExecutor(
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL") or "gpt-5.6-luna",
        codex_model=os.getenv("CODEX_MODEL") or "gpt-5.3-codex",
    )
    task = CodexTaskSpec(
        task_id="bing-assets-smoke",
        stage=StageName.ASSETS,
        workspace=output,
        prompt=build_prompt(),
        allowed_paths=["md/**", "assets/**"],
        required_outputs=["md/ecg.md", "assets/asset-manifest.json"],
        allow_network=True,
        reasoning_effort="high",
        idle_timeout_seconds=900,
    )
    with WorkspaceMutationGuard(output, task.allowed_paths) as guard:
        result = await executor.execute(task)
        result, audit = guard.finish(result, task.required_outputs)
    payload: dict[str, Any] = {
        "task_result": result.model_dump(mode="json"),
        "filesystem_audit": {
            "passed": audit.passed,
            "changed_files": audit.changed_files,
            "unauthorized_files": audit.unauthorized_files,
            "restored_files": audit.restored_files,
            "missing_outputs": audit.missing_outputs,
            "symlinks": audit.symlinks,
        },
    }
    if result.status != "completed" or not audit.passed:
        return payload
    payload["validated_output"] = validate_outputs(output)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("codex-bing-smoke"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.output = args.output.resolve()
    result_path = args.output.parent / f"{args.output.name}-result.json"
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("CODEX_API_KEY")):
        payload = {"status": "skipped", "reason": "no OPENAI_API_KEY or CODEX_API_KEY"}
        result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("CODEX_BING_SMOKE=" + json.dumps(payload))
        return 0

    try:
        payload = asyncio.run(run(args.output))
    except Exception as exc:
        payload = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
        result_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("CODEX_BING_SMOKE=" + json.dumps(payload, ensure_ascii=False))
        return 1

    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("CODEX_BING_SMOKE=" + json.dumps(payload, ensure_ascii=False))
    task_status = payload.get("task_result", {}).get("status")
    return 0 if task_status == "completed" and "validated_output" in payload else 1


if __name__ == "__main__":
    raise SystemExit(main())
