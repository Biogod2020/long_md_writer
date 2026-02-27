import re
import asyncio
import os
from pathlib import Path
from src.core.gemini_client import GeminiClient

async def refine_output(md_path: str):
    p = Path(md_path)
    if not p.exists():
        print(f"❌ File not found: {md_path}")
        return
    content = p.read_text(encoding="utf-8")
    
    print(f"🛠️  Phase 1: Fixing paths and rendering structure...")
    
    # 1. Fix Paths to flat resource/
    # Handle ../assets/images/ and ../agent_generated/
    content = re.sub(r'src="\.\./assets/images/([^"]+)"', r'src="resource/\1"', content)
    content = re.sub(r'src="\.\./agent_generated/([^"]+)"', r'src="resource/\1"', content)
    
    # 2. Fix Caption Rendering (Ensure exactly 2 newlines)
    content = re.sub(r'<figcaption>\s*', r'<figcaption>\n\n', content)
    content = re.sub(r'\s*</figcaption>', r'\n\n</figcaption>', content)
    
    # 3. Phase 2: AI Localization (Translate Captions to Chinese)
    print(f"🤖 Phase 2: Localizing captions to Chinese using Gemini...")
    client = GeminiClient()
    
    prompt = f"""You are a Senior Technical Editor. The following Markdown document has technical captions in English inside <figcaption> tags, but the main body is in Chinese. 

### YOUR TASK:
1. Translate ALL text inside <figcaption>...</figcaption> and the 'alt' attributes of <img> tags into professional, academic Chinese.
2. The Chinese must match the tone and terminology of the surrounding article context.
3. Keep the "Title: Description" format.
4. MAINTAIN all **bolding** and LaTeX formulas ($...$) exactly as they are.
5. Output the COMPLETE corrected Markdown document.

### Document:
{content}
"""
    
    response = await client.generate_async(
        prompt=prompt,
        system_instruction="You are a SOTA Technical Translator. Output the full document with Chinese captions.",
        temperature=0.0,
        stream=True
    )
    
    if response.success and response.text:
        # Save the final masterpiece
        final_path = p.with_name("final_full_sota.md")
        final_path.write_text(response.text, encoding="utf-8")
        print(f"✨ SUCCESS! Refined document saved to: {final_path.absolute()}")
    else:
        print(f"❌ AI refinement failed: {response.error}")
        # Save structural fixes anyway
        p.write_text(content, encoding="utf-8")
        print(f"⚠️  Only physical fixes (paths/spacing) were applied to the original file.")

if __name__ == "__main__":
    job_path = "workspace/sota2_20260223_220554/final_full.md"
    asyncio.run(refine_output(job_path))
