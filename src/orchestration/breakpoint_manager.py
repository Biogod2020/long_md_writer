"""
SnapshotManager: SOTA 2.0 Scene Solidification & Artifact Export
Manages physical scene snapshots and logical state persistence.
"""

import json
import shutil
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..core.types import AgentState
from ..core.persistence import ProfileManager

class SnapshotManager:
    """
    Handles artifact collection and state persistence at breakpoints.
    Creates a 'High-Fidelity' snapshot of the workspace for auditing.
    """
    
    def __init__(self, state: AgentState, profile_manager: Optional[ProfileManager] = None):
        self.state = state
        self.workspace = Path(state.workspace_path)
        self.snapshots_dir = self.workspace / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
        self.pm = profile_manager or ProfileManager(profiles_dir=self.workspace / "profiles")

    def capture(self, bp_id: str, auto_continue: bool = False):
        """
        Captures a complete scene snapshot: State + All physical artifacts.
        """
        print(f"\n📸 [SNAPSHOT] Solidifying scene at {bp_id}...")
        
        timestamp = datetime.now().strftime("%H%M%S")
        snapshot_name = f"{bp_id}_{timestamp}"
        snapshot_path = self.snapshots_dir / snapshot_name
        snapshot_path.mkdir(parents=True, exist_ok=True)
        
        artifacts_path = snapshot_path / "artifacts"
        artifacts_path.mkdir(exist_ok=True)
        
        # 1. Collect Logical State
        state_file = snapshot_path / "state.json"
        state_file.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")
        
        # 2. Collect Physical Artifacts
        self._collect_artifacts(artifacts_path)
        
        # 3. Generate Audit Manifest (SOTA Enhancement)
        self._generate_audit_manifest(snapshot_path)
        
        # 4. Integrate with ProfileManager
        self.pm.create_profile(
            project_title=self.state.manifest.project_title if self.state.manifest else "Breakpoint Test",
            profile_id=f"snap_{snapshot_name}"
        )
        self.pm.record_uar_checkpoint(self.state)
        if self.state.manifest:
            self.pm.record_manifest(self.state.manifest)
        self.pm.save_profile()
        
        print(f"✅ Scene solidified at: {snapshot_name}")
        
        if not auto_continue:
            print(f"\n🩺 [SURGERY MODE] Flow interrupted at {bp_id}.")
            print(f"   Inspection Base: {snapshot_path.absolute()}")
            if os.getenv("CI") != "true":
                input("   Press Enter when verification is complete to resume flow...")
                print("🚀 Resuming execution...")

    def list_snapshots(self) -> list[dict]:
        """Lists all available snapshots with metadata."""
        snapshots = []
        if not self.snapshots_dir.exists():
            return []
            
        for d in sorted(self.snapshots_dir.iterdir(), key=os.path.getmtime, reverse=True):
            if d.is_dir() and (d / "state.json").exists():
                manifest_path = d / "audit_manifest.json"
                metadata = {}
                if manifest_path.exists():
                    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
                
                snapshots.append({
                    "id": d.name,
                    "path": str(d),
                    "timestamp": metadata.get("timestamp"),
                    "bp_id": d.name.split("_")[0],
                    "assets": metadata.get("assets_in_uar", 0),
                    "sections": metadata.get("sections_completed", 0)
                })
        return snapshots

    def load_snapshot_state(self, snapshot_id: str) -> AgentState:
        """Loads a logical AgentState from a snapshot folder."""
        state_path = self.snapshots_dir / snapshot_id / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"Snapshot state not found: {state_path}")
            
        print(f"📖 [SNAPSHOT] Loading state from {snapshot_id}...")
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        return AgentState(**state_data)

    def restore_artifacts(self, snapshot_id: str):
        """Physically restores artifacts from a snapshot back to the active workspace."""
        source_dir = self.snapshots_dir / snapshot_id / "artifacts"
        if not source_dir.exists():
            print(f"⚠️ No artifacts found in snapshot {snapshot_id}")
            return
            
        print(f"🔄 [SNAPSHOT] Restoring physical artifacts from {snapshot_id} to workspace...")
        
        # We selectively restore common dirs to avoid nuking everything
        for dirname in ["md", "html", "agent_generated", "agent_sourced", "assets"]:
            src = source_dir / dirname
            dst = self.workspace / dirname
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        
        for filename in ["manifest.json", "assets.json", "design_tokens.json", "style_mapping.json"]:
            src = source_dir / filename
            dst = self.workspace / filename
            if src.exists():
                shutil.copy2(src, dst)
        print("✅ Physical scene restored.")

    def _collect_artifacts(self, target_dir: Path):
        """Physically copies workspace files to snapshot."""
        source_dirs = ["md", "html", "agent_generated", "agent_sourced", "assets", "qa_logs"]
        for dirname in source_dirs:
            src_path = self.workspace / dirname
            if src_path.exists() and src_path.is_dir():
                shutil.copytree(src_path, target_dir / dirname, dirs_exist_ok=True)
        
        for filename in ["manifest.json", "assets.json", "design_tokens.json", "style_mapping.json"]:
            src_file = self.workspace / filename
            if src_file.exists():
                shutil.copy2(src_file, target_dir / filename)

    def _generate_audit_manifest(self, snapshot_path: Path):
        """Generates a summary of artifacts for the Agent auditor."""
        uar = self.state.get_uar()
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "breakpoint": snapshot_path.name,
            "assets_in_uar": len(uar.assets),
            "sections_completed": len(self.state.completed_md_sections),
            "uar_details": [
                {
                    "id": a.id,
                    "label": a.semantic_label,
                    "path": a.local_path,
                    "quality": a.quality_level.value if a.quality_level else "N/A"
                }
                for a in uar.assets.values()
            ]
        }
        (snapshot_path / "audit_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")