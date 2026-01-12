"""
EditorialQAAgent: SOTA 2.0 Phase E 全量语义综审

核心职责：
1. 全量多模态终审 - 接收完整文本与资产流
2. 校验 <img style="..."> 裁切范围是否准确命中文字焦点
3. 语义一致性检查 - 确保图文描述对应
4. 生成审计报告与修复建议

执行时机：
- 在 AssetFulfillment 完成后、HTML 转换前执行
"""

import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState, AssetQualityLevel


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

EDITORIAL_QA_PROMPT = """你是一位专业的技术文档编辑审核员。请对以下 Markdown 内容进行全面的语义审核。

## 审核重点

1. **图文一致性**：检查每个 `<img>` 或 `<figure>` 标签：
   - alt 文本是否准确描述图片内容
   - figcaption 是否与上下文语义一致
   - 图片是否出现在合适的位置（紧跟相关段落）

2. **裁切准确性**：如果 img 标签包含 `style="object-position: ..."`：
   - 检查裁切位置是否合理指向描述的焦点区域
   - 百分比值是否在合理范围内

3. **语义连贯性**：
   - 段落之间的逻辑过渡是否自然
   - 专业术语使用是否一致
   - 引用和参照是否准确（如 [REF:xxx]）

4. **资产完整性**：
   - 是否存在未履约的 :::visual 指令
   - 图片路径是否看起来有效

## 待审核内容

```markdown
{content}
```

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
- 只输出 JSON，不要其他内容
- 如果没有问题，issues 为空数组，passed 为 true
- severity=error 的问题会导致 passed=false
"""


class EditorialQAAgent:
    """
    全量语义综审 Agent

    负责在 HTML 转换前进行最终的语义和质量审核
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        skip_llm_review: bool = False,
        strict_mode: bool = True
    ):
        """
        初始化 Editorial QA Agent

        Args:
            client: Gemini API 客户端
            skip_llm_review: 跳过 LLM 审核（仅执行本地检查）
            strict_mode: 严格模式（warning 也会导致失败）
        """
        self.client = client or GeminiClient()
        self.skip_llm_review = skip_llm_review
        self.strict_mode = strict_mode

    async def run_async(
        self,
        state: AgentState,
        content: str,
        namespace: str
    ) -> tuple[AgentState, QAReport]:
        """
        异步执行 QA 审核

        Args:
            state: Agent 状态
            content: 待审核的 Markdown 内容
            namespace: 章节命名空间

        Returns:
            (更新后的状态, QA报告)
        """
        print(f"[EditorialQA] 开始全量语义审核 (namespace: {namespace})")

        issues: list[QAIssue] = []

        # 1. 本地静态检查
        local_issues = self._run_local_checks(content, namespace, state)
        issues.extend(local_issues)
        print(f"  本地检查发现 {len(local_issues)} 个问题")

        # 2. LLM 语义审核
        if not self.skip_llm_review:
            llm_issues = await self._run_llm_review(content)
            issues.extend(llm_issues)
            print(f"  LLM 审核发现 {len(llm_issues)} 个问题")

        # 3. 统计资产
        asset_count = self._count_assets(content)

        # 4. 判断是否通过
        error_count = sum(1 for i in issues if i.severity == QASeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == QASeverity.WARNING)

        if self.strict_mode:
            passed = error_count == 0 and warning_count == 0
        else:
            passed = error_count == 0

        # 5. 生成报告
        report = QAReport(
            passed=passed,
            issues=issues,
            summary=self._generate_summary(issues, passed),
            asset_count=asset_count,
            reviewed_count=asset_count
        )

        print(f"  审核结果: {'✓ 通过' if passed else '✗ 未通过'}")
        print(f"  问题统计: {error_count} 错误, {warning_count} 警告")

        return state, report

    def run(
        self,
        state: AgentState,
        content: str,
        namespace: str
    ) -> tuple[AgentState, QAReport]:
        """同步版本"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 在异步上下文中，只执行本地检查
            issues = self._run_local_checks(content, namespace, state)
            asset_count = self._count_assets(content)
            error_count = sum(1 for i in issues if i.severity == QASeverity.ERROR)
            passed = error_count == 0
            report = QAReport(
                passed=passed,
                issues=issues,
                summary=self._generate_summary(issues, passed),
                asset_count=asset_count,
                reviewed_count=asset_count
            )
            return state, report
        except RuntimeError:
            return asyncio.run(self.run_async(state, content, namespace))

    def _run_local_checks(
        self,
        content: str,
        namespace: str,
        state: AgentState
    ) -> list[QAIssue]:
        """执行本地静态检查"""
        issues = []

        # 检查未履约的 :::visual
        issues.extend(self._check_unfulfilled_visuals(content))

        # 检查 img 标签
        issues.extend(self._check_img_tags(content, state))

        # 检查 figure 标签
        issues.extend(self._check_figure_tags(content))

        # 检查断裂的引用
        issues.extend(self._check_broken_refs(content))

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
                suggestion="请运行 AssetFulfillmentAgent 处理此指令",
                context={"directive": match.group(0)[:100]}
            ))

        return issues

    def _check_img_tags(self, content: str, state: AgentState) -> list[QAIssue]:
        """检查 img 标签"""
        issues = []

        # 匹配 img 标签
        img_pattern = r'<img\s+([^>]+)>'

        for match in re.finditer(img_pattern, content, re.IGNORECASE):
            attrs_str = match.group(1)

            # 检查 alt 属性
            if 'alt=' not in attrs_str.lower():
                issues.append(QAIssue(
                    issue_type=QAIssueType.MISSING_ALT,
                    severity=QASeverity.WARNING,
                    location=f"位置 {match.start()}",
                    message="img 标签缺少 alt 属性",
                    suggestion="添加描述性的 alt 文本以提高可访问性"
                ))

            # 检查 src 属性
            src_match = re.search(r'src=["\']([^"\']+)["\']', attrs_str)
            if src_match:
                src = src_match.group(1)
                # 检查是否是有效路径格式
                if not src.startswith(('http', '/', 'data:', 'generated_assets/')):
                    if not src.startswith(('assets/', './')):
                        issues.append(QAIssue(
                            issue_type=QAIssueType.BROKEN_REFERENCE,
                            severity=QASeverity.WARNING,
                            location=f"位置 {match.start()}",
                            message=f"img src 路径可能无效: {src}",
                            suggestion="确保图片路径正确，使用相对路径或绝对路径"
                        ))

            # 检查 object-position 样式
            style_match = re.search(r'style=["\']([^"\']+)["\']', attrs_str)
            if style_match:
                style = style_match.group(1)
                if 'object-position' in style:
                    # 验证百分比值（支持负数）
                    pos_match = re.search(r'object-position:\s*(-?\d+)%\s+(-?\d+)%', style)
                    if pos_match:
                        x, y = int(pos_match.group(1)), int(pos_match.group(2))
                        if x < 0 or x > 100 or y < 0 or y > 100:
                            issues.append(QAIssue(
                                issue_type=QAIssueType.CROP_MISMATCH,
                                severity=QASeverity.ERROR,
                                location=f"位置 {match.start()}",
                                message=f"object-position 值超出范围: {x}% {y}%",
                                suggestion="确保百分比值在 0-100 之间"
                            ))

        return issues

    def _check_figure_tags(self, content: str) -> list[QAIssue]:
        """检查 figure 标签"""
        issues = []

        # 检查 figure 是否有 figcaption
        figure_pattern = r'<figure[^>]*>([\s\S]*?)</figure>'

        for match in re.finditer(figure_pattern, content, re.IGNORECASE):
            figure_content = match.group(1)

            if '<figcaption' not in figure_content.lower():
                issues.append(QAIssue(
                    issue_type=QAIssueType.ACCESSIBILITY_ISSUE,
                    severity=QASeverity.INFO,
                    location=f"位置 {match.start()}",
                    message="figure 标签缺少 figcaption",
                    suggestion="添加 figcaption 以提供图片说明"
                ))

        return issues

    def _check_broken_refs(self, content: str) -> list[QAIssue]:
        """检查断裂的引用"""
        issues = []

        # 检查 [REF:xxx] 格式的引用
        ref_pattern = r'\[REF:([^\]]+)\]'

        for match in re.finditer(ref_pattern, content):
            ref_id = match.group(1)
            # 这里只是标记，实际验证需要全局上下文
            # 暂时只检查格式
            if not re.match(r'^[a-z0-9-]+$', ref_id):
                issues.append(QAIssue(
                    issue_type=QAIssueType.BROKEN_REFERENCE,
                    severity=QASeverity.WARNING,
                    location=f"位置 {match.start()}",
                    message=f"引用 ID 格式不规范: {ref_id}",
                    suggestion="使用小写字母、数字和连字符组成的 ID"
                ))

        return issues

    async def _run_llm_review(self, content: str) -> list[QAIssue]:
        """使用 LLM 进行语义审核"""
        issues = []

        prompt = EDITORIAL_QA_PROMPT.format(content=content)  # Full content - no truncation

        try:
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一位专业的技术文档编辑审核员。请仔细审核文档质量。",
                temperature=0.2
            )

            if not response.success:
                print(f"  LLM 审核调用失败: {response.error}")
                return issues

            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                data = json.loads(json_match.group())

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

        except json.JSONDecodeError as e:
            print(f"  解析 LLM 响应失败: {e}")
        except Exception as e:
            print(f"  LLM 审核出错: {e}")

        return issues

    def _count_assets(self, content: str) -> int:
        """统计内容中的资产数量"""
        img_count = len(re.findall(r'<img\s+', content, re.IGNORECASE))
        figure_count = len(re.findall(r'<figure', content, re.IGNORECASE))
        return max(img_count, figure_count)

    def _generate_summary(self, issues: list[QAIssue], passed: bool) -> str:
        """生成审核摘要"""
        if not issues:
            return "文档审核通过，未发现任何问题。"

        error_count = sum(1 for i in issues if i.severity == QASeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == QASeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == QASeverity.INFO)

        parts = []
        if error_count:
            parts.append(f"{error_count} 个错误")
        if warning_count:
            parts.append(f"{warning_count} 个警告")
        if info_count:
            parts.append(f"{info_count} 个提示")

        status = "未通过" if not passed else "通过（有提示）"
        return f"审核{status}，发现 {', '.join(parts)}。"


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

    prompt = SEMANTIC_SUMMARY_PROMPT.format(content=content)  # Full content - no truncation

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="你是一位专业的技术文档分析师。请提取文档的核心语义信息。",
            temperature=0.3
        )

        if not response.success:
            print(f"语义摘要提取失败: {response.error}")
            return None

        json_match = re.search(r'\{[\s\S]*\}', response.text)
        if json_match:
            data = json.loads(json_match.group())
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
