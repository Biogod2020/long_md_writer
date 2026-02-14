import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.editorial_qa_agent import EditorialQAAgent

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.generate_async = AsyncMock()
    return client

@pytest.fixture
def sample_state(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    md_dir = workspace / "md"
    md_dir.mkdir()
    
    # Create sample md files
    s1_path = md_dir / "sec-1.md"
    s1_path.write_text("# S1\nContent 1", encoding="utf-8")
    s2_path = md_dir / "sec-2.md"
    s2_path.write_text("# S2\nContent 2", encoding="utf-8")
    
    state = AgentState(
        job_id="test_job",
        workspace_path=str(workspace),
        completed_md_sections=[str(s1_path), str(s2_path)],
        manifest=Manifest(
            project_title="Test Project",
            description="Test Desc",
            sections=[
                SectionInfo(id="sec-1", title="S1", summary="Sum 1"),
                SectionInfo(id="sec-2", title="S2", summary="Sum 2")
            ]
        )
    )
    return state

@pytest.mark.asyncio
async def test_editorial_qa_orchestration(sample_state, mock_client):
    agent = EditorialQAAgent(client=mock_client, max_iterations=1)
    
    # 1. Mock Critic Approve
    resp = MagicMock()
    resp.success = True
    resp.text = '{"verdict": "APPROVE", "thought": "Good", "feedback": "Nice"}'
    resp.thoughts = "Thinking..."
    mock_client.generate_async.side_effect = [resp]
    
    # 2. Run agent
    updated_state = await agent.run_async(sample_state)
    
    # 3. Verify
    assert updated_state.markdown_approved is True
    merged_path = Path(sample_state.workspace_path) / "final_full.md"
    assert merged_path.exists()
    content = merged_path.read_text(encoding="utf-8")
    assert "<!-- SECTION: sec-1 -->" in content
    assert "<!-- SECTION: sec-2 -->" in content

@pytest.mark.asyncio
async def test_editorial_qa_repair_loop(sample_state, mock_client):
    agent = EditorialQAAgent(client=mock_client, max_iterations=2)
    
    # 1. Mock responses: Modify -> Advicer -> Fixer -> Approve
    r1 = MagicMock(success=True, text='{"verdict": "MODIFY", "feedback": "Fix X"}')
    r2 = MagicMock(success=True, text='{"final_full.md": "Change Content 1 to Fixed 1"}')
    r3 = MagicMock(success=True, text='{"patches": [{"search": "Content 1", "replace": "Fixed 1"}]}')
    r4 = MagicMock(success=True, text='{"verdict": "APPROVE"}')
    
    mock_client.generate_async.side_effect = [r1, r2, r3, r4]
    
    # 2. Run agent
    updated_state = await agent.run_async(sample_state)
    
    # 3. Verify
    assert updated_state.markdown_approved is True
    merged_path = Path(sample_state.workspace_path) / "final_full.md"
    content = merged_path.read_text(encoding="utf-8")
    assert "Fixed 1" in content
    assert mock_client.generate_async.call_count == 4
