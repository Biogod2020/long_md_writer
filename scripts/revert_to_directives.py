
import re
import os
import json
from pathlib import Path

def revert_file(file_path):
    content = file_path.read_text(encoding="utf-8")
    
    # 匹配 <figure> 包装的 img 标签，提取 ID 和 caption
    # 兼容之前产生的各种路径和格式
    figure_pattern = re.compile(r'<figure>\s*<img[^>]+data-asset-id="([^"]+)"[^>]*>.*?<figcaption>(.*?)</figcaption>\s*</figure>', re.DOTALL | re.IGNORECASE)
    
    def replace_with_directive(match):
        asset_id = match.group(1)
        caption = match.group(2).strip()
        
        # 根据 ID 模式启发式推断 action
        action = "GENERATE_SVG"
        if any(k in asset_id.lower() for k in ["electrode", "clinical", "ecg-strip", "normal"]):
            action = "SEARCH_WEB"
            
        directive = {
            "id": asset_id,
            "action": action,
            "description": caption,
            "reason": "Restored for clean-room re-fulfillment"
        }
        
        # 保持 JSON 格式整洁
        return f'\n:::visual {json.dumps(directive, ensure_ascii=False)}\n:::\n'

    new_content = figure_pattern.sub(replace_with_directive, content)
    
    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        return True
    return False

def main():
    md_dir = Path("workspace/v16_comprehensive_run/md")
    if not md_dir.exists():
        print("❌ MD directory not found.")
        return

    count = 0
    for md_file in md_dir.glob("*.md"):
        if revert_file(md_file):
            print(f"✅ Reverted {md_file.name} to directives.")
            count += 1
        else:
            print(f"ℹ️ No image patterns found in {md_file.name}")
    
    print(f"\n✨ Total files reverted: {count}")

if __name__ == "__main__":
    main()
