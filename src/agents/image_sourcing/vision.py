"""
VisionSelector: Optimized for High-Speed Audit using pre-resized VQA thumbnails.
SOTA 2.1: Supports Dual-Mode selection (Elite-First with Hierarchical Fallback).
"""

import base64
import json
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from ...core.gemini_client import GeminiClient
from ...core.json_utils import parse_json_dict_robust
from ...core.config import (
    DEFAULT_ELITE_BATCH_SIZE, 
    DEFAULT_HIERARCHY_BATCH_SIZE, 
    DEFAULT_HIERARCHY_WINNERS_PER_BATCH
)


class VisionSelector:
    """
    Selects the best image using Gemini Vision.
    Supports both bulk 'Flat' auditing and high-precision 'Hierarchical' competition.
    """

    def __init__(self, client: GeminiClient, debug: bool = False, use_hierarchy: bool = True):
        self.client = client
        self.debug = debug
        self.use_hierarchy = use_hierarchy
        # Configs aligned with SOTA 2.1 standards
        self.elite_batch_size = DEFAULT_ELITE_BATCH_SIZE
        self.tier1_batch_size = DEFAULT_HIERARCHY_BATCH_SIZE
        self.winners_per_batch = DEFAULT_HIERARCHY_WINNERS_PER_BATCH
        
        # SOTA 2.1: Semaphore to ensure sequential, stable multi-modal API calls
        self.vlm_semaphore = asyncio.Semaphore(1)

    async def select_best_async(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str] = {}) -> List[Dict[str, Any]]:
        """
        Main entry point for VLM selection.
        Strategy: 
        1. Elite Pass: Try the first 20 images (top 10+10 from queries) in a flat batch.
        2. Fallback: If no CERTAIN winner, run full hierarchical 10-to-2-to-1 on all images.
        """
        if not images: return []
        
        # --- STEP 1: ELITE PASS ---
        elite_images = images[:self.elite_batch_size]
        if self.debug: print(f"    - [Vision-Elite] Auditing top {len(elite_images)} elite candidates first...")
        
        async with self.vlm_semaphore:
            elite_results = await self._audit_flat_async(elite_images, description, guidance, descriptions_map)
        
        # If we found a high-confidence winner, return immediately
        certain_winners = [r for r in elite_results if r.get("status") == "CERTAIN"]
        if certain_winners:
            if self.debug: print(f"    - [Vision-Elite] 🎯 Found CERTAIN winner in elite batch. Skipping fallback.")
            return certain_winners

        # --- STEP 2: HIERARCHICAL FALLBACK ---
        if not self.use_hierarchy:
            return elite_results # Already tried the best ones in flat mode
            
        if self.debug: print(f"    - [Vision-Hierarchical] No certain winner in elite batch. Starting 10-to-2-to-1 fallback for all {len(images)} images...")
        return await self._audit_hierarchical_async(images, description, guidance, descriptions_map)

    async def _audit_flat_async(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """Process images in batches and take all non-rejected results."""
        tasks = []
        for i in range(0, len(images), self.elite_batch_size):
            batch = images[i:i + self.elite_batch_size]
            tasks.append(self._call_vision_api_internal_async(batch, description, guidance, descriptions_map, is_tier1=False))
        
        # Note: In elite pass, there's usually only 1 task.
        results = await asyncio.gather(*tasks)
        return [res for res in results if res and res.get("success") and res.get("status") != "REJECTED"]

    async def _audit_hierarchical_async(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """Hierarchical logic: Shuffled 10-to-2 sea-selection followed by a 2-to-1 final."""
        import random
        candidates = list(images)
        random.shuffle(candidates)
        
        # Layer 1: Sea-selection (10-to-2)
        # SOTA: Process batches SEQUENTIALLY using semaphore to avoid API hangs
        tier1_winners = []
        for i in range(0, len(candidates), self.tier1_batch_size):
            batch = candidates[i:i + self.tier1_batch_size]
            async with self.vlm_semaphore:
                res = await self._call_vision_api_internal_async(batch, description, guidance, descriptions_map, is_tier1=True)
                if res and res.get("paths"): 
                    tier1_winners.extend(res["paths"])
                    if self.debug: print(f"      - Batch {i//10 + 1}: Selected {len(res['paths'])} finalists.")
            
        if not tier1_winners: 
            if self.debug: print("    - [Vision] Hierarchical Layer 1 found no candidates.")
            return []

        if self.debug: print(f"    - [Vision] Layer 1 complete. {len(tier1_winners)} finalists advancing to the Finals.")

        # Layer 2: The Finals (2-to-1 competition)
        async with self.vlm_semaphore:
            final_winner = await self._call_vision_api_internal_async(tier1_winners, description, guidance, descriptions_map, is_tier1=False)
        
        return [final_winner] if final_winner and final_winner.get("path") else []

    async def _call_vision_api_internal_async(
        self, images: List[Path], description: str, guidance: str, 
        descriptions_map: Dict[str, str], is_tier1: bool = False
    ) -> Dict[str, Any]:
        """Atomic async call using pre-generated _vqa.jpg files."""
        
        def get_vqa_b64(orig_path: Path) -> Optional[str]:
            vqa_path = orig_path.parent / f"{orig_path.stem}_vqa.jpg"
            target = vqa_path if vqa_path.exists() else orig_path
            try: return base64.b64encode(target.read_bytes()).decode('utf-8')
            except: return None

        # 1. Parallel B64 encoding from disk (Very fast for thumbnails)
        encoding_tasks = [asyncio.to_thread(get_vqa_b64, p) for p in images]
        encoded_results = await asyncio.gather(*encoding_tasks)
        
        parts = []
        img_contexts_str = ""
        for i, img in enumerate(images):
            desc_text = descriptions_map.get(img.name, "No description")
            img_contexts_str += f"- Image {img.name}: {desc_text}\n"
            b64 = encoded_results[i]
            if b64:
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        
        if is_tier1:
            # TIER 1 PROMPT: Multi-selection
            full_prompt = f"""You are a visual content scout for a SOTA publication. Your mission is to select the TOP {self.winners_per_batch} most promising images for: "{description}".

### EVALUATION CRITERIA:
- Semantic Relevance: Does it show what is described?
- Technical Accuracy: Is the diagram logical and error-free?
- Professionalism: No watermarks, high-end aesthetic.

**Target Subject**: "{description}"
**Guidance**: {guidance}

**Candidate Images with Source Context:**
{img_contexts_str}

**Output Format (JSON only)**:
```json
{{
  "thought": "Brief comparison of candidates.",
  "top_candidates": ["img_X.jpg", "img_Y.jpg"],
  "reasons": ["Why X", "Why Y"]
}}
```
"""
        else:
            # TIER 2 PROMPT (or Flat Mode): Pick absolute winner
            full_prompt = f"""You are a Senior Visual Intelligence Expert. Pick the ABSOLUTE best image for: "{description}".

**Target Subject**: "{description}"
**Acceptance Guidance**: {guidance}

**Candidate Images with Source Context:**
{img_contexts_str}

**Output Format (JSON only)**:
```json
{{
  "thought": "Deep technical analysis of the visual details and patterns.",
  "selection_status": "CERTAIN | PROBABLE | REJECTED",
  "selected_image": "img_X.jpg",
  "confidence_score": 0-100,
  "description_of_selected": "1-sentence factual description."
}}
```
"""
        parts.insert(0, {"text": full_prompt})

        try:
            # SOTA 2.1: Large multi-modal request. 
            # Rely on GeminiClient's internal polling and retries.
            if self.debug: print(f"      - [API] Sending {len(images)} images to VLM (expect 30-90s wait)...")
            
            # Use a robust timeout for multi-modal inference
            response = await asyncio.wait_for(
                self.client.generate_async(parts=parts, temperature=0.1, stream=True),
                timeout=120.0
            )
            
            if not response.success: 
                if self.debug: print(f"      - [API] ❌ Failed: {response.error}")
                return {"success": False, "error": response.error}
            
            if self.debug: print("      - [API] ✅ Response received. Parsing...")
            
            raw_text = response.text.strip() if response.text else ""
            data = parse_json_dict_robust(raw_text)
            
            if is_tier1:
                sel_names = data.get("top_candidates", [])
                matched_paths = []
                for name in sel_names:
                    # Robust name mapping
                    clean = Path(name).stem.replace("_vqa", "")
                    hit = next((p for p in images if p.stem == clean or p.name == name), None)
                    if hit: matched_paths.append(hit)
                return {"success": True, "paths": matched_paths[:self.winners_per_batch]}
            else:
                sel_name = data.get("selected_image")
                if sel_name and data.get("selection_status") != "REJECTED":
                    clean = Path(sel_name).stem.replace("_vqa", "")
                    matched_path = next((p for p in images if p.stem == clean or p.name == sel_name), images[0])
                    
                    return {
                        "success": True, "path": matched_path, 
                        "reason": data.get("thought", ""), "description": data.get("description_of_selected", ""),
                        "score": data.get("confidence_score", 0), "status": data.get("selection_status", "CERTAIN"),
                        "metadata": data
                    }
                return {"success": True, "path": None, "score": 0, "status": "REJECTED", "reason": data.get("failure_analysis", "Rejected"), "metadata": data}
        except Exception as e: return {"success": False, "error": str(e)}

    def select_best(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str] = {}) -> List[Dict[str, Any]]:
        """Synchronous wrapper."""
        import concurrent.futures
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(lambda: asyncio.run(self.select_best_async(images, description, guidance, descriptions_map))).result()
            return asyncio.run(self.select_best_async(images, description, guidance, descriptions_map))
        except RuntimeError: return asyncio.run(self.select_best_async(images, description, guidance, descriptions_map))
