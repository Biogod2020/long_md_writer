#!/usr/bin/env python3
"""Convenience CLI for Markdown-only jobs."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.models import WorkflowMode, WorkflowRequest
from src.orchestration.openai_workflow import run_publication_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Magnum Opus Markdown publisher")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--intent", "-i")
    group.add_argument("--input", type=Path)
    parser.add_argument("--reference", "-r", type=Path, action="append", default=[])
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--output", "-o", type=Path, default=Path("./workspace"))
    parser.add_argument("--job-id")
    parser.add_argument("--baseline-workspace", type=Path)
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--force-restart", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def _run(args: argparse.Namespace) -> int:
    intent = args.intent
    if args.input is not None:
        intent = args.input.read_text(encoding="utf-8")
    request = WorkflowRequest(
        user_intent=intent,
        reference_files=args.reference,
        assets_dir=args.assets_dir,
        output_base=args.output,
        job_id=args.job_id,
        mode=WorkflowMode.MARKDOWN,
        baseline_workspace=args.baseline_workspace,
        auto_approve=args.auto_approve,
        force_restart=args.force_restart,
        allow_network=args.allow_network,
        debug=args.debug,
    )
    result = await run_publication_workflow(request)
    if args.as_json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"Status: {result.status.value}\nWorkspace: {result.workspace_path}")
        if result.final_markdown_path:
            print(f"Markdown: {result.final_markdown_path}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result.succeeded else 1


def main() -> int:
    try:
        return asyncio.run(_run(build_parser().parse_args()))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
