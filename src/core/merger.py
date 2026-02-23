"""
Markdown Merger Utility (SOTA 2.0)
Concatenates multiple Markdown files into a single document with traceability markers.
"""

import re
import shutil
from pathlib import Path
from typing import List, Optional, Any

def merge_markdown_sections(
    section_paths: List[str],
    output_path: str,
    workspace_path: Optional[str] = None,
    asset_registry: Optional[Any] = None
) -> bool:
    """
    Concatenates Markdown sections into a single file and EXPORTS assets to a local folder.
    
    SOTA 2.0 Export Protocol:
    1. Moves/Copies all referenced assets to a flat 'resource/' folder.
    2. Rewrites all img src to 'resource/filename'.
    """
    try:
        merged_content = []
        ws = Path(workspace_path) if workspace_path else Path.cwd()
        
        # 确定导出目录和资源子目录
        final_file_path = Path(output_path)
        if not final_file_path.is_absolute() and workspace_path:
            final_file_path = ws / final_file_path
            
        export_dir = final_file_path.parent
        resource_dir = export_dir / "resource"
        resource_dir.mkdir(parents=True, exist_ok=True)

        for i, path_str in enumerate(section_paths):
            p = Path(path_str)
            if not p.is_absolute():
                p = ws / p
                
            if not p.exists():
                print(f"  [Merger] ⚠️ File not found: {p}")
                continue
                
            content = p.read_text(encoding="utf-8")
            
            # --- SOTA: 资源重定向与物理导出 ---
            if asset_registry:
                def redirect_asset(match):
                    full_tag = match.group(0)
                    asset_id_match = re.search(r'data-asset-id="([^"]+)"', full_tag)
                    if asset_id_match:
                        asset_id = asset_id_match.group(1)
                        asset = asset_registry.get_asset(asset_id)
                        if asset:
                            # 获取原物理路径
                            abs_src = asset.get_absolute_path(workspace_path=workspace_path)
                            if abs_src and abs_src.exists():
                                # 物理拷贝到 resource 文件夹
                                target_name = abs_src.name
                                dst_path = resource_dir / target_name
                                if not dst_path.exists():
                                    shutil.copy2(abs_src, dst_path)
                                
                                # 改写路径为扁平化的资源路径
                                # 替换 src="..." 里的内容
                                new_tag = re.sub(r'src="[^"]+"', f'src="resource/{target_name}"', full_tag)
                                return new_tag
                    return full_tag

                # 匹配所有 <img> 标签
                content = re.sub(r'<img[^>]+>', redirect_asset, content)

            section_id = p.stem
            marker = f"<!-- SECTION: {section_id} -->"
            merged_content.append(f"{marker}\n{content}\n")
            
        final_file_path.parent.mkdir(parents=True, exist_ok=True)
        final_file_path.write_text("\n".join(merged_content), encoding="utf-8")
        
        print(f"  [Merger] 📦 SOTA Export Complete: {final_file_path.name} created with localized /resource folder.")
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  [Merger] ❌ Export failed: {e}")
        return False

def split_merged_document(
    merged_file_path: str,
    output_dir: str
) -> bool:
    """
    Splits a merged Markdown document back into individual section files
    based on the <!-- SECTION: xxx --> markers.
    
    Returns:
        True if successful.
    """
    try:
        path = Path(merged_file_path)
        if not path.exists():
            return False
            
        content = path.read_text(encoding="utf-8")
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        import re
        # Pattern to split by section marker
        sections = re.split(r'<!-- SECTION: (.*?) -->', content)
        
        # re.split will return [intro_text, id1, content1, id2, content2, ...]
        # We skip the first element if it's empty or whitespace
        for i in range(1, len(sections), 2):
            section_id = sections[i].strip()
            section_content = sections[i+1].strip()
            
            if section_id:
                # SOTA: 如果是在子目录下（如 audited_md），将资源路径重锚为 ../resource/
                # 这样分章节文稿也能正常预览根目录下的资源
                section_content = re.sub(r'src="resource/', 'src="../resource/', section_content)
                
                file_path = out_path / f"{section_id}.md"
                file_path.write_text(section_content, encoding="utf-8")
                
        return True
    except Exception as e:
        print(f"  [Merger] ❌ Split-back failed: {e}")
        return False
