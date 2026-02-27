"""Utility functions for Visual QA."""

import json
import re
from pathlib import Path
from typing import Optional, Dict

def parse_json_response(text: str) -> Optional[Dict]:
    """Extract and parse JSON from VLM response."""
    if not text:
        return None
    
    # Try to find JSON block in markdown
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        text = json_match.group(1).strip()
    
    # Try to find raw JSON object
    if not text.startswith('{'):
        brace_start = text.find('{')
        if brace_start != -1:
            brace_end = text.rfind('}')
            if brace_end > brace_start:
                text = text[brace_start:brace_end + 1]
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Try fixing common issues
        try:
            # Fix unescaped backslashes
            fixed = re.sub(r'(?<!\\)\\(?!["\\/bfnrt])', r'\\\\', text)
            return json.loads(fixed)
        except:
            print(f"  [Utils] JSON parse error: {e}")
            return None

def add_line_numbers(code: str) -> str:
    """Add line numbers to code for VLM reference."""
    lines = code.split('\n')
    width = len(str(len(lines)))
    return '\n'.join(f"{str(i+1).rjust(width)} | {line}" for i, line in enumerate(lines))

def draw_bounding_boxes(image_path: Path, issues: list, output_path: Path):
    """
    Draw red bounding boxes on the image based on issue coordinates.
    Coordinates are [ymin, xmin, ymax, xmax] in 0-1000 normalized scale.
    """
    try:
        from PIL import Image, ImageDraw
        with Image.open(image_path) as img:
            # SOTA Fix: Convert to RGB immediately to avoid Palette transparency warnings
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            for issue in issues:
                coords = issue.get("coordinates")
                if not coords or len(coords) != 4:
                    continue
                
                ymin, xmin, ymax, xmax = coords
                # Convert normalized to pixel coordinates
                left = xmin * width / 1000
                top = ymin * height / 1000
                right = xmax * width / 1000
                bottom = ymax * height / 1000
                
                # Draw thick red rectangle
                draw.rectangle([left, top, right, bottom], outline="red", width=5)
                # Add issue ID label
                draw.text((left + 5, top + 5), f"ID: {issue.get('id', '?')}", fill="red")
            
            img.save(output_path, format="JPEG")
            return True
    except Exception as e:
        print(f"    [Utils] Error drawing boxes: {e}")
        return False
