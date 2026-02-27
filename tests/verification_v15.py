"""
Final Verification E2E - v15 (Standardization & Language Sync)
Testing SOTA 2.0 Full Pipeline with fix for:
1. Path redirection robustness (resource/ folder)
2. Figcaption Markdown rendering (naked newlines)
3. Multi-modal language alignment (Chinese captions)
"""

import asyncio
import os
import shutil
import json
import re
from pathlib import Path
from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.types import AssetSource

async def run_verification_v15():
    job_id = "v15_standardization_run"
    workspace_base = "workspace"
    workspace_path = Path(workspace_base) / job_id

    # SOTA: Always start fresh for v15 to verify the fix from zero-state
    if workspace_path.exists():
        print(f"🧹 Cleaning previous workspace: {workspace_path}")
        shutil.rmtree(workspace_path)
    
    print(f"🚀 [VERIFICATION v15] Starting FRESH E2E Run: {job_id}")
    
    # 1. Load Real Inputs (Chinese focus)
    try:
        user_intent = """写一篇关于心电图 (ECG) 基础原理的专业教程。要求：
1. 必须包含一个复杂的 Mermaid 流程图展示诊断逻辑。
2. 必须包含至少一个 SVG 示意图展示偶极子模型。
3. 所有图片描述和图注必须使用中文。
4. 确保 3 个以上的章节。"""
        reference_materials = "参考资料：心电图是利用心电图机从体表记录心脏每一心动周期所产生的电活动变化图形的技术。"
        print("✅ Chinese inputs loaded.")
    except Exception as e:
        print(f"❌ Failed to load inputs: {e}")
        return
    
    print(f"📍 Target Workspace: {workspace_path.absolute()}")

    # 2. Execute Workflow in Auto-Mode
    print("⚙️  Initiating SOTA 2.0 Pipeline...")
    state = await run_sota2_workflow(
        user_intent=user_intent,
        reference_materials=reference_materials,
        workspace_base=workspace_base,
        job_id=job_id,
        auto_mode=True, 
        debug_mode=True
    )
    
    # 3. Quality Audit Report
    print("\n" + "="*50)
    print("📊 VERIFICATION v15 QUALITY AUDIT REPORT")
    print("="*50)
    
    # Check 1: Path Redirection in final_full.md
    merged_path = workspace_path / "final_full.md"
    path_redirection_ok = False
    if merged_path.exists():
        content = merged_path.read_text(encoding="utf-8")
        # Regex to check if all img src point to resource/
        total_imgs = len(re.findall(r'<img[^>]+>', content))
        # Look for src="resource/..." or src='resource/...' with potential spaces
        correct_imgs = len(re.findall(r'src\s*=\s*["\']resource/', content, re.IGNORECASE))
        print(f"Check 1 (Path Redirection): {correct_imgs}/{total_imgs} images redirected to 'resource/'")
        if total_imgs > 0 and correct_imgs == total_imgs:
            path_redirection_ok = True
        elif total_imgs == 0:
            print("Check 1: Skip (No images found in merged output)")
            path_redirection_ok = True
    
    # Check 2: Figcaption Naked Newlines
    rendering_purity_ok = False
    if merged_path.exists():
        content = merged_path.read_text(encoding="utf-8")
        # Check for <figcaption>\n\n
        naked_newlines = len(re.findall(r'<figcaption>\n\n', content))
        print(f"Check 2 (Figcaption Purity): Found {naked_newlines} instances of naked newlines.")
        if naked_newlines > 0:
            rendering_purity_ok = True
        else:
            # Check if there are any figcaptions at all
            if "<figcaption>" not in content:
                print("Check 2: Skip (No figcaptions found)")
                rendering_purity_ok = True

    # Check 3: Language Alignment (Chinese check)
    language_sync_ok = False
    if merged_path.exists():
        content = merged_path.read_text(encoding="utf-8")
        # Search for common English drift words in figcaptions
        english_drift = re.search(r'<figcaption>[^<]*?(Diagram|Illustration|Figure|This image|Showing)[^<]*?</figcaption>', content, re.IGNORECASE)
        if not english_drift:
            print("Check 3 (Language Sync): No English drift detected in figcaptions.")
            language_sync_ok = True
        else:
            print(f"Check 3 (Language Sync): WARNING! Potential English drift found: '{english_drift.group(0)}'")

    print(f"Status: {'✅ SUCCESS' if not state.errors else '❌ FAILED'}")
    
    # Final Verdict
    if not state.errors and path_redirection_ok and rendering_purity_ok and language_sync_ok:
        print("\n🏆 [VERIFICATION v15] ALL QUALITY CRITERIA PASSED.")
    else:
        print("\n💀 [VERIFICATION v15] QUALITY REGRESSION DETECTED.")
        if not path_redirection_ok: print("   - Reason: Path redirection regression.")
        if not rendering_purity_ok: print("   - Reason: Figcaption rendering regression.")
        if not language_sync_ok: print("   - Reason: Language sync regression.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(run_verification_v15())
