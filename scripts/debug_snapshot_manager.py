import asyncio
import os
import shutil
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.orchestration.breakpoint_manager import SnapshotManager

async def debug_snapshot_manager():
    print("🧪 [DEBUG] Starting SnapshotManager Validation...")
    
    # 1. Setup mock workspace
    job_id = "debug_test_001"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Create some dummy artifacts
    (workspace_path / "md").mkdir()
    (workspace_path / "md" / "test.md").write_text("# Test Content", encoding="utf-8")
    (workspace_path / "manifest.json").write_text('{"project_title": "Debug Project"}', encoding="utf-8")
    
    # 2. Initialize mock state
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent="Debug testing",
        manifest=Manifest(project_title="Debug Project", description="Test", sections=[
            SectionInfo(id="sec-1", title="Section 1", summary="Debug summary")
        ])
    )
    
    manager = SnapshotManager(state)
    
    # 3. Test Capture
    print("\n--- Testing Capture ---")
    manager.capture("BP-TEST", auto_continue=True)
    
    # 4. Test List
    print("\n--- Testing List ---")
    snaps = manager.list_snapshots()
    for s in snaps:
        print(f"Found Snapshot: {s['id']} (BP: {s['bp_id']}, Assets: {s['assets']})")
    
    if not snaps:
        print("❌ No snapshots found!")
        return

    # 5. Test Load State
    print("\n--- Testing Load State ---")
    snapshot_id = snaps[0]['id']
    loaded_state = manager.load_snapshot_state(snapshot_id)
    print(f"Loaded State Job ID: {loaded_state.job_id}")
    
    # 6. Test Restore Artifacts
    print("\n--- Testing Restore Artifacts ---")
    # Delete original file to verify restore
    test_file = workspace_path / "md" / "test.md"
    if test_file.exists():
        test_file.unlink()
        print("Deleted original md/test.md")
    
    manager.restore_artifacts(snapshot_id)
    if test_file.exists():
        print("✅ Restore Successful: md/test.md back in place.")
    else:
        print("❌ Restore Failed: md/test.md missing.")
        
    print("\n✨ [DEBUG] SnapshotManager validation complete.")

if __name__ == "__main__":
    asyncio.run(debug_snapshot_manager())