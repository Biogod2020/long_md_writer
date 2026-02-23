
import sys
import os
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.gemini_client import GeminiClient

async def run_uncut_qa_test(stream: bool):
    print(f"\n{'='*20} Testing with STREAM={stream} {'='*20}")
    workspace_id = "d2d3d333"
    workspace_path = Path(f"workspaces/workspace/{workspace_id}")
    
    # 1. Load Manifest
    manifest_path = workspace_path / "manifest.json"
    manifest_data = {}
    if manifest_path.exists():
        manifest_data = json.loads(manifest_path.read_text())
    
    # 2. Load Raw Materials from log (most realistic)
    log_path = workspace_path / "debug_logs/step_001.json"
    raw_materials = "Not found"
    project_brief = "Not found"
    if log_path.exists():
        try:
            log_data = json.loads(log_path.read_text())
            raw_materials = log_data.get("raw_materials", "")
            project_brief = log_data.get("project_brief", "Refer to raw materials")
        except Exception as e:
            print(f"Error loading raw materials from log: {e}")
            raw_materials = "Sample raw materials about ECG."
    
    # 3. Load Merged Markdown
    md_dir = workspace_path / "md"
    md_contents = []
    if md_dir.exists():
        for md_file in sorted(md_dir.glob("*.md")):
            content = md_file.read_text()
            md_contents.append(f"## File: {md_file.name}\n{content}")
    
    merged_md = "\n\n".join(md_contents)
    
    # 4. Construct the prompt (UNCUT)
    prompt = f"""# TASK
You are a medical textbook editor. Review the following generated Markdown content against the Manifest, Project Brief, and Raw Materials.
Identify any factual errors, missing information, or stylistic inconsistencies.

# Manifest
{json.dumps(manifest_data, indent=2, ensure_ascii=False)}

# Project Brief
{project_brief}

# Raw Materials
{raw_materials}

# Generated Markdown Content
{merged_md}

---
Provide a concise list of major issues found. Be specific.
"""

    print("--- Prompt Statistics ---")
    print(f"Total Prompt size: {len(prompt)} chars")
    
    # 5. Send to API
    api_url = os.getenv("API_URL", "http://localhost:3000")
    client = GeminiClient(api_base_url=api_url, timeout=300)
    
    print(f"Sending request to {api_url} (timeout=300s, stream={stream})...")
    
    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="You are a professional medical content critic.",
            temperature=0.0,
            stream=stream
        )
        
        if response.success:
            print(f"\n--- SUCCESS (STREAM={stream}) ---")
            print(response.text[:2000] + ("..." if len(response.text) > 2000 else ""))
        else:
            print(f"\n--- FAILED (STREAM={stream}) ---")
            print(f"Error: {response.error}")
    except Exception as e:
        print(f"\n--- EXCEPTION (STREAM={stream}) ---")
        print(str(e))

async def main():
    # Test stream=False
    await run_uncut_qa_test(stream=False)
    # Test stream=True
    await run_uncut_qa_test(stream=True)

if __name__ == "__main__":
    asyncio.run(main())
