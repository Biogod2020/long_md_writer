import sys
import os
import asyncio
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.image_sourcing.agent import ImageSourcingAgent
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState

async def run_intent_stress_test():
    print("\n" + "="*70)
    print(" 🎯 IMAGE SOURCING INTENT-DRIVEN STRESS TEST")
    print("="*70)

    # 1. 模拟多样化的用户视觉意图
    test_intents = [
        {
            "id": "medical-anatomy",
            "description": "Detailed anatomical diagram of the human heart showing all four chambers and major valves with clear labels."
        },
        {
            "id": "high-tech-lab",
            "description": "Modern Cardiac Electrophysiology (EP) lab featuring Siemens or Philips 3D mapping systems and multiple high-definition monitors."
        },
        {
            "id": "physics-vector",
            "description": "A physics diagram illustrating an electric dipole and its corresponding vector field lines."
        },
        {
            "id": "pathology-ecg",
            "description": "A high-quality 12-lead ECG tracing showing clear signs of Right Bundle Branch Block (RBBB) with rSR' pattern in V1."
        }
    ]

    output_base = Path("./test_intent_sourcing")
    if output_base.exists(): shutil.rmtree(output_base)
    output_base.mkdir(parents=True, exist_ok=True)

    client = GeminiClient()
    # We use a real agent to test the entire pipeline: Strategy -> Search -> Download -> Vision Selection
    agent = ImageSourcingAgent(client=client, debug=True, headless=True)

    results = []
    
    # We process them sequentially to keep logs clean, though the agent itself uses threads
    for intent in test_intents:
        print(f"\n🚀 Testing Intent: {intent['id']}")
        print(f"📝 Description: {intent['description']}")
        
        # 构造模拟 HTML 上下文以满足 agent 接口
        html_context = f"<p>This section describes {intent['description']}. It is a critical visual for cardiology fellows.</p>"
        
        try:
            # 执行采购逻辑
            # Note: _source_single_image is the atomic worker in the agent
            start_time = asyncio.get_event_loop().time()
            
            # Since _source_single_image is synchronous (with internal threads/loops), we run it directly
            # or in a thread. For simplicity here, we call it.
            html_result = agent._source_single_image(
                img_id=intent['id'],
                description=intent['description'],
                assets_dir=output_base,
                html_context=html_context,
                preserve_candidates=True, # Keep candidates for analysis if it fails
                uar=None # No UAR for this pure web test
            )
            
            duration = asyncio.get_event_loop().time() - start_time
            
            success = html_result is not None and "src=" in html_result
            status = "✅ SUCCESS" if success else "❌ FAILED"
            
            print(f"🏁 Result: {status} | Time: {duration:.2f}s")
            results.append({
                "id": intent['id'],
                "success": success,
                "time": duration,
                "html": html_result
            })
            
        except Exception as e:
            print(f"💥 CRASHED: {e}")
            results.append({"id": intent['id'], "success": False, "error": str(e)})

    # 2. 输出汇总报告与失败模式分析
    print("\n" + "="*70)
    print(" 📊 INTENT STRESS TEST SUMMARY")
    print("="*70)
    
    success_count = 0
    failures = []
    
    for r in results:
        if r['success']:
            print(f"✅ {r['id']:<20} | {r['time']:.2f}s")
            success_count += 1
        else:
            print(f"❌ {r['id']:<20} | FAILED")
            failures.append(r)
    
    print(f"\nTotal: {len(results)} | Success: {success_count} | Failure: {len(results)-success_count}")
    
    if failures:
        print("\n🔍 FAILURE ANALYSIS REQUIRED:")
        print("Please check the 'test_intent_sourcing' directory for candidate logs and partial downloads.")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(run_intent_stress_test())
