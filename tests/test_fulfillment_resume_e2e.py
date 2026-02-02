import pytest
import json
from src.core.types import AgentState, AssetEntry, AssetSource, AssetVQAStatus
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent

@pytest.fixture
def e2e_workspace(tmp_path):
    ws = tmp_path / "e2e_ws"
    ws.mkdir()
    (ws / "agent_generated").mkdir()
    (ws / "agent_sourced").mkdir()
    (ws / "md").mkdir()
    return ws

@pytest.mark.asyncio
async def test_fulfillment_resume_e2e(e2e_workspace):
    # 1. Setup Markdown with 3 directives
    md_content = """
# Section 1
:::visual {"id": "v1", "action": "GENERATE_SVG", "description": "Desc 1"}
:::
:::visual {"id": "v2", "action": "GENERATE_SVG", "description": "Desc 2"}
:::
:::visual {"id": "v3", "action": "GENERATE_SVG", "description": "Desc 3"}
:::
"""
    md_path = e2e_workspace / "md" / "sec-1.md"
    md_path.write_text(md_content, encoding="utf-8")
    
    state = AgentState(
        job_id="e2e_test",
        workspace_path=str(e2e_workspace),
        uar_path=str(e2e_workspace / "assets.json")
    )
    state.completed_md_sections = [str(md_path)]
    uar = state.initialize_uar()
    
    # 2. Simulate "Partial Completion" (Crash scenario)
    # We manually create v1 asset and register it to simulate it was done before crash
    v1_file = e2e_workspace / "agent_generated" / "v1.svg"
    v1_file.write_text("<svg>v1</svg>")
    
    asset_v1 = AssetEntry(
        id="v1",
        source=AssetSource.AI,
        local_path=str(v1_file.relative_to(e2e_workspace)),
        semantic_label="Desc 1",
        content_hash="h1"
    )
    uar.register_immediate(asset_v1)
    
    # Also create a .working file that already has v1 replaced
    working_path = md_path.with_suffix(md_path.suffix + ".working")
    working_content = md_content.replace(':::visual {"id": "v1", "action": "GENERATE_SVG", "description": "Desc 1"}\n:::', '<img src="agent_generated/v1.svg">')
    working_path.write_text(working_content, encoding="utf-8")
    
    # 3. Run Fulfillment (Resume)
    # It should skip v1 and only do v2, v3
    agent = AssetFulfillmentAgent(max_concurrency=2)
    
    # Mock _fulfill_svg_step to avoid real AI calls but still return result
    async def mock_fulfill_svg(d, uar, out_path, ns, ws_path, state, trace, target_file=None):
        file_path = out_path / f"{d.id}.svg"
        file_path.write_text(f"<svg>{d.id}</svg>")
        asset = AssetEntry(
            id=d.id, source=AssetSource.AI, local_path=str(file_path.relative_to(ws_path)),
            semantic_label=d.description, content_hash="mock",
            alt_text=d.description, tags=["svg", ns], vqa_status=AssetVQAStatus.PASS
        )
        d.fulfilled = True
        d.result_html = f'<img src="agent_generated/{d.id}.svg">'
        return d, asset

    agent._fulfill_svg_step = mock_fulfill_svg
    
    # Run
    await agent.run_parallel_async(state)
    
    # 4. Verify Final State
    assert not working_path.exists() # Should be committed
    
    final_content = md_path.read_text(encoding="utf-8")
    assert '<img src="agent_generated/v1.svg">' in final_content
    assert '<img src="agent_generated/v2.svg">' in final_content
    assert '<img src="agent_generated/v3.svg">' in final_content
    assert ':::visual' not in final_content
    
    # Check UAR
    assert "v1" in uar.assets
    assert "v2" in uar.assets
    assert "v3" in uar.assets
    
    # Final check on stats
    with open(e2e_workspace / "assets.json", "r") as f:
        data = json.load(f)
        assert data["stats"]["by_source"]["AI"] == 3
