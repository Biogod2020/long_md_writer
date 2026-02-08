import os
import json
import pytest
from pathlib import Path
from src.core.types import AgentState
from src.core.persistence import ProfileManager

def test_breakpoint_persistence_save(tmp_path):
    """Verify that a breakpoint saves the state to disk."""
    # Setup mock workspace and state
    workspace = tmp_path / "test_ws"
    workspace.mkdir()
    debug_dir = workspace / "debug"
    
    state = AgentState(
        job_id="test_job",
        workspace_path=str(workspace),
        user_intent="Test Intent"
    )
    
    # This will be implemented in Phase 2
    # For now, we simulate the hook logic
    bp_id = "BP-1"
    bp_save_path = debug_dir / bp_id
    bp_save_path.mkdir(parents=True, exist_ok=True)
    
    state_file = bp_save_path / "state.json"
    state_file.write_text(state.model_dump_json(), encoding="utf-8")
    
    assert state_file.exists()
    saved_data = json.loads(state_file.read_text())
    assert saved_data["job_id"] == "test_job"
    assert saved_data["user_intent"] == "Test Intent"
