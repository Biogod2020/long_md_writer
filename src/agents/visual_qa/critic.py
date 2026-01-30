"""Visual Critic Agent: Identifies visual issues in screenshots."""

import base64
import io
from pathlib import Path
from typing import Optional, Dict, List

from PIL import Image

from ...core.gemini_client import GeminiClient
from ...core.types import AgentState
from .prompts import CRITIC_SYSTEM_PROMPT
from .utils import parse_json_response, add_line_numbers

def run_critic(
    client: GeminiClient,
    state: AgentState,
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
    
    # Build native parts with compressed images
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
                
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                })
            parts.append({"text": f"[Screenshot PART {i+1}]"})
        except Exception as e:
            print(f"    [Critic] Error loading image {path}: {e}")
    
    parts.append({"text": prompt})
    
    try:
        response = client.generate(
            parts=parts,
            system_instruction=CRITIC_SYSTEM_PROMPT,
            temperature=0.0,
            stream=True
        )
        
        if debug:
            print(f"\n    [Critic Debug] Raw Response:\n{'-'*40}\n{response.text}\n{'-'*40}")
        
        if not response.success:
            print(f"    [Critic] API Error: {response.error}")
            return None
        
        # Capture thoughts
        if response.thoughts:
            state.thoughts += f"\n[VisualQA Critic] {response.thoughts}"
            
        return response.json_data if response.json_data else parse_json_response(response.text)
    except Exception as e:
        print(f"    [Critic] Exception: {e}")
        return None
