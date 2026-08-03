"""CLI entry point for deterministic stage validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import StageName, WorkflowMode
from .quality import compare_baseline, quality_report_for_stage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Magnum Opus workspace artifacts")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--stage", choices=[stage.value for stage in StageName], required=True)
    parser.add_argument("--mode", choices=[mode.value for mode in WorkflowMode], default="html")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = quality_report_for_stage(
        args.workspace.resolve(), StageName(args.stage), WorkflowMode(args.mode)
    )
    payload = report.model_dump(mode="json")
    exit_code = 0 if report.passed else 1
    if args.baseline and args.stage == StageName.QA.value:
        comparison = compare_baseline(args.workspace, args.baseline)
        payload["baseline_comparison"] = comparison.model_dump(mode="json")
        if not comparison.passed:
            exit_code = 1
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{report.stage.value}: {'PASS' if report.passed else 'FAIL'} ({report.score:.1f})")
        for check in report.checks:
            marker = "PASS" if check.passed else check.severity.value.upper()
            print(f"[{marker}] {check.code}: {check.message}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
