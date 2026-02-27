import asyncio
import base64
import time
from pathlib import Path
from PIL import Image
from src.core.gemini_client import GeminiClient
from src.agents.image_sourcing.vision import VisionSelector

async def stress_test_20_images():
    print("🧪 [STRESS TEST] Verifying VLM capacity for 20 concurrent images...")
    
    # 1. Prepare 20 small VQA thumbnails
    test_dir = Path("workspace/vlm_stress_20")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    image_paths = []
    print("  - Generating 20 mock VQA images...")
    for i in range(20):
        img_path = test_dir / f"img_{i}.jpg"
        vqa_path = test_dir / f"img_{i}_vqa.jpg"
        # Create a small random colored image
        img = Image.new('RGB', (1024, 768), color=(i*10 % 255, 100, 200))
        img.save(img_path, "JPEG")
        img.save(vqa_path, "JPEG")
        image_paths.append(img_path)
        
    client = GeminiClient(model_provider="gemini-cli-oauth")
    selector = VisionSelector(client, debug=True)
    
    description = "A collection of colored test patterns."
    guidance = "Select the one that looks most blue."
    
    print(f"  - Dispatching 20 images to VLM (Batch Size: {selector.default_batch_size})...")
    start_time = time.time()
    
    try:
        # Wrap in a safe timeout but check if it can finish
        results = await asyncio.wait_for(
            selector.select_best_async(image_paths, description, guidance),
            timeout=120.0
        )
        
        elapsed = time.time() - start_time
        print(f"\n✅ [SUCCESS] VLM processed 20 images in {elapsed:.2f} seconds.")
        print(f"📊 Results received: {len(results)}")
        
    except asyncio.TimeoutError:
        print("\n❌ [TIMEOUT] VLM failed to process 20 images within 120 seconds.")
    except Exception as e:
        print(f"\n💥 [CRASHED] {e}")
    finally:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(stress_test_20_images())
