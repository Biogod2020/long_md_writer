import asyncio
import os
import base64
from pathlib import Path
from PIL import Image
from src.agents.asset_management.processors.audit import render_svg_with_playwright
from src.agents.asset_management.processors.mermaid import render_mermaid_to_png

async def test_sizes():
    print("--- Diagnostic: Testing Payload Sizes ---")
    
    test_dir = Path("test_payload_output")
    test_dir.mkdir(exist_ok=True)
    
    # 1. Sample SVG (Technical diagram)
    svg_code = """
    <svg width="800" height="600" viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#f0f0f0"/>
        <circle cx="400" cy="300" r="100" fill="red" stroke="black" stroke-width="5"/>
        <text x="400" y="320" font-family="Arial" font-size="24" text-anchor="middle">Test SVG Axis</text>
        <path d="M 100 100 L 700 500" stroke="blue" stroke-width="2" marker-end="url(#arrowhead)"/>
        <text x="150" y="150" font-family="Arial" font-size="16">Vector P</text>
    </svg>
    """
    
    # 2. Sample Mermaid (Workflow)
    mermaid_code = """
    graph TD
        A[Start Audit] --> B{Is Quality High?}
        B -- Yes --> C[Pass]
        B -- No --> D[Repair Loop]
        D --> E[Check Hash]
        E --> B
    """
    
    svg_out = test_dir / "test_svg.png"
    mermaid_out = test_dir / "test_mermaid.png"
    
    print("\n[SVG Rendering]")
    success_svg = await render_svg_with_playwright(svg_code, svg_out)
    if success_svg:
        size = svg_out.stat().st_size / 1024
        with open(svg_out, "rb") as f:
            b64_len = len(base64.b64encode(f.read()))
        with Image.open(svg_out) as img:
            dims = img.size
            fmt = img.format
        print(f"  - File: {svg_out.name}")
        print(f"  - Format: {fmt}, Dimensions: {dims}")
        print(f"  - Disk Size: {size:.2f} KB")
        print(f"  - Base64 Length: {b64_len} chars")
    
    print("\n[Mermaid Rendering]")
    success_mm = await render_mermaid_to_png(mermaid_code, mermaid_out)
    if success_mm:
        size = mermaid_out.stat().st_size / 1024
        with open(mermaid_out, "rb") as f:
            b64_len = len(base64.b64encode(f.read()))
        with Image.open(mermaid_out) as img:
            dims = img.size
            fmt = img.format
        print(f"  - File: {mermaid_out.name}")
        print(f"  - Format: {fmt}, Dimensions: {dims}")
        print(f"  - Disk Size: {size:.2f} KB")
        print(f"  - Base64 Length: {b64_len} chars")

if __name__ == "__main__":
    asyncio.run(test_sizes())
