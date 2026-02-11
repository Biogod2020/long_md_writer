import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.asset_management.processors.mermaid import render_mermaid_to_png

async def stress_test():
    print("🚀 Starting Mermaid Rendering Stress Test...")
    
    # Test cases: a simple diagram and a complex one
    simple_mermaid = "graph TD; A-->B;"
    complex_mermaid = """
    graph TD
        Start([ECG Analysis]) --> Filter{Is STEMI?}
        Filter -- Yes --> Activate[Cath Lab Activation]
        Filter -- No --> Observe[Serial ECGs]
        
        subgraph Detail [Anatomical Mapping]
            Activate --> LAD[LAD Territory: V1-V4]
            Activate --> RCA[RCA Territory: II, III, aVF]
        end
        
        style Start fill:#f9f,stroke:#333,stroke-width:4px
        style Activate fill:#f00,color:#fff
    """
    
    test_dir = Path("data/test_artifacts/mermaid_stress")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Concurrency test: Run 5 renders in parallel
    print(f"📊 Running 5 parallel render tasks to {test_dir}...")
    
    tasks = []
    for i in range(5):
        code = complex_mermaid if i % 2 == 0 else simple_mermaid
        out_path = test_dir / f"stress_test_{i}.png"
        tasks.append(render_mermaid_to_png(code, out_path))
    
    results = await asyncio.gather(*tasks)
    
    success_count = sum(1 for r in results if r)
    print(f"\n🏁 Finished. Success rate: {success_count}/5")
    
    if success_count < 5:
        print("❌ STRESS TEST FAILED. Check logs above for Playwright errors.")
    else:
        print("✅ STRESS TEST PASSED.")

if __name__ == "__main__":
    asyncio.run(stress_test())