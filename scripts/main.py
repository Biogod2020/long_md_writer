#!/usr/bin/env python3
"""Unified CLI for Markdown and self-contained HTML publication."""

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
    parser = argparse.ArgumentParser(description="Magnum Opus: OpenAI Agents SDK + Codex publisher")
    parser.add_argument("--input", "-i", type=Path, required=True, help="UTF-8 request/brief file")
    parser.add_argument("--reference", "-r", type=Path, action="append", default=[])
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--output", "-o", type=Path, default=Path("./workspace"))
    parser.add_argument("--job-id")
    parser.add_argument("--mode", choices=[mode.value for mode in WorkflowMode], default="html")
    parser.add_argument("--baseline-workspace", type=Path)
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--force-restart", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--draft-concurrency", type=int, default=3)
    parser.add_argument("--max-stage-attempts", type=int, default=3)
    parser.add_argument("--orchestrator-model", default="gpt-5.6-luna")
    parser.add_argument("--codex-model", default="gpt-5.3-codex")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def _run(args: argparse.Namespace) -> int:
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    request = WorkflowRequest(
        user_intent=args.input.read_text(encoding="utf-8"),
        reference_files=args.reference,
        assets_dir=args.assets_dir,
        output_base=args.output,
        job_id=args.job_id,
        mode=WorkflowMode(args.mode),
        baseline_workspace=args.baseline_workspace,
        auto_approve=args.auto_approve,
        force_restart=args.force_restart,
        resume=not args.no_resume,
        allow_network=args.allow_network,
        draft_concurrency=args.draft_concurrency,
        max_stage_attempts=args.max_stage_attempts,
        orchestrator_model=args.orchestrator_model,
        codex_model=args.codex_model,
        debug=args.debug,
    )
    result = await run_publication_workflow(request)
    if args.as_json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"Status: {result.status.value}")
        print(f"Workspace: {result.workspace_path}")
        if result.final_markdown_path:
            print(f"Markdown: {result.final_markdown_path}")
        if result.final_html_path:
            print(f"HTML: {result.final_html_path}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result.succeeded else 1


def main() -> int:
    args = build_parser().parse_args()
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
