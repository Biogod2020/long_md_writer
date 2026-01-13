from pathlib import Path

def gather_full_context(completed_sections: list[str]) -> str:
    """
    Merges all completed Markdown sections into a single string for full-context review.
    
    Args:
        completed_sections: List of file paths to completed Markdown sections.
        
    Returns:
        A merged string of all sections with markers.
    """
    context_parts = []
    for section_path in completed_sections:
        path = Path(section_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            context_parts.append(f"<!-- START SECTION: {path.name} -->\n{content}\n<!-- END SECTION: {path.name} -->")
    return "\n\n".join(context_parts)
