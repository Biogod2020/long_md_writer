import asyncio
import os
import shutil
import time
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.types import AgentState
from src.core.gemini_client import GeminiClient
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent

class RealAPIStressTest:
    def __init__(self, workspace_name="real_api_stress_workspace"):
        self.root = Path(os.getcwd())
        self.workspace = self.root / "workspace" / workspace_name
        self.md_dir = self.workspace / "md"
        
    def setup_environment(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        self.md_dir.mkdir(parents=True)
        
        # 构造 3 个文件，每个文件 4 个指令，刻意造成文件锁竞争
        file_configs = [
            ("physics_basics.md", [
                {"id": "s1-v1", "action": "GENERATE_SVG", "desc": "A simple pendulum diagram with gravity vector"},
                {"id": "s1-v2", "action": "GENERATE_MERMAID", "desc": "Flowchart of energy conservation: Potential to Kinetic"},
                {"id": "s1-v3", "action": "GENERATE_SVG", "desc": "Free body diagram of a block on an inclined plane"},
                {"id": "s1-v4", "action": "GENERATE_MERMAID", "desc": "Sequence diagram of a ball bouncing off a wall"}
            ]),
            ("math_formulas.md", [
                {"id": "s2-v1", "action": "GENERATE_SVG", "desc": "Unit circle with sine and cosine projections"},
                {"id": "s2-v2", "action": "GENERATE_MERMAID", "desc": "Mindmap of Calculus concepts: Limits, Derivatives, Integrals"},
                {"id": "s2-v3", "action": "GENERATE_SVG", "desc": "3D coordinate system showing a vector (1,2,3)"},
                {"id": "s2-v4", "action": "GENERATE_MERMAID", "desc": "Decision tree for solving quadratic equations"}
            ]),
            ("biology_cell.md", [
                {"id": "s3-v1", "action": "GENERATE_SVG", "desc": "Simplified diagram of a Mitochondria with inner membrane"},
                {"id": "s3-v2", "action": "GENERATE_MERMAID", "desc": "Cycle of ATP synthesis"},
                {"id": "s3-v3", "action": "GENERATE_SVG", "desc": "Structure of a DNA double helix"},
                {"id": "s3-v4", "action": "GENERATE_MERMAID", "desc": "Process of Osmosis through a semi-permeable membrane"}
            ])
        ]
        
        file_paths = []
        for filename, directives in file_configs:
            content = f"# {filename.split('.')[0].replace('_', ' ').title()}\n\nIntro text for {filename}.\n\n"
            for d in directives:
                content += f":::visual {{\"id\":\"{d['id']}\",\"action\":\"{d['action']}\",\"description\":\"{d['desc']}\"}}\n"
                content += f"Detailed explanation for {d['id']} goes here.\n"
                content += ":::\n\nIntermediate filler text to ensure Patcher has enough context.\n\n"
            
            p = self.md_dir / filename
            p.write_text(content, encoding="utf-8")
            file_paths.append(str(p))
        return file_paths

    async def run(self):
        print("\n" + "="*60)
        print(" 🚀 STARTING REAL API PARALLEL FULFILLMENT STRESS TEST")
        print("="*60)
        print("  - Files: 3")
        print("  - Total API Calls: 12 (SVG/Mermaid)")
        print("  - Concurrency: 5 (Simulating heavy IO contention)")
        
        file_paths = self.setup_environment()
        
        # 1. Initialize State & Client
        client = GeminiClient()
        state = AgentState(
            job_id="real_stress_job",
            workspace_path=str(self.workspace),
            completed_md_sections=file_paths,
            uar_path=str(self.workspace / "assets.json")
        )
        
        # 2. Run Fulfillment (Actual Agent, No Mocks!)
        # SOTA: Lowering concurrency to 2 to avoid 429 Rate Limits while still testing async locks
        agent = AssetFulfillmentAgent(client=client, max_concurrency=2, debug=True)
        
        start_time = time.time()
        final_state = await agent.run_parallel_async(state)
        duration = time.time() - start_time
        
        # 3. Verification
        print("\n" + "="*60)
        print(" 🔍 VERIFICATION PHASE (REAL API)")
        print("="*60)
        
        total_missing = 0
        corrupted = []
        
        for p_str in file_paths:
            content = Path(p_str).read_text(encoding="utf-8")
            if ":::visual" in content:
                missing = content.count(":::visual")
                print(f"  ❌ FAILURE: {Path(p_str).name} still has {missing} directives!")
                total_missing += missing
            
            if "<figure" not in content:
                print(f"  ❌ FAILURE: {Path(p_str).name} has NO injected figures!")
            
            # Integrity check
            if "Intro text" not in content or "filler text" not in content:
                print(f"  ❌ CRITICAL: Content corruption in {Path(p_str).name}")
                corrupted.append(Path(p_str).name)

        uar = final_state.get_uar()
        print(f"\n  [Final Stats]")
        print(f"  - Duration: {duration:.2f}s")
        print(f"  - Assets in UAR: {len(uar.assets)}")
        print(f"  - Failed Directives: {len(final_state.failed_directives)}")
        print(f"  - Content Integrity: {'OK' if not corrupted else 'FAILED'}")
        
        if total_missing == 0 and not corrupted and len(final_state.failed_directives) == 0:
            print("\n  ✅ SOTA SUCCESS: Parallel fulfillment with REAL API is 100% stable.")
        else:
            print("\n  ❌ SOTA FAILURE: Real-world conditions revealed instability.")
            # Print failed details
            for fd in final_state.failed_directives:
                print(f"    - Failed: {fd['id']} in {fd['file']}: {fd['error']}")
            sys.exit(1)

if __name__ == "__main__":
    test = RealAPIStressTest()
    asyncio.run(test.run())
