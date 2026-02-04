import asyncio
from src.core.gemini_client import GeminiClient
from src.agents.asset_management.processors.audit import audit_svg_visual_async
from src.core.types import AgentState

import time

async def test_svg_stress_patching():
    print("🔥 Starting SVG STRESS PATCHING Test...")
    client = GeminiClient()
    state = AgentState(user_context="stress_test", workspace_path="workspace_test", job_id="stress_job")
    
    # 1. 生成一个巨大的 SVG (模拟工业级复杂度)
    print("  - Generating 500-element SVG...")
    svg_lines = [
        '<svg width="1200" height="1000" viewBox="0 0 1200 1000" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<g id="background_clutter" opacity="0.2">'
    ]
    for i in range(400):
        svg_lines.append(f'  <rect x="{i*3}" y="{i*2}" width="20" height="20" fill="gray" />')
    svg_lines.append('</g>')
    
    # 2. 注入核心内容 (故意制造错误：文字重叠，颜色错误)
    svg_lines.append('<g id="main_content">')
    svg_lines.append('  <circle cx="600" cy="500" r="150" fill="blue" id="core_node" />')
    # 错误 1: 文字完全重叠在圆心上
    svg_lines.append('  <text x="600" y="500" font-size="40" fill="white" id="label_1">OVERLAP_ERROR</text>')
    # 错误 2: 引导线断裂
    svg_lines.append('  <line x1="100" y1="100" x2="200" y2="200" stroke="red" stroke-width="5" id="broken_line" />')
    svg_lines.append('</g>')
    svg_lines.append('</svg>')
    
    svg_code = "\n".join(svg_lines)
    intent = "这张图是一个核心节点图。要求：1. label_1 必须在圆形的上方，不能重叠。2. 红色引导线 broken_line 必须加粗并连接到 (300, 300)。"

    print(f"📊 Payload Info: {len(svg_code)} chars, {len(svg_lines)} lines")
    
    from src.agents.asset_management.processors.audit import render_svg_to_png_base64
    png_b64 = render_svg_to_png_base64(svg_code)
    
    # 3. 模拟 Audit -> Repair 流程
    from src.agents.asset_management.processors.svg import repair_svg_async
    
    print("\n[Step 1] Auditing huge SVG...")
    report = await audit_svg_visual_async(client, svg_code, intent, state=state)
    
    if report and report.get("result") != "pass":
        print(f"✅ Audit successfully identified issues: {report.get('issues')}")
        
        print("\n[Step 2] Repairing via PATCHING...")
        start_time = time.time()
        
        # 获取最新的截图用于修复
        repaired_code = await repair_svg_async(
            client, 
            intent, 
            svg_code, 
            report.get("issues"), 
            report.get("suggestions"), 
            state=state,
            rendered_image_b64=png_b64
        )
        
        duration = time.time() - start_time
        
        if repaired_code:
            print(f"🎊 Success in {duration:.2f}s!")
            # 验证 Patch 是否生效 (简单字符串检查)
            if 'y="300"' in repaired_code or 'y="320"' in repaired_code:
                print("  - Patch logic: Text position moved.")
            if 'x2="300"' in repaired_code:
                print("  - Patch logic: Line extended.")
            
            # 打印最后的 Thoughts
            if state.thoughts:
                print(f"\n🧠 LATEST THOUGHTS:\n{state.thoughts.split('---')[-1]}")
        else:
            print("❌ Repair failed to generate patches.")
    else:
        print("❓ Audit unexpectedly passed or failed to run.")

    await client.close_async()

if __name__ == "__main__":
    asyncio.run(test_svg_stress_patching())

if __name__ == "__main__":

    asyncio.run(test_svg_stress_patching())
