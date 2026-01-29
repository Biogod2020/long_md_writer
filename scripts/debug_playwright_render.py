import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.asset_management.processors.audit import render_svg_with_playwright
from src.agents.asset_management.processors.mermaid import render_mermaid_to_png

async def debug_render():
    print("🚀 Starting Playwright Render Debug...")
    
    output_dir = Path("test_render_output")
    output_dir.mkdir(exist_ok=True)
    
    # 1. Test SVG with Chinese
    svg_code = """
    <svg width="400" height="200" viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#f0f0f0" />
        <text x="50%" y="50%" font-family="sans-serif" font-size="24" text-anchor="middle" fill="#333">
            测试中文字体: 向量投影
        </text>
        <circle cx="50" cy="50" r="40" stroke="green" stroke-width="4" fill="yellow" />
    </svg>
    """
    svg_out = output_dir / "debug_svg.png"
    print(f"  - Rendering SVG to {svg_out}...")
    success = await render_svg_with_playwright(svg_code, svg_out)
    if success:
        print(f"  ✅ SVG Render Success (Check manually: {svg_out})")
    else:
        print("  ❌ SVG Render Failed")

    # 2. Test Mermaid with Chinese
    mermaid_code = """
    graph TD
        A[开始] --> B{是否正常?}
        B -- 是 --> C[中文节点]
        B -- 否 --> D[调试模式]
    """
    mermaid_out = output_dir / "debug_mermaid.png"
    print(f"  - Rendering Mermaid to {mermaid_out}...")
    success = await render_mermaid_to_png(mermaid_code, mermaid_out)
    if success:
        print(f"  ✅ Mermaid Render Success (Check manually: {mermaid_out})")
    else:
        print("  ❌ Mermaid Render Failed")

if __name__ == "__main__":
    asyncio.run(debug_render())
