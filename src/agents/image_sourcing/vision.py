"""
VisionSelector: Handles image selection via Gemini Vision API.
"""

import base64
import json
import re
import time
import io
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from PIL import Image
from ...core.gemini_client import GeminiClient


class VisionSelector:
    """Selects the best image from a list of candidates using Gemini Vision."""

    def __init__(self, client: GeminiClient, debug: bool = False):
        self.client = client
        self.debug = debug
        # Default max image dimension for Vision API to keep payload small
        self.max_vision_dim = 1024 
        # Default batch size to avoid 400 Bad Request / Proxy timeouts
        self.default_batch_size = 5

    def select_best(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str] = {}) -> Tuple[Optional[Path], str, str]:
        """
        Use Gemini Vision to evaluate and select the best image.
        Uses batch processing by default to ensure stability with proxies.
        """
        if not images:
            return None, "No images to select from", ""

        if self.debug:
            print(f"    - Vision selecting from {len(images)} images (Batch Size: {self.default_batch_size})...")

        # Sort images by number (img_1, img_2...)
        sorted_images = sorted(images, key=lambda p: int(re.search(r'\d+', p.stem).group()) if re.search(r'\d+', p.stem) else 999)
        
        # Use top 20 candidates
        candidate_pool = sorted_images[:20]
        
        # We always use batching now for stability
        return self._select_in_batches(candidate_pool, description, guidance, descriptions_map)

    def _select_in_batches(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> Tuple[Optional[Path], str, str]:
        """Split images into small batches, find winners, then pick final winner."""
        batch_size = self.default_batch_size
        winners = []
        
        # 1. Process batches
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            if self.debug:
                print(f"        - Processing batch {i//batch_size + 1} ({len(batch)} images)...")
            
            res = self._call_vision_api_with_retry(batch, description, guidance, descriptions_map)
            if res["success"] and res["path"]:
                winners.append((res["path"], res["reason"], res["description"]))
        
        if not winners:
            return None, "Batch processing failed to find any valid candidates.", ""
            
        if len(winners) == 1:
            return winners[0]
            
        # 2. Final selection among winners
        if self.debug:
            print(f"        - Final selection among {len(winners)} batch winners...")
            
        winner_paths = [w[0] for w in winners]
        res = self._call_vision_api_with_retry(winner_paths, description, guidance, descriptions_map)
        
        if res["success"] and res["path"]:
            return res["path"], res["reason"], res["description"]
        
        # Fallback to the first winner if final selection fails
        return winners[0]

    def _call_vision_api_with_retry(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str], max_retries: int = 3) -> Dict[str, Any]:
        """Call Vision API with retry logic for network and 400/500 errors."""
        last_error = "Unknown"
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt
                    if self.debug: print(f"        - Retry {attempt} after {wait_time}s due to: {last_error}")
                    time.sleep(wait_time)
                
                result = self._call_vision_api(images, description, guidance, descriptions_map)
                if result["success"]:
                    return result
                
                last_error = result.get("error", "Unknown API error")
                
                # If 400 error occurs and batch is still large, we don't retry same batch here,
                # but in production we'd ideally split it smaller. 
                # For now, we retry because it might be a transient proxy 400/500 mismatch.
                if "400" in last_error or "500" in last_error or "RemoteDisconnected" in last_error:
                    continue
                else:
                    break # Stop on logic errors
                    
            except Exception as e:
                last_error = str(e)
                continue
                
        return {"success": False, "error": last_error}

    def _call_vision_api(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> Dict[str, Any]:
        """Atomic call to Gemini Vision API with image compression."""
        
        def encode_and_compress_image(path):
            try:
                with Image.open(path) as img:
                    # Convert to RGB if necessary (Alpha channel can cause issues or larger size)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # Resize if too large
                    if max(img.size) > self.max_vision_dim:
                        img.thumbnail((self.max_vision_dim, self.max_vision_dim), Image.LANCZOS)
                    
                    # Save to buffer as JPEG with 85% quality
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85, optimize=True)
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')
            except Exception as e:
                if self.debug: print(f"      - Image encode error ({path.name}): {e}")
                return None

        img_contexts_str = ""
        for img in images:
            desc_text = descriptions_map.get(img.name, "No description")
            img_contexts_str += f"- Image {img.name}: {desc_text}\n"
        
        prompt = f"""You are an expert visual evaluator for academic and technical publications.

**Your Task:** Carefully examine the candidate images below and select the ONE best image that satisfies the request and criteria.

**Image Request:** "{description}"

**Acceptance Guidance:**
{guidance}

**Candidate Images with Source Context:**
{img_contexts_str}

**Evaluation Protocol:**
1. Observe all images, compare with the description and guidance.
2. Select the ONE image that best aligns.
3. Prefer professional, clear illustrations over watermarked or low-quality ones.

**Output Format (JSON only):**
```json
{{
  "selected_image": "img_X.jpg",
  "reasoning": "Brief explanation.",
  "description_of_selected": "Image description in SAME LANGUAGE as the context (Chinese if Chinese, English if English). CONCISE (1-2 sentences)."
}}
```
If NO candidate is acceptable, set `selected_image` to null.
"""
        parts = [{"text": prompt}]
        for img_path in images:
            b64 = encode_and_compress_image(img_path)
            if b64:
                # We forced it to JPEG in encode_and_compress_image
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})

        try:
            response = self.client.generate(parts=parts, temperature=0.2)
            if response.success:
                text = response.text
                if "```json" in text:
                    text = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL).group(1)
                elif "```" in text:
                    text = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL).group(1)
                
                data = json.loads(text.strip())
                sel_name = data.get("selected_image")
                if sel_name:
                    # Map back to original filename extension
                    for img in images:
                        if img.stem == Path(sel_name).stem:
                            return {"success": True, "path": img, "reason": data.get("reasoning", ""), "description": data.get("description_of_selected", "")}
                    # If model returned a name that doesn't exactly match but exists in pool
                    return {"success": True, "path": images[0], "reason": data.get("reasoning", ""), "description": data.get("description_of_selected", "")}
                return {"success": True, "path": None, "reason": data.get("reasoning", ""), "description": ""}
            return {"success": False, "error": response.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
