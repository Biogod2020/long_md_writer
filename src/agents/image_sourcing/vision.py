"""
VisionSelector: Optimized for High-Speed Audit using pre-resized VQA thumbnails.
SOTA 2.0: Decouples VLM transfer from original file I/O.
"""

import base64
import json
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from ...core.gemini_client import GeminiClient
from ...core.json_utils import parse_json_dict_robust


class VisionSelector:
    """Selects the best image using Gemini Vision via pre-generated VQA thumbnails."""

    def __init__(self, client: GeminiClient, debug: bool = False):
        self.client = client
        self.debug = debug
        self.default_batch_size = 20

    async def select_best_async(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str] = {}) -> List[Dict[str, Any]]:
        """
        Expects 'images' to be Paths to ORIGINAL files.
        Automatically switches to corresponding '_vqa.jpg' for API transfer.
        """
        if not images: return []
        if self.debug: print(f"    - [Vision-Async] Auditing {len(images)} candidates using VQA thumbnails...")

        sorted_images = sorted(images, key=lambda p: int(re.search(r'\d+', p.stem).group()) if re.search(r'\d+', p.stem) else 999)
        
        tasks = []
        for i in range(0, len(sorted_images), self.default_batch_size):
            batch = sorted_images[i:i + self.default_batch_size]
            tasks.append(self._call_vision_api_with_retry_async(batch, description, guidance, descriptions_map))
        
        results = await asyncio.gather(*tasks)
        return [res for res in results if res is not None]

    async def _call_vision_api_with_retry_async(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str], max_retries: int = 3) -> Dict[str, Any]:
        last_error = ""
        for attempt in range(max_retries):
            try:
                if attempt > 0: await asyncio.sleep(2 ** attempt)
                result = await self._call_vision_api_async(images, description, guidance, descriptions_map)
                if result.get("success"): return result
                last_error = result.get("error", "Unknown API error")
                if "400" in last_error or "500" in last_error or "429" in last_error: continue
                break
            except Exception as e:
                last_error = str(e)
                continue
        return {"success": False, "error": last_error, "path": None, "status": "FAILED"}

    async def _call_vision_api_async(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> Dict[str, Any]:
        """Atomic async call using pre-generated _vqa.jpg files."""
        
        def get_vqa_b64(orig_path: Path) -> Optional[str]:
            """Reads the pre-resized VQA thumbnail and encodes to B64."""
            vqa_path = orig_path.parent / f"{orig_path.stem}_vqa.jpg"
            # Fallback to original if thumbnail missing (shouldn't happen in SOTA 2.0)
            target = vqa_path if vqa_path.exists() else orig_path
            try:
                return base64.b64encode(target.read_bytes()).decode('utf-8')
            except Exception: return None

        # 1. Parallel B64 encoding from disk (Very fast for thumbnails)
        encoding_tasks = [asyncio.to_thread(get_vqa_b64, p) for p in images]
        encoded_results = await asyncio.gather(*encoding_tasks)
        
        img_contexts_str = ""
        parts = []
        
        prompt_header = f"""You are a Senior Visual Intelligence Expert. Your mission is to DEDUCE the most canonical and accurate image for: "{description}".

### EVALUATION STRATEGY:
1. **Deductive Analysis**: Look at all candidates as a set to find consistent visual evidence.
2. **Cross-Verification**: Match visual clues inside images against the "Source Context" text.
3. **Truth over Aesthetics**: Prioritize authenticity over artistic variations.

**Target Subject**: "{description}"
**Acceptance Guidance**: {guidance}

**Candidate Images with Source Context:**
"""
        for i, img in enumerate(images):
            desc_text = descriptions_map.get(img.name, "No description")
            img_contexts_str += f"- Image {img.name}: {desc_text}\n"
            b64 = encoded_results[i]
            if b64:
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        
        parts.insert(0, {"text": prompt_header + img_contexts_str})
        parts.append({"text": """
**Output Format (JSON only)**:
```json
{
  "thought": "Analysis of visual details and patterns.",
  "selection_status": "CERTAIN | PROBABLE | REJECTED",
  "selected_image": "img_X.jpg or null",
  "confidence_score": 0-100,
  "failure_analysis": "Detail why if rejected.",
  "description_of_selected": "1-sentence factual description."
}
```
"""})

        try:
            response = await self.client.generate_async(parts=parts, temperature=0.2, stream=True)
            if not response.success: return {"success": False, "error": response.error}
            
            raw_text = response.text.strip() if response.text else ""
            data = parse_json_dict_robust(raw_text)
            sel_name = data.get("selected_image")
            
            if sel_name and data.get("selection_status") != "REJECTED":
                # Map back to ORIGINAL path
                # API might return img_X.jpg or img_X_vqa.jpg or just img_X
                clean_name = Path(sel_name).stem.replace("_vqa", "")
                matched_path = next((p for p in images if p.stem == clean_name), images[0])
                
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
