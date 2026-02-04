import asyncio
import time
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.agents.asset_management.processors.svg import generate_svg_async

async def stress_test_svg():
    client = GeminiClient()
    
    # 定义 5 个不同复杂度的任务
    tasks = [
        {"id": "simple", "desc": "A simple red circle with a blue outline and label 'Cell'"},
        {"id": "medium", "desc": "A flowchart of the cardiac cycle: Atrial Systole -> Ventricular Systole -> Diastole, with arrows and icons"},
        {"id": "complex_bio", "desc": "A detailed cross-section of a human heart showing four chambers, valves (mitral, tricuspid), and aorta, isometric view"},
        {"id": "complex_mech", "desc": "A futuristic nano-robot structure with gears, sensors, and a needle tip, high detail, isometric"},
        {"id": "data_viz", "desc": "A complex dashboard UI layout with 3 line charts, 2 pie charts, and many data labels, tech style"}
    ]
    
    print(f"🚀 [StressTest] 启动并行 SVG 生成压力测试 (并发数: {len(tasks)})")
    start_time = time.time()
    
    async def run_task(task):
        t_start = time.time()
        print(f"  [Task:{task['id']}] 正在生成...")
        try:
            # 直接调用底层生成模块
            svg_code = await generate_svg_async(
                client, 
                task['desc'], 
                style_hints="Professional, textbook style, no overlapping labels."
            )
            
            t_end = time.time()
            if svg_code:
                size_kb = len(svg_code) / 1024
                print(f"  ✅ [Task:{task['id']}] 成功! 大小: {size_kb:.1f} KB, 耗时: {t_end - t_start:.1f}s")
                # 保存结果供视觉检查
                out_path = Path("workspace/stress_test_svg") / f"{task['id']}.svg"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(svg_code, encoding="utf-8")
                return True
            else:
                print(f"  ❌ [Task:{task['id']}] 失败: 未返回内容")
                return False
        except Exception as e:
            print(f"  🔥 [Task:{task['id']}] 崩溃: {str(e)}")
            return False

    # 并行执行
    results = await asyncio.gather(*(run_task(t) for t in tasks))
    
    end_time = time.time()
    success_count = sum(1 for r in results if r)
    
    print(f"\n📊 [StressTest] 测试结果: {success_count}/{len(tasks)} 成功")
    print(f"⏱️ 总耗时: {end_time - start_time:.1f}s")

if __name__ == "__main__":
    asyncio.run(stress_test_svg())
