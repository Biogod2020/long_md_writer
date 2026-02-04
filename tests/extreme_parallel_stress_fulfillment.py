import asyncio
import os
import shutil
import time
import json
import random
from pathlib import Path
from unittest.mock import MagicMock

import sys
# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.types import AgentState, AssetEntry, AssetSource, AssetPriority, AssetVQAStatus, AssetFulfillmentAction
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.agents.asset_management.models import VisualDirective

class ExtremeStressFulfillment:
    def __init__(self, workspace_name="stress_test_workspace"):
        self.root = Path(os.getcwd())
        self.workspace = self.root / "workspace" / workspace_name
        self.md_dir = self.workspace / "md"
        self.gen_dir = self.workspace / "agent_generated"
        
    def setup_environment(self, file_count=20, directives_per_file=15):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        self.md_dir.mkdir(parents=True)
        self.gen_dir.mkdir(parents=True)
        
        file_paths = []
        for i in range(file_count):
            content = f"# Section {i}\n\nIntroduction prose.\n\n"
            for j in range(directives_per_file):
                indent = " " * (random.randint(0, 4) * 2)
                directive_id = f"s{i}-v{j}"
                content += f"{indent}:::visual {{ \"id\": \"{directive_id}\", \"action\": \"GENERATE_SVG\", \"description\": \"Stress test asset {directive_id}\" }}\n"
                content += f"{indent}Context for {directive_id} with some math: $\\frac{{a}}{{b}}$\n"
                content += f"{indent}:::\n\nIntermediate text.\n\n"
            
            p = self.md_dir / f"section_{i:02d}.md"
            p.write_text(content, encoding="utf-8")
            file_paths.append(str(p))
        return file_paths

    async def run_stress_test(self):
        print("\n" + "="*60)
        print(" 🔥 STARTING EXTREME PARALLEL FULFILLMENT STRESS TEST")
        print("="*60)
        
        # 1. Prepare 300 directives (20 files * 15)
        file_paths = self.setup_environment(file_count=20, directives_per_file=15)
        print(f"  [Setup] Created 20 files with 15 directives each (Total: 300 targets)")

        # 2. Setup State
        state = AgentState(
            job_id="stress_job",
            workspace_path=str(self.workspace),
            completed_md_sections=file_paths,
            uar_path=str(self.workspace / "assets.json")
        )
        
        # 3. Setup Agent with High Concurrency
        # Note: We monkey-patch the fulfillment steps to simulate work without calling Google API
        agent = AssetFulfillmentAgent(client=MagicMock(), max_concurrency=20)
        
        # SOTA: Define the mock fulfillment step properly
        async def mock_fulfill_step(self, d, uar, gen_path, src_path, ns, ws_path, state, trace, target_file=None):
            # Simulate processing delay
            await asyncio.sleep(random.uniform(0.001, 0.01))
            
            # Use gen_path for everything in stress test
            asset_file = gen_path / f"{d.id}.svg"
            asset_file.parent.mkdir(parents=True, exist_ok=True)
            asset_file.write_text(f"<svg>Stress {d.id}</svg>")
            
            # Rel path from workspace
            rel_path = str(asset_file.relative_to(Path(state.workspace_path)))
            
            asset = AssetEntry(
                id=d.id, source=AssetSource.AI, local_path=rel_path,
                semantic_label=d.description, content_hash=f"hash-{d.id}",
                alt_text=d.description, tags=["stress"], vqa_status=AssetVQAStatus.PASS
            )
            
            # Simulate HTML generation (Mirroring generate_figure_html)
            d.fulfilled = True
            d.result_html = f"<figure id='{d.id}' class='stress-test'><img src='{asset.local_path}'></figure>"
            return d, asset

        # Apply monkey patch properly
        import types
        agent._fulfill_directive_async = types.MethodType(mock_fulfill_step, agent)
        
        # Also mock strategy decision to avoid Gemini API calls
        async def mock_strategy(self, d, uar, state):
            return d
        agent._decide_fulfillment_strategy = types.MethodType(mock_strategy, agent)
        
        # 4. Execute
        start_time = time.time()
        final_state = await agent.run_parallel_async(state)
        duration = time.time() - start_time
        
        # 5. Verification
        print("\n" + "="*60)
        print(" 🔍 VERIFICATION PHASE")
        print("="*60)
        
        if final_state.errors:
            print("\n❌ AGENT ERRORS DETECTED:")
            for err in final_state.errors:
                print(f"  - {err}")
        
        total_missing = 0
        total_corrupted = 0
        
        for p_str in file_paths:
            content = Path(p_str).read_text(encoding="utf-8")
            if ":::visual" in content:
                print(f"  ❌ FAILURE: File {Path(p_str).name} still contains directives!")
                total_missing += content.count(":::visual")
            
            if "<figure" not in content:
                print(f"  ❌ FAILURE: File {Path(p_str).name} has no injected figures!")
            
            # Check for content loss (simple heuristic)
            if "Section" not in content or "Introduction" not in content:
                print(f"  ❌ CRITICAL: Content corruption detected in {Path(p_str).name}")
                total_corrupted += 1

        # Check UAR
        uar = final_state.get_uar()
        print(f"  [Stats] Duration: {duration:.2f}s")
        print(f"  [Stats] Throughput: {300/duration:.2f} assets/sec")
        print(f"  [Stats] UAR Count: {len(uar.assets)}")
        print(f"  [Stats] Missing Replacements: {total_missing}")
        print(f"  [Stats] Corrupted Files: {total_corrupted}")
        
        if total_missing == 0 and total_corrupted == 0 and len(uar.assets) == 300:
            print("\n  ✅ PASSED: System handled 300 parallel targets with 100% integrity.")
        else:
            print("\n  ❌ FAILED: Stress test revealed issues in parallel write-back.")
            sys.exit(1)

if __name__ == "__main__":
    stress = ExtremeStressFulfillment()
    asyncio.run(stress.run_stress_test())
