"""
StrategyGenerator: Handles VLM prompt generation for search query strategy.
SOTA 2.0: Added support for reflection loop via audit feedback.
"""

import re
import json
from typing import Dict, Any, List, Optional
from ...core.gemini_client import GeminiClient


class StrategyGenerator:
    """Generates search strategies using VLM."""

    def __init__(self, client: GeminiClient, debug: bool = False):
        self.client = client
        self.debug = debug

    def generate(self, description: str, context: str, failed_queries: Optional[List[str]] = None, rejection_feedback: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate search strategy with queries and acceptance guidance.
        
        Args:
            description: Image description from placeholder
            context: HTML context snippet
            failed_queries: Previously failed queries to avoid
            rejection_feedback: Feedback from VLM audit on why previous candidates were rejected
            
        Returns:
            Dict with 'queries' and 'guidance' keys
        """
        failed_queries_section = ""
        if failed_queries:
            failed_queries_section = f"\n**Previously Failed Queries**: {failed_queries}"
        
        rejection_section = ""
        if rejection_feedback:
            rejection_section = f"\n**Critical Audit Feedback**: Previous images were REJECTED because: {rejection_feedback}. You MUST pivot your keywords to address these specific concerns."
        
        prompt = f"""You are an expert visual content curator for academic and technical publications. Your task is to devise an optimal image sourcing strategy.

**Step 1: Deep Context Analysis**
First, carefully analyze the following:
- Image Description: "{description}"
- Surrounding Article Context (HTML snippet):
```html
{context}
```
{failed_queries_section}{rejection_section}

**Step 2: Strategic Query Design (Keywords Only)**
Generate exactly 2 Google Image Search queries that maximize the chance of finding professional, relevant results.
STRICT CONSTRAINTS:
- Queries must be concise KEYWORDS (2-4 core keywords per query), NOT sentences or descriptive phrases.
- Remove all unnecessary adjectives (e.g., "historical", "vivid", "clear", "bright") and fillers.
- Focus ONLY on nouns, entities, specific locations, and technical terms.
- For Chinese content, use 2-3 core keywords separated by spaces.
- PROHIBITED: Do not include phrases like "A photo of...", "Showing...", "Demonstrating...", or any verbs.

**Comparison Examples:**
- BAD: "广州市第二中学应元校区历史悠久的校门图" 
- GOOD: "广州二中 应元 校门"
- BAD: "An ECG trace showing significant QRS widening from Class I drugs"
- GOOD: "Class I antiarrhythmic ECG"
- BAD: "A photo of the front gate of Guangzhou No.2 High School at Yingyuan Road"
- GOOD: "'Guangzhou No.2 High School' Yingyuan gate"

**Step 3: Acceptance Guidance**
Provide a single, short sentence of guidance for selecting the best image (e.g., "The image should clearly illustrate the specified ECG changes within the provided medical context.").

**Output Format (JSON only):**
```json
{{
  "thinking": "Brief reasoning.",
  "queries": ["query1", "query2"],
  "guidance": "Single sentence selection guidance."
}}
```
"""
        
        # Schema for structured output
        schema = {
            "type": "object",
            "properties": {
                "thinking": {"type": "string"},
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2
                },
                "guidance": {"type": "string"}
            },
            "required": ["thinking", "queries", "guidance"]
        }

        try:
            # Try structured generation first
            if hasattr(self.client, "generate_structured"):
                response = self.client.generate_structured(
                    prompt=prompt,
                    response_schema=schema,
                    schema_name="ImageSearchStrategy",
                    temperature=0.2,
                    stream=True
                )
                
                if response.success and response.json_data:
                    result = response.json_data
                    if self.debug:
                        print(f"    - Strategy Thinking: {result.get('thinking', 'N/A')[:100]}...")
                        print(f"    - Queries: {result.get('queries', [])}")
                        print(f"    - Guidance: {result.get('guidance', 'N/A')}")
                    return result
            
            # Fallback to standard generation
            response = self.client.generate(prompt=prompt, temperature=0.2)
            if response.success and response.text:
                text = response.text
                if "```json" in text:
                    text = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL).group(1)
                elif "```" in text:
                    text = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL).group(1)
                
                result = json.loads(text.strip())
                if self.debug:
                    print(f"    - Strategy Thinking: {result.get('thinking', 'N/A')[:100]}...")
                    print(f"    - Queries: {result.get('queries', [])}")
                    print(f"    - Guidance: {result.get('guidance', 'N/A')}")
                return result
            else:
                if self.debug:
                    print(f"      - Strategy generation failed: Success={response.success}, Error={response.error}")

        except Exception as e:
            if self.debug:
                print(f"      - Strategy generation error: {e}")
        
        # Fallback: Generate 2 queries from description
        keywords = description.replace("。", "").replace("，", " ").split()[:3]
        fallback_query_2 = " ".join(keywords) if len(keywords) > 1 else description
        
        return {
            "queries": [description, fallback_query_2],
            "guidance": "The image should accurately fit the description and context."
        }
