import asyncio
import os
import shutil
from pathlib import Path
from src.core.types import AgentState
from src.agents.svg_generation.processor import repair_svg_async
from src.core.gemini_client import GeminiClient

async def test_patch_failure_reproduction():
    print("🧪 [TEST] Reproducing Patch Matching Failure...")
    
    # 1. Dummy SVG with complex formatting
    svg_code = '<svg viewBox="0 0 100 100">\n  <circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />\n</svg>'
    
    # 2. Issues and suggestions
    issues = ["The circle should be blue."]
    suggestions = ["Change fill='red' to fill='blue'."]
    intent = "A blue circle."
    
    state = AgentState(
        job_id="test_fail",
        workspace_path="workspace/test_patch_fail",
        user_intent="Testing repair robustness.",
        debug_mode=True
    )
    os.makedirs(state.workspace_path, exist_ok=True)

    client = GeminiClient()

    # 3. Attempt repair
    print("🚀 Attempting repair...")
    
    new_svg = await repair_svg_async(
        client,
        intent,
        svg_code,
        issues,
        suggestions,
        state=state
    )
    
    if new_svg is None:
        print("✅ Baseline confirmed: Repair returned None on failure/mismatch.")
    else:
        print(f"⚠️ Repair returned something: {len(new_svg)} chars.")

if __name__ == "__main__":
    asyncio.run(test_patch_failure_reproduction())
