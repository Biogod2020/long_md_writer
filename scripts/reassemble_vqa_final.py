
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.types import AgentState, Manifest
from src.agents.assembler_agent import AssemblerAgent
import json

def reassemble():
    workspace_path = "/Users/jay/LocalProjects/long_html_writing_agent/workspace_debug/debug_201956"
    workspace = Path(workspace_path)
    
    # Load manifest
    manifest_data = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    manifest = Manifest(**manifest_data)
    
    # Correct order of sections
    sections = ["sec-1.html", "sec-2.html", "sec-3.html", "sec-4.html", "sec-5.html", "sec-6.html", "sec-7.html"]
    completed_html_sections = [str(workspace / "html" / s) for s in sections]
    
    state = AgentState(
        job_id="debug_201956",
        workspace_path=workspace_path,
        manifest=manifest,
        completed_html_sections=completed_html_sections
    )
    
    assembler = AssemblerAgent()
    new_state = assembler.run(state)
    
    print(f"✅ Final HTML reassembled at: {new_state.final_html_path}")

if __name__ == "__main__":
    reassemble()
