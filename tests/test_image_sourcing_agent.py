"""
Standalone test for ImageSourcingAgent.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.agents.image_sourcing_agent import ImageSourcingAgent

def test_image_sourcing():
    # 1. Setup workspace
    workspace = (Path(__file__).parent / "resources" / "test_workspace_images").resolve()
    if workspace.exists():
        import shutil
        shutil.rmtree(workspace)
        print("Cleaned up existing workspace.")
    
    workspace.mkdir(exist_ok=True)
    (workspace / "html").mkdir(exist_ok=True)
    (workspace / "assets" / "images").mkdir(parents=True, exist_ok=True)

    # 2. Create sample HTML with 3 placeholders for Antiarrhythmic Drugs
    html_content = """
    <section id="antiarrhythmics-ecg">
        <h1>ECG Effects of Antiarrhythmic Drugs</h1>
        <p>Antiarrhythmic drugs are classified by the Vaughan Williams system based on their primary mechanism of action. Each class has distinct effects on the ECG waveforms.</p>
        
        <h2>Class I: Sodium Channel Blockers</h2>
        <p>Class I agents primarily affect the QRS complex by slowing the rate of depolarization. Class Ic drugs, like flecainide, significantly prolong the QRS duration.</p>
        <div class="img-placeholder" data-img-id="class-i-ecg">
            <p class="img-description">ECG trace showing QRS widening from Class I antiarrhythmic drugs</p>
        </div>
        
        <h2>Class III: Potassium Channel Blockers</h2>
        <p>Class III agents, such as amiodarone and sotalol, block potassium channels, leading to a prolonged repolarization phase and QT interval prolongation.</p>
        <div class="img-placeholder" data-img-id="class-iii-qt-prolongation">
            <p class="img-description">ECG diagram showing QT interval prolongation due to Class III antiarrhythmics</p>
        </div>

        <h2>Class IV: Calcium Channel Blockers</h2>
        <p>Class IV agents (verapamil, diltiazem) slow conduction through the AV node, which typically manifests as an increase in the PR interval on the ECG.</p>
        <div class="img-placeholder" data-img-id="class-iv-pr-interval">
            <p class="img-description">ECG strip illustrating PR interval prolongation from calcium channel blockers</p>
        </div>
    </section>
    """
    html_file = (workspace / "html" / "sec-test.html").resolve()
    html_file.write_text(html_content, encoding="utf-8")

    # 3. Initialize AgentState
    state = AgentState(
        job_id="test_img_en",
        workspace_path=str(workspace),
        completed_html_sections=[str(html_file)]
    )

    # 4. Initialize Client and Agent
    import os
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    client = GeminiClient(api_base_url="http://localhost:7860", auth_token=auth_token)
    agent = ImageSourcingAgent(client=client, debug=True)

    # 5. Run Agent
    print("Starting ImageSourcingAgent EN test (with candidates preserved)...")
    updated_state = agent.run(state, preserve_candidates=True)

    if updated_state.errors:
        print("Errors occurred:")
        for err in updated_state.errors:
            print(f" - {err}")
    else:
        print("Success! Check the workspace for results.")
        
        # Verify changes
        new_content = html_file.read_text(encoding="utf-8")
        if 'img src="../assets/images/' in new_content:
            print("Placeholder replaced successfully.")
        else:
            print("Placeholder was NOT replaced.")

if __name__ == "__main__":
    test_image_sourcing()
