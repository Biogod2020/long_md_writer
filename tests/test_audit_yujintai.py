import asyncio
import os
import json
from pathlib import Path
from src.agents.image_sourcing.vision import VisionSelector
from src.core.gemini_client import GeminiClient

async def test_specific_audit():
    print("🎯 [AUDIT TEST] Targeting: 复旦大学郁金泰 (Jintai Yu)")
    print("📂 Source: Previously downloaded candidates (Batch 20)")
    
    client = GeminiClient()
    vision_selector = VisionSelector(client, debug=True)
    
    # 路径指向上次下载的文件夹
    candidates_dir = Path("workspaces/workspace/stress_sourcing_v6_1770824451/candidates_person-yujintai")
    
    if not candidates_dir.exists():
        print(f"❌ Error: Directory not found: {candidates_dir}")
        return

    # 收集图片和对应的文字描述
    local_images = sorted(list(candidates_dir.glob("img_*.jpg")) + list(candidates_dir.glob("img_*.png")))
    # 限制在 20 张以内
    local_images = local_images[:20]
    
    descriptions_map = {}
    for img_path in local_images:
        txt_path = img_path.with_suffix('.txt')
        if txt_path.exists():
            descriptions_map[img_path.name] = txt_path.read_text(encoding='utf-8')

    description = "复旦大学研究员郁金泰的照片，医学学术背景，包含人物面部特征"
    guidance = "The image should clearly show researcher Jintai Yu in a professional or academic setting."

    print(f"🚀 Sending {len(local_images)} images to VLM in a SINGLE BATCH...")
    
    # 触发新升级的异步审计
    results = await vision_selector.select_best_async(
        local_images, 
        description, 
        guidance, 
        descriptions_map
    )

    print("\n" + "="*60)
    print("📊 VLM AUDIT RESULTS (Enriched Format)")
    print("="*60)
    
    if results:
        for i, res in enumerate(results):
            meta = res.get("metadata", {})
            print(f"Batch Result {i+1}:")
            print(f"  - Selected: {res.get('path')}")
            print(f"  - Score: {res.get('score')}/100")
            print(f"  - Thought: {meta.get('thought', 'N/A')}")
            print(f"  - Quality: {meta.get('quality_assessment', 'N/A')}")
            if not res.get('path'):
                print(f"  - Failure Analysis: {meta.get('failure_analysis', 'N/A')}")
            print("-" * 30)
    else:
        print("❌ No results returned from VisionSelector.")

if __name__ == "__main__":
    asyncio.run(test_specific_audit())
