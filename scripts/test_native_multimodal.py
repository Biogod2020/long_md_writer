import asyncio
import os
import base64
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.agents.asset_management.processors.audit import render_svg_with_playwright

async def stress_test():
    print("🚀 Starting Native Multimodal Stress Test...")
    client = GeminiClient()
    
    # 1. Prepare a high-payload SVG
    # A very complex SVG path or just many lines of code
    svg_code = """
    <svg width="1200" height="800" viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#ffffff"/>
        <g stroke="black" stroke-width="1" fill="none">
    """
    for i in range(500):
        svg_code += f'<circle cx="{i*2}" cy="{i*1.5}" r="50" stroke="rgba({i%255}, {i//2%255}, 100, 0.5)"/>\n'
    svg_code += "</g>\n</svg>"
    
    print(f"  - Generated SVG code size: {len(svg_code)} chars")
    
    # 2. Render to a high-quality PNG/JPG
    temp_img = Path("stress_test_image.jpg")
    print("  - Rendering SVG to JPEG (High Quality)...")
    success = await render_svg_with_playwright(svg_code, temp_img)
    
    if not success:
        print("  ❌ Rendering failed.")
        return

    with open(temp_img, "rb") as f:
        img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    
    print(f"  - Image payload size: {len(img_b64)} chars")
    
    # 3. Perform Audit via Native Protocol
    prompt = "Audit this complex SVG diagram. Identify any overlapping elements or visual artifacts. Output JSON result: pass|fail."
    
    parts = [
        {"text": prompt},
        {"text": f"## Source Code\n```svg\n{svg_code}\n```"},
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_b64
            }
        }
    ]
    
    print("  - Sending high-payload request to Native Proxy...")
    response = await client.generate_async(
        parts=parts,
        system_instruction="You are a senior visual auditor.",
        temperature=0.0
    )
    
    if response.success:
        print("  ✅ Success! Proxy handled the payload perfectly.")
        print(f"  - AI Response: {response.text[:200]}...")
        if response.thoughts:
            print(f"  - Thoughts captured: {len(response.thoughts)} chars")
    else:
        print(f"  ❌ Failed: {response.error}")
    
    # Cleanup
    if temp_img.exists():
        temp_img.unlink()
    await client.close_async()

if __name__ == "__main__":
    asyncio.run(stress_test())
