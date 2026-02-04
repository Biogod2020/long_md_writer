#!/usr/bin/env python3
"""
Magnum Opus SOTA 2.0 - Markdown 语义生成流水线
CLI 入口
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# SOTA: Ensure project root is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.orchestration.workflow_markdown import run_sota2_workflow


def main():
    parser = argparse.ArgumentParser(
        description="Magnum Opus SOTA 2.0 - Markdown 语义生成流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 只使用用户意图 (指令)
  python main_markdown.py --intent "写一篇关于 AI 的科普文章"

  # 使用意图 + 参考资料
  python main_markdown.py --intent "请将这份资料整理成教材" --reference inputs/raw_data.md

  # 多个参考资料
  python main_markdown.py --intent "汇总医学指南" --reference doc1.md --reference doc2.md
""",
    )
    
    parser.add_argument(
        "--intent", "-i",
        type=str,
        required=True,
        help="用户意图/指令 (告诉 AI 做什么)"
    )
    
    parser.add_argument(
        "--reference", "-r",
        type=str,
        action="append",
        help="参考资料文件路径 (可多次指定，将合并为一个完整的 reference_materials)"
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
        "--global-uar",
        type=str,
        help="全局资产库索引路径 (例如: data/global_asset_lib/master_assets.json)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启调试模式"
    )


    args = parser.parse_args()
    
    # 读取用户意图
    user_intent = args.intent
    
    # 读取参考资料 (合并所有文件)
    reference_materials = ""
    if args.reference:
        ref_parts = []
        for ref_path in args.reference:
            ref_file = Path(ref_path)
            if not ref_file.exists():
                print(f"Warning: Reference file {ref_path} not found, skipping.")
                continue
            try:
                content = ref_file.read_text(encoding="utf-8")
                ref_parts.append(f"## 来源: {ref_file.name}\n\n{content}")
            except Exception as e:
                print(f"Warning: Failed to read {ref_path}: {e}")
        if ref_parts:
            reference_materials = "\n\n---\n\n".join(ref_parts)
    
    print(f"\n🎯 用户意图: {user_intent[:100]}...")
    if reference_materials:
        print(f"📚 参考资料: {len(args.reference)} 个文件, 共 {len(reference_materials)} 字符")
    else:
        print("📚 参考资料: (无)")
    
    try:
        asyncio.run(run_sota2_workflow(
            user_intent=user_intent,
            reference_materials=reference_materials,
            assets_input_dir=args.assets_dir,
            workspace_base=args.output,
            job_id=args.job_id,
            skip_vision=args.skip_vision,
            skip_asset_audit=args.skip_audit,
            debug_mode=args.debug,
            global_uar_path=args.global_uar,
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
