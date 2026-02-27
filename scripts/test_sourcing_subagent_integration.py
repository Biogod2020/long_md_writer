import asyncio
import time
import shutil
import json
from pathlib import Path
from src.agents.image_sourcing.agent import ImageSourcingAgent
from src.agents.asset_management.models import VisualDirective
from src.core.types import AgentState, Manifest, UniversalAssetRegistry
from src.core.gemini_client import GeminiClient

class ChaosSearcher:
    """Mock searcher that injects hanging URLs to test subagent robustness."""
    def __init__(self, original_searcher):
        self.original_searcher = original_searcher
    
    def search(self, queries: list) -> list:
        # Get some real results
        results = self.original_searcher.search(queries)
        
        # Inject "Trap" URLs at the start to force the subagent to handle them first
        traps = []
        for i in range(10):
            traps.append({
                "url": f"https://httpstat.us/200?sleep=60000&chaos_id={i}",
                "desc": f"Chaos Trap {i}"
            })
        
        print(f"🧨 [Chaos] Injected 10 hang traps into search results.")
        return traps + results

async def test_subagent_resilience():
    print("🔬 INTEGRATION TEST: Sourcing Sub-Agent Resilience")
    
    # 1. Setup Environment
    job_id = "chaos_subagent_test"
    workspace_path = Path("workspace") / job_id
    if workspace_path.exists(): shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    client = GeminiClient()
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path)
    )
    state.manifest = Manifest(project_title="Chaos Test", description="Test", sections=[])
    state.asset_registry = UniversalAssetRegistry.load_from_file(str(workspace_path / "assets.json"))
    state.asset_registry.set_persist_path(str(workspace_path / "assets.json"))

    # 2. Create Agent
    agent = ImageSourcingAgent(client=client, debug=True, headless=True)
    
    # 3. Create Directive
    directive = VisualDirective(
        id="chaos-fig-01",
        description="A professional diagram showing Wilson Central Terminal resistors in an ECG circuit.",
        raw_block=":::visual ... :::",
        start_pos=0,
        end_pos=0
    )

    # 4. Monkey-patch the searcher inside the fulfill_directive_async logic
    # We need to do this carefully because the BrowserManager creates the searcher
    from src.agents.image_sourcing.search import GoogleImageSearcher
    original_init = GoogleImageSearcher.__init__
    
    def chaos_init(self, browser_manager, debug=False):
        original_init(self, browser_manager, debug)
        # Wrap the search method
        orig_search = self.search
        def wrapped_search(queries):
            results = orig_search(queries)
            traps = [{"url": f"https://httpstat.us/200?sleep=60000&chaos_id={i}", "desc": f"Chaos Trap {i}"} for i in range(8)]
            return traps + results
        self.search = wrapped_search

    GoogleImageSearcher.__init__ = chaos_init

    print("🚀 Running Sub-Agent with Chaos Injection...")
    start_time = time.time()
    
    try:
        success, asset, html = await agent.fulfill_directive_async(directive, state)
        
        elapsed = time.time() - start_time
        print(f"\n🏁 SUB-AGENT TEST FINISHED in {elapsed:.2f}s")
        
        if success and asset:
            print(f"✅ SUCCESS: Captured asset {asset.id}")
            print(f"📍 Path: {asset.local_path}")
        else:
            print("❌ FAILURE: Sub-agent failed to fulfill directive.")

        if elapsed < 150: # 8 traps * 15s / 5 slots = ~30s extra overhead expected
            print("🏆 CONCLUSION: Sub-agent is DEADLOCK-PROOF. It recycled resources correctly.")
        else:
            print("⚠️ CONCLUSION: Sub-agent took too long. Deadlock protection might be weak.")

    except Exception as e:
        print(f"💥 CRASHED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original init
        GoogleImageSearcher.__init__ = original_init
        # shutil.rmtree(workspace_path, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(test_subagent_resilience())
