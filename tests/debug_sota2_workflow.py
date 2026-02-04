import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.orchestration.workflow_markdown import create_sota2_workflow

async def run_clever_e2e():
    print("\n" + "=" * 70)
    print(" 🧠 Starting CLEVER INTERACTIVE SOTA 2.0 E2E Test")
    print("=" * 70)

    job_id = f"clever_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workspace_path = Path("./workspace_test") / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    for d in ["md", "agent_generated", "agent_sourced"]: (workspace_path / d).mkdir(exist_ok=True)

    # 🎯 UPDATED INTENT: Force SEARCH_WEB and provide context for potential USE_EXISTING
    user_intent = """Write a technical guide on 'Cardiac Vector Projections'. 
    Section 1: The Dipole. 
    Section 2: The Projections. 
    Section 3: Clinical Evidence. 
    
    IMPORTANT: 
    - In Section 3, I need a REAL medical photograph of a cardiology lab (SEARCH_WEB).
    - I have already provided a high-quality heart diagram in the library, please try to reuse it if possible.
    """
    
    reference_materials = "# Core Physics\nThe ECG signal V is the dot product of the heart vector P and the lead vector L: V = P · L."

    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent=user_intent,
        reference_materials=reference_materials,
        uar_path=str(workspace_path / "assets.json"),
        debug_mode=True
    )

    # 📦 INJECT MOCK ASSET into UAR to test reuse
    uar = state.get_uar()
    from src.core.types import AssetEntry, AssetSource, AssetQualityLevel
    mock_asset = AssetEntry(
        id="u-img-heart-ref",
        source=AssetSource.USER,
        semantic_label="A clear anatomical diagram of the human heart showing 4 chambers.",
        local_path="assets/images/candidates_ecg-medication-effects/img_1.jpg", # Path must exist relative to root
        quality_level=AssetQualityLevel.HIGH
    )
    uar.register_immediate(mock_asset)
    print(f"  [Test] Injected mock asset: {mock_asset.id}")

    client = GeminiClient()
    # We use skip_vision to keep the test focused on the fulfillment logic
    app = create_sota2_workflow(client=client, skip_vision=True)
    
    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    current_state = state
    print(f"🚀 Initializing Job: {job_id}")

    while True:
        # Run until next interrupt
        async for event in app.astream(current_state, config=config, stream_mode="values"):
            pass
        
        state_info = app.get_state(config)
        if not state_info.next:
            print("\n" + "="*70)
            print(" ✅ WORKFLOW COMPLETE")
            print("="*70)
            final_s = AgentState(**state_info.values)
            
            # SOTA: Enhanced Reporting Breakdown
            uar = final_s.get_uar()
            # 重新加载一次以确保获取最新的 stats (如果是从文件加载)
            print(f"Final Assets Cataloged: {len(uar.assets)}")
            print(f"  - New Assets Created: {len([a for a in uar.assets.values() if a.source in ['AI', 'WEB']])}")
            print(f"  - Pre-existing Assets: {len([a for a in uar.assets.values() if a.source == 'USER'])}")
            
            if final_s.failed_directives:
                print(f"\n❌ Fulfillment Failures: {len(final_s.failed_directives)}")
                for fd in final_s.failed_directives:
                    print(f"  - [{fd['id']}]: {fd['error']}")
            
            return

        next_node = state_info.next[0]
        current_values = AgentState(**state_info.values)
        update_data = {}

        print(f"\n[GATE: {next_node}]")

        if next_node == "refiner":
            print("🤖 AI Architect is asking for clarification...")
            for q in current_values.clarifier_questions:
                print(f"  ? {q['question']}")
            
            print("\n🧠 Clever Human Response:")
            print("  'The target audience is cardiology fellows. Please emphasize the mathematical derivation of Einthoven's Law from first principles of vector addition.'")
            ans = {q['id']: "Target: Cardiology fellows. Focus on first-principles derivation of Einthoven's Law." for q in current_values.clarifier_questions}
            update_data = {"clarifier_answers": ans}
        
        elif next_node == "review_brief":
            print("🤖 Reviewing Project Brief...")
            print(f"--- BRIEF SNIPPET ---\n{current_values.project_brief[:300]}...\n--------------------")
            print("\n🧠 Clever Human Response:")
            print("  'The vision is solid. I particularly like the emphasis on clinical rigor. Proceed to architecture.'")
            update_data = {"brief_approved": True}
            
        elif next_node == "review_outline":
            print("🤖 Reviewing Manifest...")
            if current_values.manifest:
                for s in current_values.manifest.sections:
                    print(f"  - {s.title}")
            else:
                print("  ⚠ Manifest generation failed.")
            print("\n🧠 Clever Human Response:")
            print("  'The section sequence is logical. Section 1 establishing the dipole physics before Section 2's lead geometry is perfect. Approved.'")
            update_data = {"outline_approved": True}
            
        elif next_node == "markdown_review":
            if current_values.completed_md_sections:
                last_file = Path(current_values.completed_md_sections[-1]).name
                print(f"🤖 Reviewing Draft: {last_file}")
                print("\n🧠 Clever Human Response:")
                print(f"  'The technical depth in {last_file} is SOTA level. The LaTeX formatting for vector dot products is impeccable. Verified.'")
                update_data = {"markdown_approved": True}
            else:
                print("⚠ No sections generated for review.")
                update_data = {"markdown_approved": True} # Skip review to avoid stuck state
            
        elif next_node == "batch_asset_review":
            print("🤖 Final Asset Audit...")
            if not current_values.failed_directives:
                print("  ✓ All parallel assets passed VQA.")
                update_data = {"asset_revision_needed": False}
            else:
                print(f"  ⚠ Found {len(current_values.failed_directives)} issues. Auto-resolving for test...")
                update_data = {"asset_revision_needed": False}

        # Apply update
        if update_data:
            app.update_state(config, update_data)
        
        # Reset approval for the next loop iteration (Crucial for section-level loops)
        if next_node == "markdown_review":
             # We let it pass this time, but the loop needs it false for the NEXT section
             pass 

        current_state = None # Resume

if __name__ == "__main__":
    asyncio.run(run_clever_e2e())