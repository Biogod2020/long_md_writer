import asyncio
import os
import json
from pathlib import Path
from src.core.types import AgentState
from src.agents.asset_management.processors.audit import audit_svg_visual_async
from src.core.gemini_client import GeminiClient

async def retrospective_audit():
    print("🔬 [RETROSPECTIVE AUDIT] Checking existing asset with NEW scientific rules...")
    
    svg_path = Path("workspace/v12_final_verification_stable/agent_generated/s2-fig-einthoven-triangle.svg")
    if not svg_path.exists():
        print(f"❌ File not found: {svg_path}")
        return

    svg_code = svg_path.read_text(encoding="utf-8")
    intent = "A geometric representation of Einthoven's Triangle. It must show Lead I, II, and III as vectors forming an equilateral triangle, correctly representing the projections of the heart vector P."
    
    state = AgentState(
        job_id="audit_rev",
        workspace_path="workspace/v12_final_verification_stable",
        user_intent="ECG physics lecture about vector projections and lead definitions.",
        debug_mode=True
    )

    client = GeminiClient()
    print(f"\n📋 Auditing: {svg_path.name}")
    print("⏳ Sending to VLM Auditor (Scientific Rigor Mode)...")
    
    result = await audit_svg_visual_async(client, svg_code, intent, state=state, svg_path=svg_path)

    print("\n" + "="*50)
    print("📊 SCIENTIFIC AUDIT REPORT")
    print("="*50)
    if result:
        print(f"Result: {result.get('result').upper()}")
        print(f"Scientific Accuracy Score: {result.get('accuracy_score')}/100")
        print(f"\nAuditor Thought:\n{result.get('thought')}")
        if result.get("issues"):
            print("\n🚨 Identified Issues:")
            for issue in result.get("issues"): print(f"  - {issue}")
        if result.get("suggestions"):
            print("\n🛠️ Repair Suggestions:")
            for sug in result.get("suggestions"): print(f"  - {sug}")
    else:
        print("❌ Audit failed to return a valid response.")

if __name__ == "__main__":
    asyncio.run(retrospective_audit())
