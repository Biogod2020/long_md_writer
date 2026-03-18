import asyncio
import random
from src.core.gemini_client import GeminiClient, GeminiResponse
from src.orchestration.nodes import NodeFactory

async def debug_rotation():
    print("🧪 Starting SOTA 2.1 Provider Rotation Debugger (Global State aware)")
    
    provider_stats = {}
    
    # We will patch _get_client to avoid real HTTP, but let _get_next_provider run naturally
    async def mock_generate_async(self, prompt=None, parts=None, **kwargs):
        # The real _get_next_provider logic
        p = self._get_next_provider()
        provider_stats[p] = provider_stats.get(p, 0) + 1
        return GeminiResponse(success=True, text="Mock Success")

    # Physical patch
    GeminiClient.generate_async = mock_generate_async
    
    factory = NodeFactory()
    
    print("\n--- Phase 1: Simulate Heavy Load (Architect + 4 Writers) ---")
    tasks = []
    # These prefer first provider (CLI)
    tasks.append(factory.pro_client.generate_async(prompt="Architect Task"))
    for i in range(4):
        tasks.append(factory.heavy_client.generate_async(prompt=f"Writer Task {i}"))
        
    await asyncio.gather(*tasks)
    print(f"Stats after Heavy: {provider_stats}")
    
    print("\n--- Phase 2: Simulate Light/Fulfillment Load (20 Concurrent tasks) ---")
    # These should POLL
    provider_stats = {}
    tasks = []
    for i in range(10):
        tasks.append(factory.svg_pro_client.generate_async(prompt=f"SVG Task {i}"))
        tasks.append(factory.light_client.generate_async(prompt=f"Search Task {i}"))
        
    await asyncio.gather(*tasks)
    
    print("\n--- Final Analysis ---")
    total = sum(provider_stats.values())
    for p, count in provider_stats.items():
        percentage = (count / total) * 100
        print(f"Provider {p:20}: {count} hits ({percentage:.1f}%)")

if __name__ == "__main__":
    asyncio.run(debug_rotation())
