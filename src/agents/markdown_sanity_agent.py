"""
MarkdownSanityAgent: SOTA 2.0 Local Structure & Syntax Fixer.
Dedicated to fixing objective structural errors (JSON, ::: blocks, LaTeX) 
using the Universal Fixer mechanism.
"""

from pathlib import Path
from typing import Optional, List
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.core.validators import MarkdownValidator, ValidationSeverity
from src.agents.markdown_qa.fixer import run_markdown_fixer, apply_patches

class MarkdownSanityAgent:
    """
    负责本地语法纠错的 Agent。
    它不进行语义审计，只通过静态校验器发现错误并调用 API 修复。
    """

    def __init__(self, client: Optional[GeminiClient] = None, max_retries: int = 3):
        self.client = client or GeminiClient()
        self.validator = MarkdownValidator()
        self.max_retries = max_retries

    async def run_async(self, state: AgentState) -> AgentState:
        """
        扫描所有已完成的章节，发现并修复结构性错误。
        """
        print("\n[SanityAgent] 🛠️ 启动本地结构扫描与自动修复...")
        
        # SOTA: 创建专门的日志目录
        sanity_log_dir = Path(state.workspace_path) / "sanity_logs"
        sanity_log_dir.mkdir(exist_ok=True)
        
        modified_any = False
        
        for md_path_str in state.completed_md_sections:
            md_path = Path(md_path_str)
            if not md_path.exists(): continue
            
            retry = 0
            while retry < self.max_retries:
                content = md_path.read_text(encoding="utf-8")
                validation = self.validator.validate_all(content)
                
                if validation.is_valid:
                    break
                
                # 提取致命错误
                errors = [i for i in validation.issues if i.severity == ValidationSeverity.ERROR]
                if not errors:
                    break
                
                retry += 1
                
                # --- 🔍 增强型 DEBUG 记录开始 ---
                print(f"\n[Sanity] 🚨 发现 {len(errors)} 个结构错误于 {md_path.name} (尝试 {retry}/{self.max_retries})")
                
                error_records = []
                for i, err in enumerate(errors, 1):
                    msg = f"  Issue {i}: {err.message} (Line {err.line_number})"
                    print(msg)
                    if err.context:
                        print(f"    Context: {err.context}")
                    error_records.append({
                        "message": err.message,
                        "line": err.line_number,
                        "context": err.context,
                        "suggestion": err.suggestion
                    })
                
                # 保存物理日志以供复盘
                import json
                from datetime import datetime
                log_file = sanity_log_dir / f"error_{md_path.stem}_it{retry}_{datetime.now().strftime('%H%M%S')}.json"
                log_file.write_text(json.dumps({
                    "file": md_path.name,
                    "iteration": retry,
                    "errors": error_records
                }, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"    📝 详细错误已记录至: {log_file.relative_to(state.workspace_path)}")
                # --- 🔍 增强型 DEBUG 记录结束 ---
                
                # 构造修复建议 (Advice)
                advice_parts = ["CRITICAL STRUCTURAL ERRORS FOUND BY SYSTEM VALIDATOR:"]
                for err in errors:
                    loc = f"Line {err.line_number}: " if err.line_number else ""
                    advice_parts.append(f"- {loc}{err.message}. Context: {err.context}")
                
                advice_parts.append("\nFix the issues above using precise JSON patches. Focus on JSON escaping and directive closure.")
                advice = "\n".join(advice_parts)
                
                # 调用 Universal Fixer
                fix_result = await run_markdown_fixer(
                    self.client,
                    content,
                    advice,
                    debug=state.debug_mode
                )
                
                if fix_result and fix_result.get("status") == "FIXED":
                    new_content = apply_patches(content, fix_result)
                    if new_content != content:
                        md_path.write_text(new_content, encoding="utf-8")
                        modified_any = True
                        print(f"    ✅ 已应用修复补丁至 {md_path.name}")
                    else:
                        print(f"    ⚠️ Fixer 未能产生有效变更")
                        break
                else:
                    print(f"    ❌ Fixer 运行失败")
                    break
                    
        if modified_any:
            print("\n[SanityAgent] ✨ 结构修复循环结束。")
        else:
            print("\n[SanityAgent] ✅ 未发现结构性错误。")
            
        return state
