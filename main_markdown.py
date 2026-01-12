#!/usr/bin/env python3
"""
Magnum Opus SOTA 2.0 - Markdown 语义生成流水线
CLI 入口
"""

import argparse
import asyncio
import sys
from pathlib import Path

from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.gemini_client import GeminiClient

def main():
    parser = argparse.ArgumentParser(
        description="Magnum Opus SOTA 2.0 - Markdown 语义生成流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="输入文件路径（包含原始素材/需求）"
    )
    
    parser.add_argument(
        "--user-prompt", "-u",
        type=str,
        help="额外的用户需求描述"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./workspace",
        help="输出文件夹基础路径 (默认: ./workspace)"
    )
    
    parser.add_argument(
        "--job-id",
        type=str,
        help="指定任务 ID"
    )
    
    parser.add_argument(
        "--assets-dir",
        type=str,
        default="inputs",
        help="资产输入目录 (默认: inputs)"
    )
    
    parser.add_argument(
        "--skip-vision",
        action="store_true",
        help="跳过 VLM 资产索引"
    )
    
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="跳过资产审计"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启调试模式"
    )

    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file {args.input} not found.")
        sys.exit(1)
        
    raw_materials = input_path.read_text(encoding="utf-8")
    
    try:
        asyncio.run(run_sota2_workflow(
            raw_materials=raw_materials,
            user_prompt=args.user_prompt or "",
            assets_input_dir=args.assets_dir,
            workspace_base=args.output,
            job_id=args.job_id,
            skip_vision=args.skip_vision,
            skip_asset_audit=args.skip_audit,
            debug_mode=args.debug
        ))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
