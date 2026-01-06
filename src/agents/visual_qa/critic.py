"""Visual Critic Agent: Identifies visual issues in screenshots."""

import base64
import io
from pathlib import Path
from typing import Optional, Dict, List

from PIL import Image

from ...core.gemini_client import GeminiClient
from .prompts import CRITIC_SYSTEM_PROMPT
from .utils import parse_json_response, add_line_numbers

def run_critic(
    client: GeminiClient,
    screenshot_paths: List[Path],
    debug: bool = False
) -> Optional[Dict]:
    """
    Analyze screenshots and return a checklist of visual issues.
    Purely vision-based to avoid hallucinations from code context.
    
    Returns:
        {"verdict": "PASS" | "FAIL", "issues": [...]}
    """
    # Build prompt - NO CODE PROVIDED
    prompt = f"""Analyze the attached {len(screenshot_paths)} screenshots of a web page section.
Identify any visual bugs, rendering errors (like unrendered LaTeX symbols or boxes), overlapping elements, or aesthetic issues.
"""
    
    # Build parts with compressed images
    parts = []
    for i, path in enumerate(screenshot_paths):
        try:
            with Image.open(path) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                if img.width > 1200:
                    ratio = 1200 / img.width
                    img = img.resize((1200, int(img.height * ratio)), Image.Resampling.LANCZOS)
                
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80, optimize=True)
                image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image_data}})
            parts.append({"text": f"[Screenshot PART {i+1}]"})
        except Exception as e:
            print(f"    [Critic] Error loading image {path}: {e}")
    
    parts.append({"text": prompt})
    
    # Check for Structured Output capability
    if hasattr(client, "generate_structured"):
        try:
            # Note: We don't include images in the structured prompt logic here because
            # generate_structured expects a string prompt.
            # Client V2 needs update to support multi-modal structured output or we construct payload manually.
            # However, our GeminiClientNew.generate_structured_async takes prompt, schema...
            # It builds messages: [{"role": "user", "content": prompt}].
            # It doesn't currently support image parts + structured output easily in the wrapper.
            # Let's fallback to standard generation for vision for now until client is updated
            # OR we can assume client handles parts if passed (but signature is prompt:str).
            
            # Actually, standard generation works fine for vision. 
            # Let's keep using generate() for now to avoid breaking multi-modal input.
            pass
        except:
            pass
    
    try:
        response = client.generate(
            parts=parts,
            system_instruction=CRITIC_SYSTEM_PROMPT,
            temperature=0.0,
            stream=True  # 同时也为 Critic 开启流式，防止截图分析耗时过长导致 500 错误
        )
        
        if debug:
            print(f"\n    [Critic Debug] Raw Response:\n{'-'*40}\n{response.text}\n{'-'*40}")
        
        if not response.success:
            print(f"    [Critic] API Error: {response.error}")
            return None
        
        return parse_json_response(response.text)
    except Exception as e:
        print(f"    [Critic] Exception: {e}")
        return None
