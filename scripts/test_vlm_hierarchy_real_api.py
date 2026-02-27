import asyncio
import json
import random
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.core.gemini_client import GeminiClient
from src.core.json_utils import parse_json_dict_robust

class HierarchicalVisionSelectorReal:
    def __init__(self, client: GeminiClient, debug=True):
        self.client = client
        self.debug = debug
        self.default_batch_size = 10
        self.winners_per_batch = 2

    async def select_best_async(self, image_paths: List[Path], description: str, guidance: str):
        print(f"🚀 [REAL API] Starting Hierarchical Audit for {len(image_paths)} images")
        
        # 1. Shuffle
        candidates = list(image_paths)
        random.shuffle(candidates)
        
        # 2. Tier 1: 10-to-2
        tier1_winners = []
        for i in range(0, len(candidates), self.default_batch_size):
            batch = candidates[i:i + self.default_batch_size]
            print(f"📦 Processing Tier 1 Batch ({len(batch)} items)...")
            
            winners = await self._call_vlm_tier1(batch, description, guidance)
            print(f"  ✅ Tier 1 winners for this batch: {[p.name for p in winners]}")
            tier1_winners.extend(winners)

        print(f"🏆 Tier 1 Complete. Total finalists: {len(tier1_winners)}")

        # 3. Tier 2: Final competition
        if not tier1_winners: return None
        
        print(f"🔥 Running Tier 2 Finals for: {[p.name for p in tier1_winners]}")
        final_winner = await self._call_vlm_tier2(tier1_winners, description, guidance)
        
        if final_winner:
            print(f"✨ ABSOLUTE WINNER: {final_winner['path'].name} (Score: {final_winner['score']})")
        return final_winner

    async def _call_vlm_tier1(self, images: List[Path], description: str, guidance: str) -> List[Path]:
        parts = []
        img_list_str = ""
        for i, img in enumerate(images):
            img_list_str += f"- Image {img.name}\n"
            b64 = base64.b64encode(img.read_bytes()).decode('utf-8')
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        
        prompt = f"""You are a visual content scout. Select the TOP {self.winners_per_batch} images for: "{description}".
Guidance: {guidance}

**Candidate Images:**
{img_list_str}

Output ONLY valid JSON:
```json
{{
  "thought": "Brief comparison.",
  "top_candidates": ["img_X.jpg", "img_Y.jpg"]
}}
```
"""
        parts.insert(0, {"text": prompt})
        
        # EXACT SOURCING LOGIC: stream=True, model_provider="gemini-cli-oauth"
        response = await self.client.generate_async(parts=parts, temperature=0.1, stream=True, model_provider="gemini-cli-oauth")
        if not response.success: 
            print(f"  ❌ API Error: {response.error}")
            return []
            
        data = parse_json_dict_robust(response.text)
        sel_names = data.get("top_candidates", [])
        matched = []
        for name in sel_names:
            hit = next((p for p in images if p.name == name or p.stem == Path(name).stem), None)
            if hit: matched.append(hit)
        return matched[:self.winners_per_batch]

    async def _call_vlm_tier2(self, images: List[Path], description: str, guidance: str) -> Optional[Dict]:
        parts = []
        img_list_str = ""
        for i, img in enumerate(images):
            img_list_str += f"- Image {img.name}\n"
            b64 = base64.b64encode(img.read_bytes()).decode('utf-8')
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
            
        prompt = f"""You are a Senior Visual Expert. Final Round. Pick the absolute best image for: "{description}".
Guidance: {guidance}

**Finalist Images:**
{img_list_str}

Output ONLY valid JSON:
```json
{{
  "thought": "Technical analysis.",
  "selection_status": "CERTAIN",
  "selected_image": "img_X.jpg",
  "confidence_score": 95,
  "description_of_selected": "Factual description."
}}
```
"""
        parts.insert(0, {"text": prompt})
        
        response = await self.client.generate_async(parts=parts, temperature=0.1, stream=True, model_provider="gemini-cli-oauth")
        if not response.success: return None
        
        data = parse_json_dict_robust(response.text)
        sel_name = data.get("selected_image")
        if sel_name:
            matched = next((p for p in images if p.name == sel_name or p.stem == Path(sel_name).stem), images[0])
            return {
                "path": matched,
                "score": data.get("confidence_score", 0),
                "data": data
            }
        return None

async def run_real_api_test():
    client = GeminiClient()
    selector = HierarchicalVisionSelectorReal(client)
    
    # Use real images from your previous successful download test
    # Looking for 'mit_main_building' folder
    source_dir = Path("workspace/massive_download_test/mit_main_building")
    if not source_dir.exists():
        print(f"❌ Source directory {source_dir} not found. Please run the download test first.")
        return
        
    image_paths = list(source_dir.glob("img_*.jpg"))[:12] # Test with 12 images
    if not image_paths:
        print("❌ No images found in directory.")
        return
        
    description = "The main building of MIT with the Great Dome."
    guidance = "Select a clear, architectural photo showing the iconic dome from a distance."
    
    await selector.select_best_async(image_paths, description, guidance)

if __name__ == "__main__":
    asyncio.run(run_real_api_test())
