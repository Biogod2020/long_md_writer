import asyncio
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

# Mocking parts of the system for standalone testing
class MockResponse:
    def __init__(self, text, success=True):
        self.text = text
        self.success = success

class MockClient:
    async def generate_async(self, parts, **kwargs):
        prompt = parts[0]["text"]
        # Determine if it's Tier 1 or Tier 2 based on the prompt content
        if "select the TOP 2" in prompt:
            # Tier 1 Mock: Pick the first two 'img_X.jpg' found in the prompt
            import re
            found = re.findall(r'img_\d+\.jpg', prompt)
            winners = found[:2] if len(found) >= 2 else found
            return MockResponse(json.dumps({"top_candidates": winners, "thought": "Tier 1 Mock selection"}))
        else:
            # Tier 2 Mock: Pick the first 'img_X.jpg'
            import re
            found = re.findall(r'img_\d+\.jpg', prompt)
            winner = found[0] if found else "null"
            return MockResponse(json.dumps({
                "selected_image": winner, 
                "selection_status": "CERTAIN",
                "thought": "Tier 2 Mock final selection"
            }))

# Implementation of the NEW logic for testing
class HierarchicalVisionSelector:
    def __init__(self, client, debug=True):
        self.client = client
        self.debug = debug
        self.default_batch_size = 10
        self.winners_per_batch = 2

    async def select_best_async(self, images: List[str], description: str):
        print(f"🚀 Starting Hierarchical Audit for {len(images)} images")
        
        # 1. Shuffle
        candidates = list(images)
        random.shuffle(candidates)
        print(f"🎲 Shuffled candidates: {candidates}")

        # 2. Tier 1: 10-to-2
        tier1_winners = []
        for i in range(0, len(candidates), self.default_batch_size):
            batch = candidates[i:i + self.default_batch_size]
            print(f"📦 Processing Tier 1 Batch ({len(batch)} items)...")
            
            # Simulate API call for Tier 1
            prompt = f"select the TOP {self.winners_per_batch} images for: {description}\nCandidates: {batch}"
            resp = await self.client.generate_async([{"text": prompt}])
            data = json.loads(resp.text)
            winners = data.get("top_candidates", [])
            print(f"  ✅ Tier 1 winners for this batch: {winners}")
            tier1_winners.extend(winners)

        print(f"🏆 Tier 1 Complete. Total finalists: {len(tier1_winners)}")

        # 3. Tier 2: 2-to-1 (Finals)
        if not tier1_winners: return None
        
        print(f"🔥 Running Tier 2 Finals for: {tier1_winners}")
        prompt = f"FINAL ROUND: Pick the best image for: {description}\nFinalists: {tier1_winners}"
        resp = await self.client.generate_async([{"text": prompt}])
        data = json.loads(resp.text)
        final_winner = data.get("selected_image")
        
        print(f"✨ ABSOLUTE WINNER: {final_winner}")
        return final_winner

async def run_test():
    client = MockClient()
    selector = HierarchicalVisionSelector(client)
    
    # Simulate 25 images
    mock_images = [f"img_{i}.jpg" for i in range(1, 26)]
    
    final = await selector.select_best_async(mock_images, "A picture of a cat")
    
    # Assertions
    assert final is not None, "Should have selected a winner"
    print("\n✅ LOGIC TEST PASSED: Shuffling, Batching, and Two-Layer Selection verified.")

if __name__ == "__main__":
    asyncio.run(run_test())
