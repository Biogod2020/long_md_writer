import pytest
from pathlib import Path
from src.core.types import AgentState, AssetEntry, AssetSource, AssetPriority, AssetVQAStatus
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.agents.asset_management.models import VisualDirective

@pytest.fixture
def temp_workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "agent_generated").mkdir()
    (ws / "agent_sourced").mkdir()
    (ws / "md").mkdir()
    return ws

@pytest.mark.asyncio
async def test_skip_existing_asset(temp_workspace):
    # 1. Setup State and UAR
    job_id = "test_job"
    state = AgentState(
        job_id=job_id,
        workspace_path=str(temp_workspace),
        uar_path=str(temp_workspace / "assets.json")
    )
    uar = state.initialize_uar()
    
    # 2. Pre-create a physical asset and register it
    asset_id = "v1"
    svg_content = "<svg>mock</svg>"
    svg_file = temp_workspace / "agent_generated" / f"{asset_id}.svg"
    svg_file.write_text(svg_content)
    
    asset = AssetEntry(
        id=asset_id,
        source=AssetSource.AI,
        local_path=str(svg_file.relative_to(temp_workspace)),
        semantic_label="Mock SVG",
        content_hash="mock_hash"
    )
    uar.register_immediate(asset)
    
    # 3. Create a directive for this asset
    directive = VisualDirective(raw_block=":::visual {\"id\": \"v1\"}\n:::", start_pos=0, end_pos=10)
    directive.id = asset_id
    
    # 4. Initialize Agent
    agent = AssetFulfillmentAgent()
    
    # 5. Check if asset exists (This is the new method we need to implement)
    # Note: We are testing the intended behavior of _check_asset_exists
    exists = await agent._check_asset_exists(directive, uar, temp_workspace)
    
    assert exists is True
    assert directive.fulfilled is True
    assert "agent_generated/v1.svg" in directive.result_html

@pytest.mark.asyncio
async def test_no_skip_non_existent_asset(temp_workspace):
    state = AgentState(
        job_id="test_job",
        workspace_path=str(temp_workspace)
    )
    uar = state.initialize_uar()
    
    directive = VisualDirective(raw_block=":::visual {\"id\": \"v2\"}\n:::", start_pos=0, end_pos=10)
    directive.id = "v2"
    
    agent = AssetFulfillmentAgent()
    exists = await agent._check_asset_exists(directive, uar, temp_workspace)
    
    assert exists is False
    assert directive.fulfilled is False
