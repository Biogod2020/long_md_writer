import asyncio
import os
import base64
from pathlib import Path
from src.core.types import AgentState
from src.agents.svg_generation.processor import repair_svg_async
from src.agents.asset_management.processors.audit import audit_svg_visual_async, render_svg_to_png_base64
from src.core.gemini_client import GeminiClient

async def run_scientific_repair_test():
    print("🛠️ [SCIENTIFIC REPAIR TEST] Starting automated repair cycle...")
    svg_path = Path("workspace/v12_final_verification_stable/agent_generated/s2-fig-einthoven-triangle.svg")
    if not svg_path.exists():
        print("❌ Source SVG not found!")
        return
    old_svg_code = svg_path.read_text(encoding="utf-8")
    
    issues = [
        "Inconsistent projection logic: Lead I component is drawn on the axis, while Lead II and III components are drawn from the heart center to the axis.",
        "Geometric inaccuracy: The red lines for Lead II and III components should lie directly on the black triangle edges (axes).",
        "Perpendicularity: The dashed projection line for Lead III is not perpendicular to the LA-LL axis."
    ]
    suggestions = [
        "Redraw the red 'component' lines for Lead II and Lead III so they are collinear with the triangle sides, starting from the midpoint of each side.",
        "Recalculate coordinates to ensure dashed lines are strictly perpendicular (90 degrees) to the diagonal axes."
    ]
    
    intent = "A geometric representation of Einthoven's Triangle showing Lead I, II, and III as vectors forming an equilateral triangle, with correct scalar projections of the heart vector P on each axis."
    state = AgentState(job_id="repair_test", workspace_path="workspace/repair_test", user_intent="ECG physics lecture about vector projections and lead definitions.", debug_mode=True)
    Path(state.workspace_path).mkdir(parents=True, exist_ok=True)
    client = GeminiClient()

    print("\n🚀 Step 1: Requesting AI Repair based on scientific feedback...")
    old_png_b64 = render_svg_to_png_base64(old_svg_code)
    new_svg_code = await repair_svg_async(client, intent, old_svg_code, issues, suggestions, state=state, rendered_image_b64=old_png_b64)

    if not new_svg_code:
        print("❌ Repair failed.")
        return

    repaired_path = Path(state.workspace_path) / "s2-fig-einthoven-triangle-REPAIRED.svg"
    repaired_path.write_text(new_svg_code, encoding="utf-8")
    print(f"✅ Repaired SVG saved to: {repaired_path}")

    print("\n📋 Step 2: Re-auditing the repaired asset...")
    result = await audit_svg_visual_async(client, new_svg_code, intent, state=state, svg_path=repaired_path)

    print("\n" + "="*50)
    print("📊 POST-REPAIR SCIENTIFIC AUDIT REPORT")
    print("="*50)
    if result:
        print(f"Result: {result.get('result').upper()}")
        print(f"New Scientific Accuracy Score: {result.get('accuracy_score')}/100")
        print(f"\nAuditor Thought: {result.get('thought')}")
        if result.get('result') == 'pass' or result.get('accuracy_score', 0) > 85:
            print("\n🎉 SUCCESS: The scientific logic has been corrected!")
        else:
            print("\n⚠️ IMPROVED BUT NOT PERFECT: See remaining issues.")
            for issue in result.get("issues", []): print(f"  - {issue}")
    else:
        print("❌ Audit failed.")

if __name__ == "__main__":
    asyncio.run(run_scientific_repair_test())
