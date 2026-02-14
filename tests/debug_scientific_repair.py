import asyncio
import os
from pathlib import Path
from src.core.types import AgentState
from src.agents.svg_generation.processor import repair_svg_async
from src.agents.asset_management.processors.audit import audit_svg_visual_async, render_svg_to_png_base64
from src.core.gemini_client import GeminiClient

async def debug_scientific_repair():
    print("🧪 [DEBUG] Starting Deep Dive into Scientific Repair...")
    svg_path = Path("workspace/v12_final_verification_stable/agent_generated/s2-fig-einthoven-triangle.svg")
    if not svg_path.exists():
        print("❌ Error: Source SVG not found!")
        return
    svg_code = svg_path.read_text(encoding="utf-8")
    issues = [
        "Scientific Inaccuracy: Projections for Lead II and III are drawn as 'tripod' lines from center to axis, which is physically wrong.",
        "Geometric Error: Dashed projection lines are not perpendicular to the diagonal axes."
    ]
    suggestions = [
        "Ensure red projection lines for Lead II/III lie DIRECTLY on the triangle edges (axes).",
        "Recalculate coordinates so projection lines form 90-degree angles with the leads."
    ]
    intent = "A geometric Einthoven's Triangle showing correct vector projections of heart vector P onto Lead I, II, and III axes."
    state = AgentState(job_id="debug_repair", workspace_path="workspace/debug_repair", user_intent="Physics of ECG: Vector projections.", debug_mode=True)
    Path(state.workspace_path).mkdir(parents=True, exist_ok=True)
    client = GeminiClient()

    print("\n--- 🛠️ Phase 1: Attempting Repair ---")
    old_png_b64 = render_svg_to_png_base64(svg_code)
    try:
        new_svg = await repair_svg_async(client, intent, svg_code, issues, suggestions, state=state, rendered_image_b64=old_png_b64)
        if new_svg:
            print("\n✅ Repair success! New SVG generated.")
            repaired_path = Path(state.workspace_path) / "debug_repaired.svg"
            repaired_path.write_text(new_svg, encoding="utf-8")
            print("\n--- 📋 Phase 2: Re-Auditing Repaired Asset ---")
            audit = await audit_svg_visual_async(client, new_svg, intent, state=state, svg_path=repaired_path)
            if audit:
                print(f"New Result: {audit.get('result')}")
                print(f"New Accuracy Score: {audit.get('accuracy_score')}/100")
                print(f"Auditor Thought: {audit.get('thought')}")
        else:
            print("\n❌ Repair failed.")
    except Exception as e:
        print(f"\n💥 CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(debug_scientific_repair())
