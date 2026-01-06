
import os
import sys
import time
from pathlib import Path

os.environ["GEMINI_AUTH_PASSWORD"] = "123456"

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.core.types import AgentState
from src.agents.image_sourcing_agent import ImageSourcingAgent

def test_parallel_sourcing():
    # Setup paths
    workspace_dir = (Path(__file__).parent / "resources" / "test_workspace_images_cn").resolve()
    html_file = workspace_dir / "html" / "detailed_intro.html"
    
    # Initialize agent
    agent = ImageSourcingAgent(debug=True, headless=True)
    
    # Initialize AgentState
    state = AgentState(
        job_id="test_parallel",
        workspace_path=str(workspace_dir),
        completed_html_sections=[str(html_file)]
    )
    
    start_time = time.time()
    print(f"Starting PARALLEL ImageSourcingAgent Test...")
    agent.run(state)
    end_time = time.time()
    
    print(f"\nExecution finished in {end_time - start_time:.2f} seconds.")
    print("Success! Check the workspace for results.")

if __name__ == "__main__":
    test_parallel_sourcing()
