"""
VisionSelector: Handles image selection via Gemini Vision API.
"""

import base64
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from ...core.gemini_client import GeminiClient


class VisionSelector:
    """Selects the best image from a list of candidates using Gemini Vision."""

    def __init__(self, client: GeminiClient, debug: bool = False):
        self.client = client
        self.debug = debug

    def select_best(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str] = {}) -> Tuple[Optional[Path], str, str]:
        """
        Use Gemini Vision to evaluate and select the best image.
        Supports up to 20 images by default. If 500 errors occur repeatedly, 
        falls back to batch processing (10 images per batch).
        """
        if not images:
            return None, "No images to select from", ""

        if self.debug:
            print(f"    - Vision selecting from {len(images)} images...")

        # Sort images by number (img_1, img_2...)
        sorted_images = sorted(images, key=lambda p: int(re.search(r'\d+', p.stem).group()) if re.search(r'\d+', p.stem) else 999)
        
        # Use top 20 as requested
        candidate_pool = sorted_images[:20]
        
        max_retries = 3
        error_500_count = 0
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(2 * attempt)
                
                # If we've seen multiple 500 errors, switch to batch processing
                if error_500_count >= 2:
                    if self.debug:
                        print("      - [!] 500 errors repeated. Switching to batch selection (size 10)...")
                    return self._select_in_batches(candidate_pool, description, guidance, descriptions_map)

                # Attempt selection on full pool
                result = self._call_vision_api(candidate_pool, description, guidance, descriptions_map)
                
                if result["success"]:
                    return result["path"], result["reason"], result["description"]
                else:
                    last_error = result["error"]
                    if any(err in last_error for err in ["500", "Proxy", "RemoteDisconnected", "Service Unavailable"]):
                        error_500_count += 1
                        continue
                    else:
                        break # Stop on other types of errors
            except Exception as e:
                error_500_count += 1
                if self.debug: print(f"      - Vision process error: {e}")
                continue

        return None, f"Vision API error after retries: {last_error if 'last_error' in locals() else 'Unknown'}", ""

    def _select_in_batches(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> Tuple[Optional[Path], str, str]:
        """Split images into batches of 10, find winners, then pick final winner."""
        batch_size = 10
        winners = []
        
        # 1. Process batches
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            if self.debug:
                print(f"        - Processing batch {i//batch_size + 1} ({len(batch)} images)...")
            
            res = self._call_vision_api(batch, description, guidance, descriptions_map)
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
        # We merge the reasoning/descriptions for context
        res = self._call_vision_api(winner_paths, description, guidance, descriptions_map)
        
        if res["success"] and res["path"]:
            return res["path"], res["reason"], res["description"]
        
        # Fallback to the first winner if final selection fails
        return winners[0]

    def _call_vision_api(self, images: List[Path], description: str, guidance: str, descriptions_map: Dict[str, str]) -> Dict[str, Any]:
        """Atomic call to Gemini Vision API for a specific set of images."""
        
        def encode_image(path):
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            except: return None

        img_contexts_str = ""
        for img in images:
            desc_text = descriptions_map.get(img.name, "No description")
            img_contexts_str += f"- Image {img.name}: {desc_text[:150]}...\n"
        
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
            b64 = encode_image(img_path)
            if b64:
                mime = "image/png" if img_path.suffix.lower() == ".png" else "image/webp" if img_path.suffix.lower() == ".webp" else "image/jpeg"
                parts.append({"inlineData": {"mimeType": mime, "data": b64}})

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
                    for img in images:
                        if img.name == sel_name:
                            return {"success": True, "path": img, "reason": data.get("reasoning", ""), "description": data.get("description_of_selected", "")}
                    # Hallucination fix
                    return {"success": True, "path": images[0], "reason": data.get("reasoning", ""), "description": data.get("description_of_selected", "")}
                return {"success": True, "path": None, "reason": data.get("reasoning", ""), "description": ""}
            return {"success": False, "error": response.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
