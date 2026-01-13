#!/usr/bin/env python3
"""
SVG Generation + Visual QA + Repair Loop End-to-End Test

This script simulates the full LangGraph workflow with repair loop:
1. AssetFulfillmentAgent generates an SVG from a :::visual directive
2. AssetCriticAgent audits the generated SVG
3. If audit fails, regenerate SVG with critic feedback
4. Repeat until pass or max attempts reached

Usage:
    python scripts/test_svg_e2e.py
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, AssetEntry, AssetSource
from src.agents.asset_management import AssetFulfillmentAgent, AssetCriticAgent
from src.agents.asset_management.processors.svg import generate_svg_async, repair_svg_async
from src.agents.asset_management.critic import AuditResult
import hashlib


# Test Markdown with :::visual directive
ORIGINAL_INTENT = """A schematic diagram of the human heart showing the four chambers:
- Left atrium (receives oxygenated blood from lungs)
- Right atrium (receives deoxygenated blood from body)
- Left ventricle (pumps oxygenated blood to body)
- Right ventricle (pumps deoxygenated blood to lungs)

Use red/pink color for oxygenated blood flow paths.
Use blue color for deoxygenated blood flow paths.
Include arrows indicating blood flow direction.
Label each chamber clearly."""

TEST_MARKDOWN = f"""
# Chapter 1: Cardiac Anatomy

The human heart is a muscular organ responsible for pumping blood throughout the body.
It consists of four chambers that work together in a coordinated rhythm.

:::visual {{"id": "s1-heart-diagram", "action": "GENERATE_SVG"}}
{ORIGINAL_INTENT}
:::

The left ventricle has the thickest walls because it must pump blood 
to the entire body through the aorta.
"""





async def run_e2e_test():
    print("\n" + "=" * 70)
    print(" 🧪 SVG Generation + Visual QA + Repair Loop E2E Test")
    print("=" * 70)

    # Setup workspace
    workspace_path = PROJECT_ROOT / "workspace" / "test_e2e_loop"
    workspace_path.mkdir(parents=True, exist_ok=True)
    assets_path = workspace_path / "generated_assets"
    assets_path.mkdir(parents=True, exist_ok=True)

    print(f"📁 Workspace: {workspace_path}")

    # Initialize state
    state = AgentState(
        job_id="e2e_loop_test",
        workspace_path=str(workspace_path),
        user_intent="Test SVG generation with QA repair loop",
    )

    # Initialize client
    client = GeminiClient()
    uar = state.get_uar()

    # Configuration
    MAX_ATTEMPTS = 4
    PASS_THRESHOLD = 0.90

    # =========================================================================
    # Phase 1: Initial SVG Generation
    # =========================================================================
    print("\n" + "-" * 70)
    print(" 📦 Phase 1: Initial SVG Generation")
    print("-" * 70)

    fulfillment = AssetFulfillmentAgent(
        client=client,
        output_dir="generated_assets",
        skip_generation=False,
        skip_search=True,
    )

    state, fulfilled_markdown = await fulfillment.run_async(
        state=state,
        section_content=TEST_MARKDOWN,
        namespace="s1"
    )

    svg_asset = uar.get_asset("s1-heart-diagram")
    if not svg_asset:
        print("❌ Error: Initial SVG was not created!")
        return

    svg_path = workspace_path / svg_asset.local_path
    print(f"✅ Initial SVG created: {svg_path.name}")

    # =========================================================================
    # Phase 2: QA + Repair Loop
    # =========================================================================
    print("\n" + "-" * 70)
    print(" 🔄 Phase 2: QA + Repair Loop")
    print("-" * 70)

    critic = AssetCriticAgent(client=client, pass_threshold=PASS_THRESHOLD)
    
    attempt = 0
    final_passed = False
    all_reports = []

    while attempt < MAX_ATTEMPTS:
        attempt += 1
        print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS} ---")
        
        # Audit current SVG
        report = await critic.audit_asset_async(
            asset=svg_asset,
            intent_description="Heart anatomy diagram with four chambers, blood flow arrows, color-coded paths (red oxygenated, blue deoxygenated), clear non-overlapping labels",
            workspace_path=workspace_path
        )
        all_reports.append(report)
        
        print(f"   Result: {report.result.value} | Score: {report.score:.0%}")
        
        if report.result == AuditResult.PASS or report.score >= PASS_THRESHOLD:
            print(f"   ✅ PASSED!")
            final_passed = True
            break
        
        if attempt >= MAX_ATTEMPTS:
            print(f"   ⚠️ Max attempts reached")
            break
        
        # Show issues
        if report.issues:
            print("   Issues:")
            for issue in report.issues[:3]:
                print(f"     - {issue[:60]}...")
        
        # === SURGICAL REPAIR: Pass the failed SVG code + rendered image to the model ===
        current_svg_path = workspace_path / svg_asset.local_path
        current_svg_code = current_svg_path.read_text(encoding="utf-8")
        
        # Render SVG to PNG for multi-modal repair
        rendered_b64 = None
        try:
            import cairosvg
            import base64
            png_data = cairosvg.svg2png(bytestring=current_svg_code.encode("utf-8"), output_width=800)
            rendered_b64 = base64.b64encode(png_data).decode("utf-8")
            print(f"\n   🔧 Multi-modal repair with image + code ({len(current_svg_code)} chars)...")
        except Exception as e:
            print(f"\n   🔧 Text-only repair (render failed: {e})...")
        
        new_svg_code = await repair_svg_async(
            client=client,
            original_intent=ORIGINAL_INTENT,
            failed_svg_code=current_svg_code,
            issues=report.issues,
            suggestions=report.suggestions,
            rendered_image_b64=rendered_b64
        )
        
        if not new_svg_code:
            print("   ❌ Failed to regenerate SVG")
            break
        
        # Save new version
        version_filename = f"s1-heart-diagram_v{attempt + 1}.svg"
        new_svg_path = assets_path / version_filename
        new_svg_path.write_text(new_svg_code, encoding="utf-8")
        
        # Update asset entry
        content_hash = hashlib.md5(new_svg_code.encode()).hexdigest()
        svg_asset.local_path = f"generated_assets/{version_filename}"
        svg_asset.content_hash = content_hash
        uar.register_immediate(svg_asset)
        
        print(f"   ✅ New version saved: {version_filename}")

    # =========================================================================
    # Phase 3: Final Results
    # =========================================================================
    print("\n" + "=" * 70)
    print(" 📊 Final Results")
    print("=" * 70)

    final_report = all_reports[-1]
    final_svg_path = workspace_path / svg_asset.local_path
    
    print(f"\n🎯 Final Status: {'✅ PASSED' if final_passed else '❌ NEEDS MORE WORK'}")
    print(f"   Total Attempts: {attempt}")
    print(f"   Final Score: {final_report.score:.0%}")
    print(f"   Final SVG: {final_svg_path}")
    
    # Show score progression
    print(f"\n📈 Score Progression:")
    for i, report in enumerate(all_reports):
        status = "✅" if report.result == AuditResult.PASS else "🔄" if report.result == AuditResult.NEEDS_REVISION else "❌"
        print(f"   Attempt {i+1}: {report.score:.0%} {status}")
    
    # Show final assessment
    if final_report.quality_assessment:
        print(f"\n📝 Final Assessment:")
        print(f"   {final_report.quality_assessment[:200]}...")
    
    if not final_passed and final_report.issues:
        print(f"\n⚠️ Remaining Issues:")
        for issue in final_report.issues[:3]:
            print(f"   - {issue[:80]}...")

    # Show final SVG preview
    if final_svg_path.exists():
        svg_content = final_svg_path.read_text()
        print(f"\n📜 Final SVG Preview (first 600 chars):")
        print("-" * 40)
        print(svg_content[:600])
        print("-" * 40)
    
    print(f"\n💾 All versions saved in: {assets_path}")
    print(f"   Open in browser to compare visual quality")


if __name__ == "__main__":
    asyncio.run(run_e2e_test())
