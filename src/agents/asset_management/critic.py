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

from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from ...core.gemini_client import GeminiClient
from ...core.types import (
    AgentState,
    AssetEntry,
)
from .processors.audit import audit_image_async, audit_svg_visual_async, check_svg_syntax


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


from .processors.audit import audit_image_async, audit_svg_visual_async, check_svg_syntax


class AssetCriticAgent:
    """
    资产审计 Agent
    
    支持双路交叉验证：对 SVG 同时进行代码分析和渲染图视觉分析。
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
        """异步审计单个资产"""
        if self.skip_audit:
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.PASS,
                score=1.0,
                issues=[],
                suggestions=[],
                quality_assessment="审计已跳过 (测试模式)"
            )

        asset_path = Path(asset.local_path) if asset.local_path else None
        if asset_path and not asset_path.is_absolute() and workspace_path:
            asset_path = workspace_path / asset.local_path

        if asset_path is None or not asset_path.exists():
            return AssetAuditReport(
                asset_id=asset.id,
                result=AuditResult.FAIL,
                score=0.0,
                issues=[f"资产文件不存在: {asset_path}"],
                suggestions=["检查资产是否正确生成"],
            )

        try:
            if asset_path.suffix.lower() == ".svg":
                svg_code = asset_path.read_text(encoding="utf-8")
                syntax_issues = check_svg_syntax(svg_code)
                if syntax_issues:
                    return AssetAuditReport(asset_id=asset.id, result=AuditResult.FAIL, score=0.0, issues=syntax_issues, suggestions=["修复语法"])
                
                # SOTA 2.0: 双路交叉验证 (代码 + 渲染图)
                audit_data = await audit_svg_visual_async(self.client, svg_code, intent_description, asset_path)

            else:
                audit_data = await audit_image_async(self.client, asset_path, intent_description)

            if audit_data:
                return self._parse_audit_data(asset.id, audit_data)
            else:
                return AssetAuditReport(asset_id=asset.id, result=AuditResult.FAIL, score=0.0, issues=["审计 API 未返回有效数据"], suggestions=["检查连接"])

        except Exception as e:
            return AssetAuditReport(asset_id=asset.id, result=AuditResult.FAIL, score=0.0, issues=[f"审计出错: {e}"], suggestions=["检查 API"])

    def audit_asset(
        self,
        asset: AssetEntry,
        intent_description: str,
        workspace_path: Optional[Path] = None
    ) -> AssetAuditReport:
        """同步审计单个资产（向后兼容）"""
        import asyncio
        try:
            asyncio.get_running_loop()
            if self.skip_audit:
                return AssetAuditReport(asset_id=asset.id, result=AuditResult.PASS, score=1.0, issues=[], suggestions=[], quality_assessment="审计已跳过")
            return AssetAuditReport(asset_id=asset.id, result=AuditResult.NEEDS_REVISION, score=0.0, issues=["在异步上下文中调用了同步方法"], suggestions=["请使用 audit_asset_async"])
        except RuntimeError:
            return asyncio.run(self.audit_asset_async(asset, intent_description, workspace_path))

    def _parse_audit_data(self, asset_id: str, data: dict) -> AssetAuditReport:
        """解析审计数据"""
        score = data.get("overall_score", 0) / 100.0
        result_str = data.get("result", "").upper()
        if result_str == "PASS" or score >= self.pass_threshold: result = AuditResult.PASS
        elif result_str == "NEEDS_REVISION" or score >= self.revision_threshold: result = AuditResult.NEEDS_REVISION
        else: result = AuditResult.FAIL
        return AssetAuditReport(asset_id=asset_id, result=result, score=score, issues=data.get("issues", []), suggestions=data.get("suggestions", []), quality_assessment=data.get("quality_assessment"))

    async def batch_audit_async(self, assets: list[tuple[AssetEntry, str]], workspace_path: Optional[Path] = None) -> list[AssetAuditReport]:
        """异步批量审计"""
        reports = []
        for asset, intent in assets:
            report = await self.audit_asset_async(asset, intent, workspace_path)
            reports.append(report)
            print(f"  {'✓' if report.is_acceptable else '✗'} {asset.id}: {report.result.value} ({report.score:.0%})")
        return reports


# ============================================================================
# 便捷函数
# ============================================================================

async def audit_generated_assets_async(
    state: AgentState,
    assets_with_intents: list[tuple[AssetEntry, str]],
    skip_audit: bool = False
) -> tuple[list[AssetAuditReport], list[AssetEntry]]:
    """异步审计生成的资产"""
    critic = AssetCriticAgent(skip_audit=skip_audit)
    workspace_path = Path(state.workspace_path) if state.workspace_path else None
    reports = await critic.batch_audit_async(assets_with_intents, workspace_path)
    failed_assets = [asset for (asset, _), report in zip(assets_with_intents, reports) if not report.is_acceptable]
    return reports, failed_assets
