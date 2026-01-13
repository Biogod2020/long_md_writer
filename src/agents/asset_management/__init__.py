"""
Asset Management Package

SOTA 2.0 资产管理模块，包含：
- AssetIndexerAgent: 资产索引器 (Phase 0)
- AssetFulfillmentAgent: 资产履约器 (Phase D)
- AssetCriticAgent: 资产审计器 (Phase D)
"""

from .indexer import AssetIndexerAgent, index_user_assets, index_user_assets_async
from .fulfillment import AssetFulfillmentAgent
from .critic import AssetCriticAgent

__all__ = [
    "AssetIndexerAgent",
    "AssetFulfillmentAgent",
    "AssetCriticAgent",
    "index_user_assets",
    "index_user_assets_async",
]
