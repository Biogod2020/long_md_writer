import asyncio
import base64
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.agents.asset_management.processors.audit import audit_svg_visual_async, refine_caption_async

async def stress_test_vlm_audit():
    print("🧪 Testing VLM Audit and Caption Refinement Robustness...")
    client = GeminiClient()
    
    # 1. Test SVG Visual Audit (The part that uses Playwright)
    svg_code = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" /></svg>'
    intent = "A red circle representing a heart vector."
    
    print("  [1/2] Running SVG Visual Audit (Playwright test)...")
    try:
        # Wrap in a strict timeout to see if it hangs
        report = await asyncio.wait_for(
            audit_svg_visual_async(client, svg_code, intent),
            timeout=45.0
        )
        print(f"  ✅ SVG Audit result: {report.get('result') if report else 'None'}")
    except asyncio.TimeoutError:
        print("  ❌ SVG Audit TIMED OUT!")
    except Exception as e:
        print(f"  ❌ SVG Audit CRASHED: {e}")

    # 2. Test Caption Refinement (Multi-modal API)
    print("  [2/2] Running Caption Refinement (API test)...")
    # Use a tiny transparent pixel as mock image
    mock_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    try:
        refined = await asyncio.wait_for(
            refine_caption_async(client, mock_png_b64, "Initial description", "Context: This is a test."),
            timeout=30.0
        )
        print(f"  ✅ Refined caption: {refined[:50]}...")
    except asyncio.TimeoutError:
        print("  ❌ Caption Refinement TIMED OUT!")
    except Exception as e:
        print(f"  ❌ Caption Refinement CRASHED: {e}")

if __name__ == "__main__":
    asyncio.run(stress_test_vlm_audit())
