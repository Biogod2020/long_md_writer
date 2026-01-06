
import os
import sys
from pathlib import Path
import json

os.environ["GEMINI_AUTH_PASSWORD"] = "123456"

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.core.types import AgentState
from src.agents.image_sourcing_agent import ImageSourcingAgent

def test_cn_sourcing_fast():
    # Setup paths
    workspace_dir = (Path(__file__).parent / "resources" / "test_workspace_images_cn").resolve()
    html_file = workspace_dir / "html" / "test_retry.html"
    assets_dir = workspace_dir / "assets" / "images"

    
    # Initialize agent
    agent = ImageSourcingAgent(debug=True, headless=True) # Headless for speed
    
    # Read HTML
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Initialize AgentState
    state = AgentState(
        job_id="test_img_cn_fast",
        workspace_path=str(workspace_dir),
        completed_html_sections=[str(html_file)]
    )
    
    # Process
    print(f"Starting FAST ImageSourcingAgent CN test...")
    
    agent.run(state)

    
    print("\nSuccess! Check the workspace for results.")

if __name__ == "__main__":
    test_cn_sourcing_fast()
