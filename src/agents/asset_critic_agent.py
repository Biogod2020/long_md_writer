"""
AssetCriticAgent: SOTA 2.0 Phase D 资产审计员

核心职责：
1. 视觉匹配审计 - 验证生成的资产是否符合意图描述
2. 质量检查 - 评估资产的视觉质量
3. 触发修复循环 - 若审计失败，提供反馈供重新生成

执行时机：
- 在 AssetFulfillmentAgent 生成每个资产后执行
- 在 HTML 转换前完成所有审计
"""

import re
import json
import base64
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from ..core.gemini_client import GeminiClient
from ..core.types import (
    AgentState,
    AssetEntry,
    AssetQualityLevel,
)


class AuditResult(Enum):
    """审计结果"""
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVISION = "needs_revision"


@dataclass
class AssetAuditReport:
    """资产审计报告"""
    asset_id: str
    result: AuditResult
    score: float  # 0-1 匹配分数
    issues: list[str]
    suggestions: list[str]
    quality_assessment: Optional[str] = None

    @property
    def is_acceptable(self) -> bool:
        return self.result == AuditResult.PASS

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "result": self.result.value,
            "score": self.score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "quality_assessment": self.quality_assessment,
        }


# ============================================================================
# 审计提示词
# ============================================================================

VISUAL_AUDIT_PROMPT = """你是一个专业的视觉内容审计员。请评估这张图片是否符合以下意图描述。

## 意图描述
{intent_description}

## 评估标准
1. **内容匹配度** (0-100分)
   - 图片是否准确表达了意图描述中的核心概念？
   - 关键元素是否都呈现？

2. **视觉质量** (0-100分)
   - 清晰度、对比度、配色是否合适？
   - 是否存在模糊、失真、水印等问题？

3. **教学适用性** (0-100分)
   - 是否适合用于教学/文档？
   - 标注、文字是否清晰易读？

## 输出格式
请严格按照以下 JSON 格式输出：

```json
{{
  "content_match_score": 85,
  "visual_quality_score": 90,
  "teaching_suitability_score": 80,
  "overall_score": 85,
  "result": "PASS|FAIL|NEEDS_REVISION",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "quality_assessment": "简短的质量总结"
}}
```

**评判标准**:
- overall_score >= 75: PASS
- overall_score >= 50: NEEDS_REVISION
- overall_score < 50: FAIL
"""

SVG_AUDIT_PROMPT = """你是一个专业的 SVG 图形审计员。请评估这段 SVG 代码是否符合以下意图描述。

## 意图描述
{intent_description}

## SVG 代码
```svg
{svg_code}
```

## 评估标准
1. **内容匹配度** (0-100分)
   - SVG 是否准确表达了意图描述中的核心概念？
   - 关键元素是否都呈现？

2. **代码质量** (0-100分)
   - SVG 语法是否正确？
   - 是否使用了合理的元素和属性？

3. **视觉效果** (0-100分)
   - 配色、布局是否合理？
   - 文字是否清晰可读？

## 输出格式
请严格按照以下 JSON 格式输出：

```json
{{
  "content_match_score": 85,
  "code_quality_score": 90,
  "visual_effect_score": 80,
  "overall_score": 85,
  "result": "PASS|FAIL|NEEDS_REVISION",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "quality_assessment": "简短的质量总结"
}}
```

**评判标准**:
- overall_score >= 75: PASS
- overall_score >= 50: NEEDS_REVISION
- overall_score < 50: FAIL
"""


class AssetCriticAgent:
    """
    资产审计 Agent

    负责验证生成的资产是否符合意图描述
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        pass_threshold: float = 0.75,
        revision_threshold: float = 0.50,
        skip_audit: bool = False
    ):
        """
        初始化资产审计员

        Args:
            client: Gemini API 客户端
            pass_threshold: 通过阈值 (0-1)
            revision_threshold: 需修订阈值 (0-1)
            skip_audit: 跳过审计 (用于测试)
        """
        self.client = client or GeminiClient()
        self.pass_threshold = pass_threshold
        self.revision_threshold = revision_threshold
        self.skip_audit = skip_audit

    async def audit_asset_async(
        self,
        asset: AssetEntry,
        intent_description: str,
        workspace_path: Optional[Path] = None
    ) -> AssetAuditReport:
        """
        异步审计单个资产

        Args:
            asset: 资产条目
            intent_description: 意图描述
            workspace_path: 工作目录 (用于解析相对路径)

        Returns:
            AssetAuditReport
        """
        if self.skip_audit:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.PASS,
                score=1.0,
                issues=[],
                suggestions=[],
                quality_assessment="审计已跳过 (测试模式)"
            )

        # 确定资产路径
        asset_path = Path(asset.local_path) if asset.local_path else None
        if asset_path and not asset_path.is_absolute() and workspace_path:
            asset_path = workspace_path / asset.local_path

        if asset_path is None:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=["资产路径为空"],
                suggestions=["检查资产是否正确生成"],
            )

        # 根据资产类型选择审计方式
        if asset_path.suffix.lower() == ".svg":
            return await self._audit_svg_async(asset, intent_description, asset_path)
        else:
            return await self._audit_image_async(asset, intent_description, asset_path)

    def audit_asset(
        self,
        asset: AssetEntry,
        intent_description: str,
        workspace_path: Optional[Path] = None
    ) -> AssetAuditReport:
        """
        同步审计单个资产（向后兼容）

        注意：在异步上下文中请使用 audit_asset_async
        """
        import asyncio
        try:
            asyncio.get_running_loop()
            # 在异步上下文中，返回不可接受的结果，避免静默通过
            if self.skip_audit:
                return AssetAuditReport(
                    asset_id=asset.id,
                    result=AuditResult.PASS,
                    score=1.0,
                    issues=[],
                    suggestions=[],
                    quality_assessment="审计已跳过 (异步上下文)"
                )
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.NEEDS_REVISION,
                score=0.0,
                issues=["在异步上下文中调用了同步方法"],
                suggestions=["请使用 audit_asset_async 方法"],
                quality_assessment="未能完成完整审计"
            )
        except RuntimeError:
            # 不在异步上下文中，可以正常运行
            return asyncio.run(self.audit_asset_async(asset, intent_description, workspace_path))

    def _audit_image(
        self,
        asset: AssetEntry,
        intent_description: str,
        image_path: Path
    ) -> AssetAuditReport:
        """审计图片资产 (使用 VLM)"""
        if not image_path.exists():
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"图片文件不存在: {image_path}"],
                suggestions=["检查文件路径是否正确"],
            )

        # 读取并编码图片
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # 确定 MIME 类型
        ext = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")

        # 构建多模态请求
        prompt = VISUAL_AUDIT_PROMPT.format(intent_description=intent_description)
        parts = [
            {"text": prompt},
            {"inlineData": {"mimeType": mime_type, "data": image_data}},
        ]

        try:
            response = self.client.generate(
                parts=parts,
                system_instruction="你是一个专业的视觉内容审计员。请严格评估并输出 JSON 格式。"
            )

            if not response.success:
                return AssetAuditReport(
                    asset_id=asset.id,
                    result=AuditResult.FAIL,
                    score=0.0,
                    issues=[f"审计 API 返回失败: {response.error}"],
                    suggestions=["检查 API 连接和响应内容"],
                )

            return self._parse_audit_response(asset.id, response.text)

        except Exception as e:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"审计过程出错: {e}"],
                suggestions=["检查 API 连接和图片格式"],
            )

    async def _audit_image_async(
        self,
        asset: AssetEntry,
        intent_description: str,
        image_path: Path
    ) -> AssetAuditReport:
        """异步审计图片资产 (使用 VLM)"""
        if not image_path.exists():
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"图片文件不存在: {image_path}"],
                suggestions=["检查文件路径是否正确"],
            )

        # 读取并编码图片
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # 确定 MIME 类型
        ext = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")

        # 构建多模态请求
        prompt = VISUAL_AUDIT_PROMPT.format(intent_description=intent_description)
        parts = [
            {"text": prompt},
            {"inlineData": {"mimeType": mime_type, "data": image_data}},
        ]

        try:
            response = await self.client.generate_async(
                parts=parts,
                system_instruction="你是一个专业的视觉内容审计员。请严格评估并输出 JSON 格式。"
            )

            if not response.success:
                return AssetAuditReport(
                    asset_id=asset.id,
                    result=AuditResult.FAIL,
                    score=0.0,
                    issues=[f"审计 API 返回失败: {response.error}"],
                    suggestions=["检查 API 连接和响应内容"],
                )

            return self._parse_audit_response(asset.id, response.text)

        except Exception as e:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"审计过程出错: {e}"],
                suggestions=["检查 API 连接和图片格式"],
            )

    def _audit_svg(
        self,
        asset: AssetEntry,
        intent_description: str,
        svg_path: Path
    ) -> AssetAuditReport:
        """审计 SVG 资产 (使用代码分析)"""
        if not svg_path.exists():
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"SVG 文件不存在: {svg_path}"],
                suggestions=["检查文件路径是否正确"],
            )

        # 读取 SVG 代码
        svg_code = svg_path.read_text(encoding="utf-8")

        # 基本语法检查
        syntax_issues = self._check_svg_syntax(svg_code)
        if syntax_issues:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=syntax_issues,
                suggestions=["修复 SVG 语法错误"],
            )

        # 使用 LLM 评估内容匹配度
        prompt = SVG_AUDIT_PROMPT.format(
            intent_description=intent_description,
            svg_code=svg_code  # Full content - no truncation
        )

        try:
            response = self.client.generate(
                prompt=prompt,
                system_instruction="你是一个专业的 SVG 图形审计员。请严格评估并输出 JSON 格式。"
            )

            if not response.success:
                return AssetAuditReport(
                    asset_id=asset.id,
                    result=AuditResult.FAIL,
                    score=0.0,
                    issues=[f"审计 API 返回失败: {response.error}"],
                    suggestions=["检查 API 连接和响应内容"],
                )

            return self._parse_audit_response(asset.id, response.text)

        except Exception as e:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"审计过程出错: {e}"],
                suggestions=["检查 API 连接"],
            )

    async def _audit_svg_async(
        self,
        asset: AssetEntry,
        intent_description: str,
        svg_path: Path
    ) -> AssetAuditReport:
        """异步审计 SVG 资产 (使用代码分析)"""
        if not svg_path.exists():
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"SVG 文件不存在: {svg_path}"],
                suggestions=["检查文件路径是否正确"],
            )

        # 读取 SVG 代码
        svg_code = svg_path.read_text(encoding="utf-8")

        # 基本语法检查
        syntax_issues = self._check_svg_syntax(svg_code)
        if syntax_issues:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=syntax_issues,
                suggestions=["修复 SVG 语法错误"],
            )

        # 使用 LLM 评估内容匹配度
        prompt = SVG_AUDIT_PROMPT.format(
            intent_description=intent_description,
            svg_code=svg_code  # Full content - no truncation
        )

        try:
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一个专业的 SVG 图形审计员。请严格评估并输出 JSON 格式。"
            )

            if not response.success:
                return AssetAuditReport(
                    asset_id=asset.id,
                    result=AuditResult.FAIL,
                    score=0.0,
                    issues=[f"审计 API 返回失败: {response.error}"],
                    suggestions=["检查 API 连接和响应内容"],
                )

            return self._parse_audit_response(asset.id, response.text)

        except Exception as e:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"审计过程出错: {e}"],
                suggestions=["检查 API 连接"],
            )

    def _check_svg_syntax(self, svg_code: str) -> list[str]:
        """检查 SVG 基本语法"""
        issues = []

        # 检查是否有 <svg> 标签
        if not re.search(r'<svg[^>]*>', svg_code, re.IGNORECASE):
            issues.append("缺少 <svg> 开始标签")

        if not re.search(r'</svg>', svg_code, re.IGNORECASE):
            issues.append("缺少 </svg> 结束标签")

        # 检查 xmlns
        if '<svg' in svg_code and 'xmlns' not in svg_code:
            issues.append("缺少 xmlns 命名空间声明")

        # 简单的标签平衡检查 - 只检查必须成对出现的 SVG 容器元素
        container_elements = ['svg', 'g', 'defs', 'symbol', 'text', 'tspan', 'clipPath', 'mask', 'pattern', 'marker', 'linearGradient', 'radialGradient', 'filter', 'switch', 'foreignObject']

        for elem in container_elements:
            # 计算开始标签: <elem ...> 但排除 <elem ... />
            # 使用更宽松的方式: 先匹配所有 <elem...>，再减去自闭合的
            all_open = re.findall(rf'<{elem}(?:\s[^>]*)?>',  svg_code, re.IGNORECASE)
            self_closing = re.findall(rf'<{elem}(?:\s[^>]*)?/>', svg_code, re.IGNORECASE)
            open_count = len(all_open) - len(self_closing)

            # 计算结束标签
            close_count = len(re.findall(rf'</{elem}\s*>', svg_code, re.IGNORECASE))

            if open_count != close_count:
                issues.append(f"<{elem}> 标签未正确闭合 (开: {open_count}, 闭: {close_count})")

        return issues

    def _extract_json_payload(self, response_text: str) -> Optional[str]:
        """提取 JSON 响应内容 (优先 code block, 否则平衡大括号)"""
        block_match = re.search(r'```json\s*([\s\S]*?)```', response_text)
        if block_match:
            return block_match.group(1).strip()

        start = response_text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(response_text)):
            ch = response_text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return response_text[start:i + 1]

        return None

    def _parse_audit_response(self, asset_id: str, response_text: str) -> AssetAuditReport:
        """解析审计响应"""
        try:
            # 提取 JSON
            payload = self._extract_json_payload(response_text)
            if not payload:
                raise ValueError("未找到 JSON 响应")

            data = json.loads(payload)

            # 解析分数
            overall_score = data.get("overall_score", 0) / 100.0

            # 确定结果
            result_str = data.get("result", "").upper()
            if result_str == "PASS" or overall_score >= self.pass_threshold:
                result = AuditResult.PASS
            elif result_str == "NEEDS_REVISION" or overall_score >= self.revision_threshold:
                result = AuditResult.NEEDS_REVISION
            else:
                result = AuditResult.FAIL

            return AssetAuditReport(
                asset_id=asset_id,
                result=result,
                score=overall_score,
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                quality_assessment=data.get("quality_assessment"),
            )

        except Exception as e:
            return AssetAuditReport(
                asset_id=asset_id,
                result=AuditResult.NEEDS_REVISION,
                score=0.5,
                issues=[f"解析审计响应失败: {e}"],
                suggestions=["人工检查资产质量"],
            )

    def batch_audit(
        self,
        assets: list[tuple[AssetEntry, str]],
        workspace_path: Optional[Path] = None
    ) -> list[AssetAuditReport]:
        """
        批量审计资产

        Args:
            assets: [(asset, intent_description), ...] 列表
            workspace_path: 工作目录

        Returns:
            审计报告列表
        """
        reports = []
        for asset, intent in assets:
            report = self.audit_asset(asset, intent, workspace_path)
            reports.append(report)
            print(f"  {'✓' if report.is_acceptable else '✗'} {asset.id}: {report.result.value} ({report.score:.0%})")
        return reports

    async def batch_audit_async(
        self,
        assets: list[tuple[AssetEntry, str]],
        workspace_path: Optional[Path] = None
    ) -> list[AssetAuditReport]:
        """异步批量审计资产"""
        reports = []
        for asset, intent in assets:
            report = await self.audit_asset_async(asset, intent, workspace_path)
            reports.append(report)
            print(f"  {'✓' if report.is_acceptable else '✗'} {asset.id}: {report.result.value} ({report.score:.0%})")
        return reports


# ============================================================================
# 便捷函数
# ============================================================================

def audit_generated_assets(
    state: AgentState,
    assets_with_intents: list[tuple[AssetEntry, str]],
    skip_audit: bool = False
) -> tuple[list[AssetAuditReport], list[AssetEntry]]:
    """
    审计生成的资产

    Returns:
        (所有审计报告, 失败的资产列表)
    """
    critic = AssetCriticAgent(skip_audit=skip_audit)
    workspace_path = Path(state.workspace_path) if state.workspace_path else None

    reports = critic.batch_audit(assets_with_intents, workspace_path)

    failed_assets = [
        asset for (asset, _), report in zip(assets_with_intents, reports)
        if not report.is_acceptable
    ]

    return reports, failed_assets


async def audit_generated_assets_async(
    state: AgentState,
    assets_with_intents: list[tuple[AssetEntry, str]],
    skip_audit: bool = False
) -> tuple[list[AssetAuditReport], list[AssetEntry]]:
    """
    异步审计生成的资产

    Returns:
        (所有审计报告, 失败的资产列表)
    """
    critic = AssetCriticAgent(skip_audit=skip_audit)
    workspace_path = Path(state.workspace_path) if state.workspace_path else None

    reports = await critic.batch_audit_async(assets_with_intents, workspace_path)

    failed_assets = [
        asset for (asset, _), report in zip(assets_with_intents, reports)
        if not report.is_acceptable
    ]

    return reports, failed_assets
