import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.workflow_markdown import run_sota2_workflow

async def main():
    print("\n" + "=" * 70)
    print(" 🚀 Parallel Fulfillment & Section-Level QA E2E Test")
    print("=" * 70)

    # Simplified intent to save time/tokens but exercise the flow
    user_intent = "Write a short 2-section tutorial on 'ECG Vector Projections'. Use at least one :::visual directive per section."
    reference_materials = "# ECG Basics\nA vector P represents the heart dipole. Lead axis L is where it projects."

    # Define mounted asset library if exists
    mounted = {}
    master_assets = Path("data/global_asset_lib/master_assets.json")
    if master_assets.exists():
        mounted["cardiology_global"] = str(master_assets)

    try:
        final_state = await run_sota2_workflow(
            user_intent=user_intent,
            reference_materials=reference_materials,
            assets_input_dir="inputs",
            workspace_base="./workspace_e2e_parallel",
            skip_vision=True, # Skip indexing to speed up
            skip_asset_audit=False,
            debug_mode=True,
            mounted_workspaces=mounted
        )

        print("\n" + "=" * 70)
        print(" ✅ Workflow Execution Finished")
        print("=" * 70)

        # Verification
        print(f"\n🔍 Verification Report (Job: {final_state.job_id}):")
        
        # 1. Check sections written
        print(f"  - Sections completed: {len(final_state.completed_md_sections)}")
        if len(final_state.completed_md_sections) < 2:
            print("  ❌ Error: Expected at least 2 sections.")
        
        # 2. Check for parallel fulfillment complete
        print(f"  - Batch fulfillment complete: {final_state.batch_fulfillment_complete}")
        if not final_state.batch_fulfillment_complete:
            print("  ❌ Error: batch_fulfillment_complete should be True.")

        # 3. Verify in-place replacement in file
        for md_path_str in final_state.completed_md_sections:
            md_path = Path(md_path_str)
            if md_path.exists():
                content = md_path.read_text(encoding="utf-8")
                has_visual = ":::visual" in content
                has_figure = "<figure>" in content
                print(f"  - File {md_path.name}: :::visual removed: {not has_visual}, <figure> injected: {has_figure}")
                if has_visual:
                    print(f"  ❌ Error: :::visual still exists in {md_path.name}")
                if not has_figure:
                    print(f"  ❌ Error: <figure> tags not found in {md_path.name}")

    except Exception as e:
        print(f"\n❌ E2E Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
