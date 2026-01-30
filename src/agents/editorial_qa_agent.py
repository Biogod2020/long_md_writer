"""
EditorialQAAgent: SOTA 2.0 Phase E 全量语义综审

核心职责：
1. 全量多模态终审 - 接收完整文本与资产流
2. 校验 <img style=\"...\"> 裁切范围是否准确命中文字焦点
3. 语义一致性检查 - 确保图文描述对应
4. 生成审计报告与修复建议

执行时机：
- 在 AssetFulfillment 完成后、HTML 转换前执行
"""

import re
import json
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState, AssetQualityLevel
from ..core.patcher import StuckDetector
from .markdown_qa.fixer import run_markdown_fixer, apply_patches


class QAIssueType(Enum):
    """QA 问题类型"""
    CROP_MISMATCH = "crop_mismatch"  # 裁切区域与描述不符
    MISSING_ALT = "missing_alt"  # 缺少 alt 文本
    BROKEN_REFERENCE = "broken_reference"  # 引用的资产不存在
    SEMANTIC_DRIFT = "semantic_drift"  # 语义偏离（图与上下文不符）
    STYLE_INCONSISTENCY = "style_inconsistency"  # 样式不一致
    ACCESSIBILITY_ISSUE = "accessibility_issue"  # 可访问性问题


class QASeverity(Enum):
    """问题严重程度"""
    ERROR = "error"  # 必须修复
    WARNING = "warning"  # 建议修复
    INFO = "info"  # 仅供参考


@dataclass
class QAIssue:
    """QA 问题记录"""
    issue_type: QAIssueType
    severity: QASeverity
    location: str  # 问题位置描述
    message: str  # 问题描述
    suggestion: str = ""  # 修复建议
    context: dict = field(default_factory=dict)  # 额外上下文


@dataclass
class QAReport:
    """QA 审计报告"""
    passed: bool
    issues: list[QAIssue] = field(default_factory=list)
    summary: str = ""
    asset_count: int = 0
    reviewed_count: int = 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": [
                {
                    "type": i.issue_type.value,
                    "severity": i.severity.value,
                    "location": i.location,
                    "message": i.message,
                    "suggestion": i.suggestion
                }
                for i in self.issues
            ],
            "summary": self.summary,
            "asset_count": self.asset_count,
            "reviewed_count": self.reviewed_count
        }


# ============================================================================
# 提示词模板
# ============================================================================

EDITORIAL_QA_PROMPT = """你是一位专业的技术文档编辑审核员。请对以下内容进行全面的语义和视觉审核。

## 审核资源

1. **当前章节 Markdown**：包含文本和资产引用。
2. **当前章节渲染截图**：展示最终呈现给用户的视觉效果（如果提供）。
3. **全书前文上下文**：用于确保术语一致性和叙事连贯性（如果提供）。

## 审核重点

1. **视觉一致性（多模态审核）**：
   - 检查渲染截图中的图片内容是否与 Markdown 描述一致。
   - 检查图片裁切（object-position）是否准确，重点区域是否被遮挡。
   - 检查 LaTeX 公式在渲染后是否有溢出或错位。

2. **术语与一致性（全量上下文审核）**：
   - 对比当前章节与“前文上下文”，确保专业术语（如医学名词、技术术语）使用一致。
   - 检查叙事逻辑，确保没有与前文矛盾的信息。

3. **图文一致性**：
   - alt 文本是否准确描述图片内容。
   - figcaption 是否与上下文语义一致。

4. **资产与格式**：
   - 是否存在未履约的 :::visual 指令。
   - 引用和参照是否准确（如 [REF:xxx]）。

## 待审核 Markdown 内容

```markdown
{content}
```

{context_section}

## 输出格式

请以 JSON 格式输出审核结果：
```json
{{
  "passed": true/false,
  "issues": [
    {{
      "type": "crop_mismatch|missing_alt|broken_reference|semantic_drift|style_inconsistency|accessibility_issue",
      "severity": "error|warning|info",
      "location": "图片/段落位置描述",
      "message": "问题描述",
      "suggestion": "修复建议"
    }}
  ],
  "summary": "整体审核总结"
}}
```

**注意**：
- 只输出 JSON，不要其他内容。
- 如果没有问题，issues 为空数组，passed 为 true。
- severity=error 的问题会导致 passed=false。
"""


class EditorialQAAgent:
    """
    全量语义综审 Agent

    负责在 HTML 转换前进行最终的语义和质量审核。
    支持渲染感知（Visual-Aware）和全量上下文（Full-Context）审核。
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        renderer: Optional[any] = None,
        skip_llm_review: bool = False,
        strict_mode: bool = True
    ):
        """
        初始化 Editorial QA Agent

        Args:
            client: Gemini API 客户端
            renderer: 渲染器实例（可选），用于生成视觉快照
            skip_llm_review: 跳过 LLM 审核（仅执行本地检查）
            strict_mode: 严格模式（warning 也会导致失败）
        """
        self.client = client or GeminiClient()
        self.renderer = renderer
        self.skip_llm_review = skip_llm_review
        self.strict_mode = strict_mode

    async def run_async(
        self,
        state: AgentState,
        content: str,
        namespace: str,
        full_context: Optional[str] = None
    ) -> tuple[AgentState, QAReport, str]:
        """
        异步执行 QA 审核 (Critic-Fixer Loop)

        Returns:
            (更新后的状态, QA报告, 最终的Markdown内容)
        """
        iteration = 0
        max_iterations = 3
        current_content = content
        last_report = None
        stuck_detector = StuckDetector()

        print(f"[EditorialQA] 开始全量语义与视觉审核 (namespace: {namespace})")

        while iteration < max_iterations:
            iteration += 1
            print(f"  [Iteration {iteration}] 执行 Critic 审核...")

            issues: list[QAIssue] = []

            # 1. 本地静态检查
            local_issues = self._run_local_checks(current_content, namespace, state)
            issues.extend(local_issues)

            # 2. 渲染视觉快照
            screenshot_path = None
            if self.renderer:
                try:
                    if asyncio.iscoroutinefunction(self.renderer.render_to_image):
                        screenshot_path = await self.renderer.render_to_image(current_content, f"qa_{namespace}_{iteration}")
                    else:
                        screenshot_path = self.renderer.render_to_image(current_content, f"qa_{namespace}_{iteration}")
                except Exception as e:
                    print(f"    ❌ 渲染失败: {e}")

            # 3. LLM 审核
            if not self.skip_llm_review:
                llm_issues = await self._run_llm_review(
                    current_content, 
                    state,
                    full_context=full_context, 
                    image_path=screenshot_path
                )
                issues.extend(llm_issues)

            # 4. 生成报告
            asset_count = self._count_assets(current_content)
            error_count = sum(1 for i in issues if i.severity == QASeverity.ERROR)
            warning_count = sum(1 for i in issues if i.severity == QASeverity.WARNING)
            
            passed = error_count == 0
            if self.strict_mode:
                passed = passed and warning_count == 0

            last_report = QAReport(
                passed=passed,
                issues=issues,
                summary=self._generate_summary(issues, passed),
                asset_count=asset_count,
                reviewed_count=asset_count
            )

            if passed:
                print(f"  [Iteration {iteration}] ✅ 审核通过")
                break

            # 🛠️ Backoff & Retry Logic
            combined_advice = "|".join([i.message for i in issues])
            is_stuck = not stuck_detector.check_progress(combined_advice, current_content)
            
            if is_stuck:
                print(f"  [EditorialQA] ⚠️ 检测到重复修复建议且内容未变化，触发 Backoff 策略...")
                for issue in issues:
                    issue.suggestion = f"PREVIOUS ATTEMPT FAILED. You MUST provide more context in your SEARCH block to ensure a unique match. {issue.suggestion}"
                
                # 使用 state.loop_metadata 跟踪重试
                retry_key = f"qa_retry_{namespace}"
                if state.loop_metadata.get(retry_key, False):
                    print(f"  [EditorialQA] ❌ 第二次尝试仍卡住，停止迭代。")
                    break
                state.loop_metadata[retry_key] = True
            else:
                state.loop_metadata[f"qa_retry_{namespace}"] = False

            # 5. Fixer 修复
            print(f"  [Iteration {iteration}] 🛠️ 发现 {len(issues)} 个问题，尝试自动修复...")
            fixed_content = await self._run_fixer_loop(current_content, issues, full_context)
            
            # NOTE: We DON'T break early here if fixed_content == current_content.
            # We let the loop continue to the next iteration where the StuckDetector
            # will see that content hasn't changed despite having the same issues,
            # and then it will trigger the Backoff logic or break.
            
            current_content = fixed_content

        return state, last_report, current_content

    async def _run_fixer_loop(self, content: str, issues: list[QAIssue], full_context: Optional[str]) -> str:
        """运行 Fixer 尝试修复所有错误级别的问题 (并行处理)"""
        current_content = content
        # 只修复错误级别的问题
        errors = [i for i in issues if i.severity == QASeverity.ERROR]
        
        if not errors:
            return current_content

        print(f"    [Fixer] 正在并行修复 {len(errors)} 个错误...")
        
        async def fix_issue(issue: QAIssue, content_state: str) -> Optional[dict]:
            advice = f"ISSUE: {issue.message}\nLOCATION: {issue.location}\nSUGGESTION: {issue.suggestion}"
            try:
                return await asyncio.wait_for(
                    run_markdown_fixer(
                        self.client,
                        content_state,
                        advice,
                        context=full_context
                    ),
                    timeout=60.0
                )
            except Exception as e:
                print(f"      ❌ 修复过程出错: {e}")
                return None

        # 发起所有修复任务
        tasks = [fix_issue(issue, current_content) for issue in errors]
        fix_results = await asyncio.gather(*tasks)
        
        applied_count = 0
        for res in fix_results:
            if res and res.get("status") == "FIXED":
                new_content = apply_patches(current_content, res)
                if new_content != current_content:
                    current_content = new_content
                    applied_count += 1
        
        if applied_count > 0:
            print(f"    [Fixer] ✅ 成功应用了 {applied_count} 个修复补丁")
        
        return current_content

    def run(
        self,
        state: AgentState,
        content: str,
        namespace: str,
        full_context: Optional[str] = None
    ) -> tuple[AgentState, QAReport, str]:
        """同步版本"""
        import asyncio
        try:
            return asyncio.run(self.run_async(state, content, namespace, full_context))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.run_async(state, content, namespace, full_context))

    def _run_local_checks(
        self,
        content: str,
        namespace: str,
        state: AgentState
    ) -> list[QAIssue]:
        """执行本地静态检查"""
        issues = []
        issues.extend(self._check_unfulfilled_visuals(content))
        issues.extend(self._check_img_tags(content, state))
        issues.extend(self._check_figure_tags(content))
        issues.extend(self._check_broken_refs(content))
        issues.extend(self._check_mandatory_assets(content, state, namespace))
        return issues

    def _check_mandatory_assets(self, content: str, state: AgentState, namespace: str) -> list[QAIssue]:
        """检查所有 MANDATORY 资产是否已在正文中引用"""
        issues = []
        uar = state.get_uar()
        assigned_ids = []
        if state.manifest:
            for sec in state.manifest.sections:
                sec_ns = sec.id.replace("sec-", "s").replace("-", "")
                if sec_ns == namespace or sec.id == namespace:
                    assigned_ids = sec.metadata.get("assigned_assets", [])
                    break
        
        if not assigned_ids:
            assigned_ids = [a.id for a in uar.assets.values() if a.priority == "MANDATORY"]

        for aid in assigned_ids:
            if f'data-asset-id="{aid}"' not in content and f"data-asset-id='{aid}'" not in content and f'"matched_asset": "{aid}"' not in content:
                asset = uar.get_asset(aid)
                label = asset.semantic_label if asset else aid
                issues.append(QAIssue(
                    issue_type=QAIssueType.BROKEN_REFERENCE,
                    severity=QASeverity.ERROR,
                    location="全量文本",
                    message=f"缺少强制性资产: [{aid}] ({label})",
                    suggestion=f"请在文中合适位置插入该图片，它是用户要求的必备素材。"
                ))
        return issues

    def _check_unfulfilled_visuals(self, content: str) -> list[QAIssue]:
        """检查未履约的 :::visual 指令"""
        issues = []
        pattern = r':::visual\s*\{([^}]+)\}'
        for match in re.finditer(pattern, content):
            issues.append(QAIssue(
                issue_type=QAIssueType.BROKEN_REFERENCE,
                severity=QASeverity.ERROR,
                location=f"位置 {match.start()}",
                message=f"发现未履约的 :::visual 指令",
                suggestion="请运行 AssetFulfillmentAgent 处理此指令"
            ))
        return issues

    def _check_img_tags(self, content: str, state: AgentState) -> list[QAIssue]:
        """检查 img 标签"""
        issues = []
        img_pattern = r'<img\s+([^>]+)>'
        for match in re.finditer(img_pattern, content, re.IGNORECASE):
            attrs_str = match.group(1)
            if 'alt=' not in attrs_str.lower():
                issues.append(QAIssue(
                    issue_type=QAIssueType.MISSING_ALT,
                    severity=QASeverity.WARNING,
                    location=f"位置 {match.start()}",
                    message="img 标签缺少 alt 属性",
                    suggestion="添加描述性的 alt 文本以提高可访问性"
                ))
            src_match = re.search(r'src=["\']([^"\\]+)["\\]', attrs_str)
            if src_match:
                src = src_match.group(1)
                if not src.startswith(('http', '/', 'data:', 'generated_assets/', 'assets/', './')):
                    issues.append(QAIssue(
                        issue_type=QAIssueType.BROKEN_REFERENCE,
                        severity=QASeverity.WARNING,
                        location=f"位置 {match.start()}",
                        message=f"img src 路径可能无效: {src}",
                        suggestion="确保图片路径正确，使用相对路径 or 绝对路径"
                    ))
            style_match = re.search(r'style=["\']([^"\\]+)["\\]', attrs_str)
            if style_match:
                style = style_match.group(1)
                if 'object-position' in style:
                    pos_match = re.search(r'object-position:\s*(-?\d+)%\s+(-?\d+)%', style)
                    if pos_match:
                        x, y = int(pos_match.group(1)), int(pos_match.group(2))
                        if x < 0 or x > 100 or y < 0 or y > 100:
                            issues.append(QAIssue(
                                issue_type=QAIssueType.CROP_MISMATCH,
                                severity=QASeverity.ERROR,
                                message=f"object-position 值超出范围: {x}% {y}%",
                                suggestion="确保百分比值在 0-100 之间"
                            ))
        return issues

    def _check_figure_tags(self, content: str) -> list[QAIssue]:
        """检查 figure 标签"""
        issues = []
        figure_pattern = r'<figure[^>]*>([\s\S]*?)</figure>'
        for match in re.finditer(figure_pattern, content, re.IGNORECASE):
            if '<figcaption' not in match.group(1).lower():
                issues.append(QAIssue(
                    issue_type=QAIssueType.ACCESSIBILITY_ISSUE,
                    severity=QASeverity.INFO,
                    message="figure 标签缺少 figcaption",
                    suggestion="添加 figcaption 以提供图片说明"
                ))
        return issues

    def _check_broken_refs(self, content: str) -> list[QAIssue]:
        """检查断裂的引用"""
        issues = []
        ref_pattern = r'\[REF:([^\]]+)\]'
        for match in re.finditer(ref_pattern, content):
            ref_id = match.group(1)
            if not re.match(r'^[a-z0-9-]+$', ref_id):
                issues.append(QAIssue(
                    issue_type=QAIssueType.BROKEN_REFERENCE,
                    severity=QASeverity.WARNING,
                    message=f"引用 ID 格式不规范: {ref_id}"
                ))
        return issues

    async def _run_llm_review(
        self, 
        content: str, 
        state: AgentState,
        full_context: Optional[str] = None,
        image_path: Optional[Path] = None
    ) -> list[QAIssue]:
        """使用 LLM 进行语义和视觉审核"""
        issues = []
        context_section = f"## 全书前文上下文\n\n```markdown\n{full_context}\n```" if full_context else ""
        prompt = EDITORIAL_QA_PROMPT.format(content=content, context_section=context_section)
        try:
            parts = [{"text": prompt}]
            if image_path and image_path.exists():
                import base64
                with open(image_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                parts.append({"inline_data": {"mime_type": "image/png", "data": img_data}})

            response = await self.client.generate_async(
                parts=parts,
                system_instruction="你是一位专业的技术文档编辑审核员。请仔细审核文档质量。",
                temperature=0.2
            )
            if not response.success: return issues
            if response.thoughts:
                state.thoughts += f"\n[EditorialQA Review] {response.thoughts}"
            data = response.json_data
            if data:
                for issue_data in data.get("issues", []):
                    try:
                        issue_type = QAIssueType(issue_data.get("type", "semantic_drift"))
                    except ValueError:
                        issue_type = QAIssueType.SEMANTIC_DRIFT

                    try:
                        severity = QASeverity(issue_data.get("severity", "warning"))
                    except ValueError:
                        severity = QASeverity.WARNING

                    issues.append(QAIssue(
                        issue_type=issue_type,
                        severity=severity,
                        location=issue_data.get("location", "未知"),
                        message=issue_data.get("message", ""),
                        suggestion=issue_data.get("suggestion", "")
                    ))
        except Exception as e:
            print(f"  LLM 审核出错: {e}")
        return issues

    def _count_assets(self, content: str) -> int:
        return len(re.findall(r'<img\s+|<figure', content, re.IGNORECASE))

    def _generate_summary(self, issues: list[QAIssue], passed: bool) -> str:
        if not issues: return "文档审核通过。"
        error_count = sum(1 for i in issues if i.severity == QASeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == QASeverity.WARNING)
        parts = []
        if error_count: parts.append(f"{error_count} 个错误")
        if warning_count: parts.append(f"{warning_count} 个警告")
        return f"审核{'未通过' if not passed else '通过'}，发现 {', '.join(parts)}。"


# ============================================================================
# 语义摘要提取
# ============================================================================

SEMANTIC_SUMMARY_PROMPT = """请为以下技术文档章节提取语义摘要，用于项目档案和后续复用。

## 文档内容

```markdown
{content}
```

## 输出格式

请以 JSON 格式输出：
```json
{{
  "title": "章节标题",
  "core_concepts": ["核心概念1", "核心概念2"],
  "key_terms": [
    {{"term": "术语", "definition": "定义"}}
  ],
  "visual_assets": [
    {{"id": "资产ID", "purpose": "用途描述"}}
  ],
  "dependencies": ["前置知识/依赖章节"],
  "summary": "200字以内的章节摘要"
}}
```

**注意**：只输出 JSON，不要其他内容。
"""


@dataclass
class SemanticSummary:
    """语义摘要"""
    title: str
    core_concepts: list[str]
    key_terms: list[dict]
    visual_assets: list[dict]
    dependencies: list[str]
    summary: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "core_concepts": self.core_concepts,
            "key_terms": self.key_terms,
            "visual_assets": self.visual_assets,
            "dependencies": self.dependencies,
            "summary": self.summary
        }


async def extract_semantic_summary(
    content: str,
    client: Optional[GeminiClient] = None
) -> Optional[SemanticSummary]:
    """
    提取章节的语义摘要

    Args:
        content: Markdown 内容
        client: Gemini 客户端

    Returns:
        语义摘要或 None
    """
    if client is None:
        client = GeminiClient()

    prompt = SEMANTIC_SUMMARY_PROMPT.format(content=content)

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="你是一位专业的技术文档分析师。请提取文档的核心语义信息。",
            temperature=0.3
        )

        if not response.success:
            print(f"语义摘要提取失败: {response.error}")
            return None

        # Robust extraction
        data = response.json_data
        if not data:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                data = json.loads(json_match.group())

        if data:
            return SemanticSummary(
                title=data.get("title", ""),
                core_concepts=data.get("core_concepts", []),
                key_terms=data.get("key_terms", []),
                visual_assets=data.get("visual_assets", []),
                dependencies=data.get("dependencies", []),
                summary=data.get("summary", "")
            )

    except Exception as e:
        print(f"语义摘要提取出错: {e}")

    return None


def save_semantic_summary(summary: SemanticSummary, output_path: Path):
    """保存语义摘要到文件"""
    output_path.write_text(
        json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
