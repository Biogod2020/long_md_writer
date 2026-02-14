"""
Markdown Merger Utility (SOTA 2.0)
Concatenates multiple Markdown files into a single document with traceability markers.
"""

from pathlib import Path
from typing import List, Optional

def merge_markdown_sections(
    section_paths: List[str],
    output_path: str,
    workspace_path: Optional[str] = None
) -> bool:
    """
    Concatenates Markdown sections into a single file with SECTION markers.
    
    Args:
        section_paths: List of absolute or workspace-relative paths to .md files.
        output_path: Path where the merged file will be saved.
        workspace_path: Optional base path for relative section paths.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        merged_content = []
        ws = Path(workspace_path) if workspace_path else Path.cwd()
        
        for i, path_str in enumerate(section_paths):
            p = Path(path_str)
            if not p.is_absolute():
                p = ws / p
                
            if not p.exists():
                print(f"  [Merger] ⚠️ File not found: {p}")
                continue
                
            content = p.read_text(encoding="utf-8")
            section_id = p.stem
            
            # Inject SOTA Traceability Marker
            marker = f"<!-- SECTION: {section_id} -->"
            merged_content.append(f"{marker}\n{content}\n")
            
        final_path = Path(output_path)
        if not final_path.is_absolute() and workspace_path:
            final_path = ws / final_path
            
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_text("\n".join(merged_content), encoding="utf-8")
        
        print(f"  [Merger] ✅ Merged {len(merged_content)} sections into {final_path.name}")
        return True
        
    except Exception as e:
        print(f"  [Merger] ❌ Error: {e}")
        return False
