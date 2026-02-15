import asyncio
import os
import json
from pathlib import Path
from src.agents.image_sourcing.vision import VisionSelector
from src.core.gemini_client import GeminiClient

async def audit_category(client, selector, category_dir, description, guidance):
    print(f"\n🔍 [AUDIT] Category: {category_dir.name}")
    local_images = sorted(list(category_dir.glob("img_*.jpg")) + list(category_dir.glob("img_*.png")))[:20]
    
    if not local_images:
        print(f"  ⚠️ No images found in {category_dir}")
        return

    descriptions_map = {}
    for img_path in local_images:
        txt_path = img_path.with_suffix('.txt')
        if txt_path.exists():
            descriptions_map[img_path.name] = txt_path.read_text(encoding='utf-8')

    print(f"  🚀 Sending {len(local_images)} images to VLM...")
    results = await selector.select_best_async(local_images, description, guidance, descriptions_map)
    
    if results:
        res = results[0]
        meta = res.get("metadata", {})
        print(f"  ✅ Result: {res.get('path').name if res.get('path') else 'None'}")
        print(f"  🚦 Status: {res.get('status')}")
        print(f"  ⭐ Score: {res.get('score')}/100")
        if res.get('path'):
            print(f"  🧠 Thought: {meta.get('thought', 'N/A')[:200]}...")
        else:
            print(f"  ❌ Failure Analysis: {meta.get('failure_analysis', 'N/A')}")
    else:
        print("  ❌ No results returned.")

async def run_all_audits():
    client = GeminiClient()
    # SOTA: Enabled debug to see the new stream monitoring and retry logic
    selector = VisionSelector(client, debug=True)
    base_ws = Path("workspaces/workspace/stress_sourcing_v6_1770824451")
    
    tasks = [
        (base_ws / "candidates_gz2hs-logo", "广州市第二中学的校徽", "The official school logo of Guangzhou No. 2 High School."),
        (base_ws / "candidates_gz2hs-uniform", "广州市第二中学的校服", "The official school uniform worn by students of Guangzhou No. 2 High School."),
        (base_ws / "candidates_fig-transformer", "Transformer Figure 1", "The original architecture diagram from 'Attention Is All You Need'.")
    ]
    
    for folder, desc, guide in tasks:
        await audit_category(client, selector, folder, desc, guide)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_all_audits())
