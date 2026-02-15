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
                file_path = out_path / f"{section_id}.md"
                # Keep H1 title if it was stripped or just write content
                file_path.write_text(section_content, encoding="utf-8")
                
        return True
    except Exception as e:
        print(f"  [Merger] ❌ Split-back failed: {e}")
        return False
