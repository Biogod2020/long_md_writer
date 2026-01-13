"""
LocalSelector: Handles selection of best matching assets from UAR using LLM.
"""

import json
import re
from typing import List, Optional, Tuple, Any
from ...core.gemini_client import GeminiClient
from ...core.types import AssetEntry, AssetQualityLevel


class LocalSelector:
    """Selects the best matching asset from a list of UAR candidates using Gemini."""

    def __init__(self, client: GeminiClient, debug: bool = False):
        self.client = client
        self.debug = debug

    async def select_best_async(self, candidates: List[AssetEntry], description: str) -> Tuple[Optional[AssetEntry], str]:
        """
        Evaluate candidates and select the best fit.
        
        Returns:
            (Best AssetEntry or None, Reasoning string)
        """
        if not candidates:
            return None, "No local candidates available."

        # Filter candidates by basic quality check (only HIGH or MEDIUM)
        qualified = [c for c in candidates if c.is_quality_acceptable(AssetQualityLevel.MEDIUM)]
        if not qualified:
            return None, "No local candidates meet the minimum quality threshold."

        candidate_data = []
        for c in qualified:
            candidate_data.append({
                "id": c.id,
                "label": c.semantic_label,
                "quality": c.quality_level.value,
                "notes": c.quality_notes or ""
            })

        prompt = f"""You are a visual content selector. Your task is to determine if any of the following EXISTING local assets perfectly match the requested image description.

**Requested Image:** "{description}"

**Available Local Assets:**
{json.dumps(candidate_data, indent=2, ensure_ascii=False)}

**Rules:**
1.  **Strict Semantic Matching**: The asset must accurately represent the content described.
2.  **Quality Preference**: Prefer HIGH quality over MEDIUM.
3.  **Reject if Unsure**: If none of the assets are a perfect or very strong match, set `selected_id` to null. We prefer to search the web for a better image than use a mediocre local one.

**Output Format (JSON only):**
```json
{{
  "thinking": "Brief reasoning for selection or rejection.",
  "selected_id": "asset-id-string or null"
}}
```
"""

        try:
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="You are a professional asset curator. Select the best matching local asset or null if no perfect match exists.",
                temperature=0.1
            )
            
            if response.success:
                text = response.text
                if "```json" in text:
                    text = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL).group(1)
                
                data = json.loads(text.strip())
                sel_id = data.get("selected_id")
                thinking = data.get("thinking", "")
                
                if sel_id:
                    for c in qualified:
                        if c.id == sel_id:
                            return c, thinking
                
                return None, f"No suitable local match found. Reasoning: {thinking}"
            
            return None, f"Selection failed: {response.error}"
            
        except Exception as e:
            return None, f"Selection error: {e}"
