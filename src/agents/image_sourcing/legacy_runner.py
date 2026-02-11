"""
ARCHIVED ImageSourcing Logic (Legacy HTML Placeholder Mode)
This file contains the original regular expression based replacement logic.
Moved from agent.py on 2026-02-11.
"""

import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

def archived_process_section(agent, html_content: str, assets_dir: Path, preserve_candidates: bool = False, uar = None, target_file = None, workspace_path = None) -> str:
    """Finds placeholders and replaces them in parallel using legacy regex matching."""
    placeholder_regex = re.compile(
        r'(<div[^>]*class="img-placeholder"[^>]*data-img-id="([^"]+)"[^>]*>.*?'
        r'<p[^>]*class="img-description">(.*?)</p>.*?'
        r'</div>)',
        re.DOTALL | re.IGNORECASE
    )

    matches = placeholder_regex.findall(html_content)
    if not matches:
        return html_content

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_placeholder = {
            executor.submit(
                agent._source_single_image, 
                img_id, description, assets_dir, html_content, preserve_candidates, uar,
                target_file=target_file,
                workspace_path=workspace_path
            ): (full_tag, img_id) 
            for full_tag, img_id, description in matches
        }
        
        for future in concurrent.futures.as_completed(future_to_placeholder):
            full_tag, img_id = future_to_placeholder[future]
            try:
                replacement_html = future.result()
                if replacement_html:
                    results.append((full_tag, replacement_html))
            except Exception: pass

    for original_tag, new_tag in results:
        html_content = html_content.replace(original_tag, new_tag)

    return html_content
