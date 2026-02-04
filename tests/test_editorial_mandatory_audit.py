import unittest
from unittest.mock import MagicMock, AsyncMock
from src.agents.editorial_qa_agent import EditorialQAAgent
from src.core.types import AgentState, AssetEntry, AssetSource, AssetPriority, UniversalAssetRegistry

class TestEditorialMandatoryAudit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = EditorialQAAgent(client=self.mock_client)
        self.uar = UniversalAssetRegistry()
        
        # Create a mandatory asset
        self.mandatory_asset = AssetEntry(
            id="m-heart",
            source=AssetSource.USER,
            priority=AssetPriority.MANDATORY,
            semantic_label="Heart"
        )
        self.uar.assets[self.mandatory_asset.id] = self.mandatory_asset

    async def test_audit_fails_on_missing_mandatory_asset(self):
        """验证如果正文中缺少 Mandatory 资产，QA 审核是否失败"""
        state = AgentState(
            job_id="test_job",
            workspace_path=".",
            asset_registry=self.uar
        )
        
        # Content MISSING 'm-heart'
        content = "This text doesn't have the mandatory heart image."
        namespace = "s1"
        
        # Mock LLM to approve text but our local validator should catch it
        self.mock_client.generate_async.return_value = MagicMock(
            success=True,
            text='{"passed": true, "issues": [], "summary": "Approved by LLM"}'
        )

        new_state, report, updated_content = await self.agent.run_async(state, content, namespace)

        # Verify
        self.assertFalse(report.passed, "Audit should fail if mandatory asset is missing.")
        has_mandatory_issue = any(i.message and "缺少强制性资产" in i.message for i in report.issues)
        self.assertTrue(has_mandatory_issue, "Report should contain mandatory asset issue.")

if __name__ == "__main__":
    unittest.main()
