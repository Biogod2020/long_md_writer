import pytest
from pathlib import Path
from src.core.merger import merge_markdown_sections

def test_merge_markdown_sections(tmp_path):
    # 1. Prepare dummy sections
    s1 = tmp_path / "sec-1.md"
    s1.write_text("# Section 1\nContent 1", encoding="utf-8")
    
    s2 = tmp_path / "sec-2.md"
    s2.write_text("# Section 2\nContent 2", encoding="utf-8")
    
    output_path = tmp_path / "final_full.md"
    
    # 2. Execute merger
    success = merge_markdown_sections(
        section_paths=[str(s1), str(s2)],
        output_path=str(output_path)
    )
    
    # 3. Verify
    assert success is True
    assert output_path.exists()
    
    content = output_path.read_text(encoding="utf-8")
    assert "<!-- SECTION: sec-1 -->" in content
    assert "# Section 1" in content
    assert "<!-- SECTION: sec-2 -->" in content
    assert "# Section 2" in content

def test_merger_missing_file(tmp_path):
    s1 = tmp_path / "exists.md"
    s1.write_text("exists", encoding="utf-8")
    
    output_path = tmp_path / "merged.md"
    
    # Attempt to merge one existing and one non-existent file
    success = merge_markdown_sections(
        section_paths=[str(s1), "non_existent.md"],
        output_path=str(output_path)
    )
    
    assert success is True # Should still succeed but skip missing
    content = output_path.read_text(encoding="utf-8")
    assert "<!-- SECTION: exists -->" in content
    assert "non_existent" not in content
