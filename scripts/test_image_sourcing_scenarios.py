#!/usr/bin/env python3
"""
Test script for ImageSourcingAgent scenarios.
- Case 1: Local asset found in UAR (Priority)
- Case 2: Local asset not found/unqualified -> Web search fallback
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, UniversalAssetRegistry, AssetEntry, AssetSource, AssetQualityLevel
from src.agents.image_sourcing.agent import ImageSourcingAgent


async def test_image_sourcing_scenarios():
    print("\n" + "="*70)
    print(" 🧪 Testing ImageSourcingAgent: Local vs Web")
    print("="*70)

    workspace = PROJECT_ROOT / "workspace" / "test_image_sourcing"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "html").mkdir(exist_ok=True)
    
    client = GeminiClient()
    
    # -------------------------------------------------------------------------
    # Scenario 1: Local Hit
    # -------------------------------------------------------------------------
    print("\n[Scenario 1] Local Hit Test")
    
    # Setup UAR with a matching asset
    uar_path = workspace / "uar_local_hit.json"
    uar = UniversalAssetRegistry()
    uar.set_persist_path(str(uar_path))
    
    heart_asset = AssetEntry(
        id="s1-heart-diagram",
        source=AssetSource.USER,
        local_path="assets/images/heart.png",
        semantic_label="A detailed physiological diagram of the human heart showing all chambers.",
        quality_level=AssetQualityLevel.HIGH,
        vqa_status="PASS"
    )
    uar.register_immediate(heart_asset)
    
    # Create mock HTML with placeholder
    html_content = """
    <div class="img-placeholder" data-img-id="heart-anatomy">
      <p class="img-description">A physiological diagram of the human heart, showing atria and ventricles.</p>
    </div>
    """
    html_path = workspace / "html" / "section_local.html"
    html_path.write_text(html_content)
    
    state = AgentState(
        job_id="test_local",
        workspace_path=str(workspace),
        completed_html_sections=[str(html_path)],
        asset_registry=uar
    )
    
    agent = ImageSourcingAgent(client=client, headless=True, debug=True)
    
    print("   Running agent...")
    processed_state = agent.run(state)
    
    updated_html = html_path.read_text()
    if 'data-asset-id="s1-heart-diagram"' in updated_html:
        print("   ✅ SUCCESS: Local asset 's1-heart-diagram' was correctly selected.")
    else:
        print("   ❌ FAILURE: Local asset was not selected.")
        print(f"   HTML Output: {updated_html}")

    # -------------------------------------------------------------------------
    # Scenario 2: Local Miss -> Web Search (Mocked for speed if possible, or real)
    # -------------------------------------------------------------------------
    print("\n[Scenario 2] Local Miss -> Web Fallback Test")
    
    # Setup UAR with NO matching assets
    uar_path_empty = workspace / "uar_empty.json"
    uar_empty = UniversalAssetRegistry()
    uar_empty.set_persist_path(str(uar_path_empty))
    
    # Create mock HTML with a placeholder that won't match anything local
    html_content_web = """
    <div class="img-placeholder" data-img-id="historical-car">
      <p class="img-description">A black and white photograph of a 1920s Ford Model T on a dirt road.</p>
    </div>
    """
    html_path_web = workspace / "html" / "section_web.html"
    html_path_web.write_text(html_content_web)
    
    state_web = AgentState(
        job_id="test_web",
        workspace_path=str(workspace),
        completed_html_sections=[str(html_path_web)],
        asset_registry=uar_empty
    )
    
    print("   Running agent (expecting web search)...")
    # Note: This will actually try to search Google if not mocked
    # For CI/CD we might want to mock the searcher, but for "Real functional test" we run it.
    processed_state_web = agent.run(state_web)
    
    updated_html_web = html_path_web.read_text()
    if '<img src="assets/images/historical-car' in updated_html_web:
        print("   ✅ SUCCESS: Web search fallback worked and replaced the placeholder.")
    elif 'img-placeholder' in updated_html_web:
        print("   ❌ FAILURE: Placeholder still exists. Web search failed or was skipped.")
    else:
        print("   ❓ UNEXPECTED result.")
        print(f"   HTML Output: {updated_html_web}")

    print("\n" + "="*70)
    print(" ✨ Tests Completed")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_image_sourcing_scenarios())
