import unittest
from unittest.mock import MagicMock, AsyncMock
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AssetEntry, AssetSource, UniversalAssetRegistry
from enum import Enum

class AssetPriority(str, Enum):
    MANDATORY = "MANDATORY"
    SUGGESTED = "SUGGESTED"
    AUTONOMOUS = "AUTONOMOUS"

class TestModularAssetScoring(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = AssetFulfillmentAgent(client=self.mock_client)
        self.uar = UniversalAssetRegistry()

    async def test_fair_scoring_prompt(self):
        """验证评分提示词是否公平（不含优先级偏见）"""
        asset = AssetEntry(
            id="test-asset-1",
            source=AssetSource.USER,
            semantic_label="测试图片",
            priority=AssetPriority.MANDATORY
        )
        
        self.uar.assets[asset.id] = asset

        self.mock_client.generate_async.return_value = MagicMock(
            success=True,
            text='{"score": 95, "reason": "Pure semantic match"}'
        )

        intent = "需要一张测试图片"
        await self.agent._calculate_reuse_score(intent, asset, self.uar)

        prompt_text = self.mock_client.generate_async.call_args[1]['prompt']
        
        # 验证提示词中不包含优先级偏见信息
        self.assertNotIn("优先级", prompt_text)
        self.assertNotIn("最高", prompt_text)
        self.assertIn("内容一致性", prompt_text)

if __name__ == "__main__":
    unittest.main()
