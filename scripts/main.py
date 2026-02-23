#!/usr/bin/env python3
"""
Magnum Opus HTML - 模块化长文 HTML 创作 Agent 集群
CLI 入口
"""

import argparse
import sys
import os
from pathlib import Path

# SOTA: Ensure project root is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.orchestration.workflow_html import run_workflow
from src.core.gemini_client import GeminiClient
from src.core.config import DEFAULT_BASE_URL, DEFAULT_AUTH_PASSWORD


console = Console()


def test_connection(api_base_url: str, auth_token: str) -> bool:
    """测试 API 连接"""
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    return client.test_connection()


def main():
    parser = argparse.ArgumentParser(
        description="Magnum Opus HTML - AI 驱动的长文 HTML 生成系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 从文件生成
  python main.py --input project_brief.md --output workspaces/workspace/my_project/
  
  # 使用自定义 API 地址
  python main.py --input brief.md --api-url http://localhost:7860 --auth-token your_token
  
  # 测试 API 连接
  python main.py --test-connection
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="输入文件路径（包含原始素材/需求）"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./workspace",
        help="输出目录（默认: ./workspace）"
    )
    
    parser.add_argument(
        "--job-id",
        type=str,
        help="任务 ID（默认自动生成）"
    )
    
    parser.add_argument(
        "--api-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"Gemini API Native Proxy root URL (default: {DEFAULT_BASE_URL})"
    )
    
    parser.add_argument(
        "--auth-token",
        type=str,
        default=DEFAULT_AUTH_PASSWORD,
        help=f"API 认证 token (default: {DEFAULT_AUTH_PASSWORD})"
    )
    
    parser.add_argument(
        "--reference", "-r",
        type=str,
        action="append",
        help="参考文档路径（可多次指定）"
    )
    
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="测试 API 连接"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启调试模式，保存每一步的中间状态"
    )

    parser.add_argument(
        "--skip-qa",
        action="store_true",
        help="跳过文本质检 (Markdown QA) 阶段"
    )
    
    args = parser.parse_args()
    
    # 测试连接模式
    if args.test_connection:
        console.print("[bold]Testing API connection...[/bold]")
        if test_connection(args.api_url, args.auth_token):
            console.print("[green]✓ Connection successful![/green]")
            sys.exit(0)
        else:
            console.print("[red]✗ Connection failed![/red]")
            sys.exit(1)
    
    # 检查输入文件
    if not args.input:
        console.print("[red]Error: --input is required[/red]")
        parser.print_help()
        sys.exit(1)
    
    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Error: Input file not found: {args.input}[/red]")
        sys.exit(1)
    
    # 读取输入
    raw_materials = input_path.read_text(encoding="utf-8")
    
    # 显示任务信息
    console.print(Panel(
        f"[bold]Magnum Opus HTML[/bold]\n\n"
        f"📄 Input: {args.input}\n"
        f"📁 Output: {args.output}\n"
        f"🔗 API: {args.api_url}",
        title="Starting Workflow",
        border_style="blue"
    ))
    
    # 运行工作流
    try:
        import asyncio
        async def run_and_close():
            client = GeminiClient(api_base_url=args.api_url, auth_token=args.auth_token)
            try:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Running agent workflow...", total=None)
                    
                    final_state = await run_workflow(
                        raw_materials=raw_materials,
                        reference_docs=args.reference,
                        workspace_base=args.output,
                        job_id=args.job_id,
                        api_base_url=args.api_url,
                        auth_token=args.auth_token,
                        debug_mode=args.debug,
                        skip_markdown_qa=args.skip_qa,
                    )
                    progress.update(task, completed=True)
                    return final_state
            finally:
                await client.close_async()

        final_state = asyncio.run(run_and_close())
        
        # 显示结果
        if final_state.errors:
            console.print("[yellow]⚠ Workflow completed with errors:[/yellow]")
            for error in final_state.errors:
                console.print(f"  [red]• {error}[/red]")
        else:
            console.print("[green]✓ Workflow completed successfully![/green]")
        
        if final_state.final_html_path:
            console.print(f"\n[bold]Output:[/bold] {final_state.final_html_path}")
        
        # 显示统计
        console.print(Panel(
            f"📝 Sections written: {len(final_state.completed_md_sections)}\n"
            f"🔄 Sections transformed: {len(final_state.completed_html_sections)}\n"
            f"📁 Workspace: {final_state.workspace_path}",
            title="Summary",
            border_style="green" if not final_state.errors else "yellow"
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
