import asyncio
import os
import shutil
from pathlib import Path
from src.core.merger import merge_markdown_sections
from src.core.types import UniversalAssetRegistry

async def test_manual_merge_v12():
    workspace = Path("workspace/v12_final_verification_stable").absolute()
    md_files = [
        str(workspace / "md" / "s1-sec-01.md"),
        str(workspace / "md" / "s2-sec-02.md"),
        str(workspace / "md" / "s3-sec-03.md"),
        str(workspace / "md" / "s4-sec-04.md")
    ]
    
    output_path = workspace / "v12_manual_final_full.md"
    uar_path = workspace / "assets.json"
    
    # Clean up previous resource folder to ensure fresh test
    resource_dir = workspace / "resource"
    if resource_dir.exists():
        shutil.rmtree(resource_dir)
        
    print(f"🚀 Manually merging artifacts from {workspace}...")
    
    uar = UniversalAssetRegistry.load_from_file(str(uar_path))
    
    success = merge_markdown_sections(
        md_files,
        str(output_path),
        workspace_path=str(workspace),
        asset_registry=uar
    )
    
    if success:
        print("✅ Manual merge call successful.")
        if output_path.exists():
            content = output_path.read_text()
            resource_count = content.count('src="resource/')
            print(f"   Resource redirection count: {resource_count}")
            
            # Check physical files
            if resource_dir.exists():
                files = list(resource_dir.glob("*"))
                print(f"   Physical assets in resource folder: {len(files)}")
                # for f in files:
                #     print(f"     - {f.name}")
            else:
                print("   ❌ resource/ directory was NOT created!")
    else:
        print("❌ Manual merge call FAILED.")

if __name__ == "__main__":
    asyncio.run(test_manual_merge_v12())
