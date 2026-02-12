"""
Real API Test for SVGAgent
Verifies the Generate-Audit-Repair loop with actual LLM calls.
"""

import asyncio
import os
from pathlib import Path
from src.agents.svg_generation.agent import SVGAgent
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.agents.asset_management.models import VisualDirective

async def test_svg_agent_real_loop():
    """
    Performs a real E2E test of the SVGAgent.
    Requires the local Gemini proxy to be running.
    """
    client = GeminiClient()
    workspace = Path("data/test_artifacts/svg_agent_test")
    if workspace.exists():
        import shutil
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    
    state = AgentState(
        job_id="test_svg_agent",
        workspace_path=str(workspace)
    )
    
    agent = SVGAgent(client=client, debug=True)
    
    # Directive with enough context to trigger a professional result
    directive = VisualDirective(
        id="s1-test-diagram",
        description="A professional technical diagram showing the interaction between a Magnetic Field and a Moving Charge. Use elegant colors, arrows for vectors, and clear labels.",
        raw_block=":::visual ... :::",
        start_pos=0,
        end_pos=100
    )
    directive.context_before = "In this section, we explore Lorentz force."
    directive.context_after = "The force is perpendicular to both velocity and magnetic field."
    
    print("\n🚀 [SMOKE TEST] Starting SVGAgent fulfill_directive_async...")
    success, asset, html = await agent.fulfill_directive_async(directive, state)
    
    print(f"\n[Test Result] Success: {success}")
    if asset:
        print(f"[Test Result] Asset ID: {asset.id}")
        print(f"[Test Result] VQA Status: {asset.vqa_status}")
        print(f"[Test Result] Path: {asset.local_path}")
        
        # Verify file existence
        full_path = workspace / asset.local_path
        if full_path.exists():
            content = full_path.read_text()
            print(f"[Test Result] SVG File exists, size: {len(content)} chars")
            if "<svg" in content:
                print("[Test Result] ✅ VALID SVG detected.")
            else:
                print("[Test Result] ❌ INVALID SVG content.")
        else:
            print(f"[Test Result] ❌ File NOT FOUND at {full_path}")
    
    if success and asset and (workspace / asset.local_path).exists():
        print("\n🎉 [SMOKE TEST] PASSED.")
    else:
        print("\n💀 [SMOKE TEST] FAILED.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(test_svg_agent_real_loop())
