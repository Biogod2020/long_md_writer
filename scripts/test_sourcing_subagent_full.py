import asyncio
import time
import shutil
from pathlib import Path
from src.agents.image_sourcing.agent import ImageSourcingAgent
from src.agents.asset_management.models import VisualDirective
from src.core.types import AgentState, Manifest, UniversalAssetRegistry
from src.core.gemini_client import GeminiClient

async def run_full_subagent_test():
    search_terms = [
        "diffusion architecture"
    ]
    
    print("🚀 INITIATING FULL SUB-AGENT E2E ANALYSIS")
    print("This test verifies: Strategy -> Search -> Massive Download -> Hierarchical VLM Audit")
    
    # Setup Workspace
    job_id = "sourcing_subagent_e2e"
    workspace_path = Path("workspace") / job_id
    if workspace_path.exists(): shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    client = GeminiClient()
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path)
    )
    # Initialize UAR for the agent
    state.asset_registry = UniversalAssetRegistry.load_from_file(str(workspace_path / "assets.json"))
    state.asset_registry.set_persist_path(str(workspace_path / "assets.json"))
    
    # Initialize Agent with Debug enabled to see the "Hierarchical" logs
    agent = ImageSourcingAgent(client=client, debug=True, headless=True)
    
    results_summary = []
    start_time = time.time()
    
    for term in search_terms:
        print(f"\n" + "="*60)
        print(f"🔍 ANALYZING TERM: {term}")
        print("="*60)
        
        directive = VisualDirective(
            id=term.replace(" ", "_"),
            description=f"A professional, high-quality image representing: {term}",
            raw_block=":::visual ... :::",
            start_pos=0,
            end_pos=0
        )
        
        try:
            # This calls the full pipeline
            success, asset, html = await agent.fulfill_directive_async(directive, state)
            
            if success and asset:
                print(f"\n✨ FINAL SELECTION FOR '{term}':")
                print(f"  - Asset ID: {asset.id}")
                print(f"  - Path: {asset.local_path}")
                print(f"  - Description: {asset.semantic_label}")
                results_summary.append({"term": term, "status": "SUCCESS", "asset": asset.id})
            else:
                print(f"\n❌ FAILED to fulfill directive for '{term}'")
                results_summary.append({"term": term, "status": "FAILED", "asset": None})
                
        except Exception as e:
            print(f"\n💥 CRASHED during '{term}': {e}")
            import traceback
            traceback.print_exc()
            results_summary.append({"term": term, "status": "CRASHED", "error": str(e)})

    total_time = time.time() - start_time
    print("\n" + "="*60)
    print("📊 SUB-AGENT E2E SUMMARY REPORT")
    print("="*60)
    print(f"Total Processing Time: {total_time:.2f} seconds")
    for r in results_summary:
        print(f"- {r['term']}: {r['status']} ({r.get('asset') or r.get('error')})")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_full_subagent_test())
