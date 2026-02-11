"""
ImageSourcingAgent: SOTA 2.0 Intent-Driven Sub-Agent.
Handles web-based image discovery, downloading, and VLM-based selection.
"""

import re
import json
import shutil
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from ...core.gemini_client import GeminiClient
from ...core.types import AgentState, AssetEntry, AssetSource, AssetVQAStatus
from .browser import BrowserManager
from .strategy import StrategyGenerator
from .search import GoogleImageSearcher
from .downloader import ImageDownloader
from .vision import VisionSelector
from .local_selector import LocalSelector
from ..asset_management.utils import generate_figure_html
from ..asset_management.models import VisualDirective


class ImageSourcingAgent:
    """
    Agent that sources real images from the web for technical documents.
    Redesigned as an async sub-agent for SOTA 2.0.
    """

    def __init__(self, client: Optional[GeminiClient] = None, debug: bool = False, headless: bool = True):
        self.client = client or GeminiClient()
        self.debug = debug
        self.headless = headless
        
        self.strategy_gen = StrategyGenerator(self.client, debug=debug)
        self.vision_selector = VisionSelector(self.client, debug=debug)
        self.local_selector = LocalSelector(self.client, debug=debug)

    async def fulfill_directive_async(
        self, 
        directive: VisualDirective, 
        state: AgentState,
        target_file: Optional[Path] = None
    ) -> Tuple[bool, Optional[AssetEntry], Optional[str]]:
        """
        SOTA 2.0 Core Interface: Fulfills a visual directive by sourcing an image.
        Returns: (Success, AssetEntry, HTML_Code)
        """
        img_id = directive.id
        description = directive.description.strip()
        ws_path = Path(state.workspace_path)
        assets_dir = ws_path / "assets" / "images"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        uar = state.get_uar()
        html_context = directive.get_full_context()

        if self.debug:
            print(f"    [SourcingAgent] 🚀 Fulfilling: {img_id}")

        # 1. Local Lookup (Priority)
        if uar:
            candidates = await uar.intent_match_candidates_async(description, client=self.client, limit=10)
            best_local, reasoning = await self.local_selector.select_best_async(candidates, description)
            
            if best_local:
                html = generate_figure_html(best_local, description, target_file=target_file, workspace_path=ws_path)
                return True, best_local, html

        # 2. Web Search (Fallback)
        print(f"    [{img_id}] Sourcing from Web: {description[:50]}...")
        
        with BrowserManager(headless=self.headless, debug=self.debug, block_resources=True) as bm:
            searcher = GoogleImageSearcher(bm, debug=self.debug)
            downloader = ImageDownloader(bm, debug=self.debug)
            
            max_sourcing_attempts = 2
            all_failed_queries = []
            
            for attempt in range(max_sourcing_attempts):
                strategy = self.strategy_gen.generate(description, html_context, failed_queries=all_failed_queries if all_failed_queries else None)
                queries = strategy.get("queries", [description])[:2]
                guidance = strategy.get("guidance", "Accurate representation.")
                
                image_candidates = []
                for q in queries:
                    image_candidates.extend(searcher.search([q])[:20])
                
                if not image_candidates:
                    all_failed_queries.extend(queries)
                    continue

                temp_dir = assets_dir / f"candidates_{img_id}_v{attempt+1}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                local_images = downloader.download_candidates(image_candidates, temp_dir)
                
                if not local_images:
                    all_failed_queries.extend(queries)
                    continue

                descriptions_map = {p.name: p.with_suffix('.txt').read_text(encoding='utf-8') for p in local_images if p.with_suffix('.txt').exists()}
                
                ranked_results = await self.vision_selector.select_best_async(local_images, description, guidance, descriptions_map)

                if ranked_results:
                    valid_results = [r for r in ranked_results if r.get("status") != "REJECTED" and r.get("path")]
                    if valid_results:
                        best_res = max(valid_results, key=lambda x: x.get("score", 0))
                        best_path = best_res["path"]
                        
                        final_name = f"{img_id}{best_path.suffix}"
                        final_path = assets_dir / final_name
                        shutil.copy2(best_path, final_path)
                        
                        asset = AssetEntry(
                            id=img_id, source=AssetSource.WEB,
                            local_path=str(final_path.relative_to(ws_path)),
                            semantic_label=best_res.get("description", description),
                            content_hash=hashlib.md5(final_path.read_bytes()).hexdigest(),
                            alt_text=best_res.get("description", description),
                            vqa_status=AssetVQAStatus.PASS if best_res.get("status") == "CERTAIN" else AssetVQAStatus.PENDING
                        )
                        
                        html = generate_figure_html(asset, asset.semantic_label, target_file=target_file, workspace_path=ws_path)
                        
                        if not self.debug:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        return True, asset, html
                
                all_failed_queries.extend(queries)
                if not self.debug: shutil.rmtree(temp_dir, ignore_errors=True)

        return False, None, None

    def run(self, state: AgentState, preserve_candidates: bool = False) -> AgentState:
        """
        DEPRECATED: Legacy physical file replacement mode. 
        Archived logic moved to legacy_runner.py.
        """
        print("  [ImageSourcingAgent] ⚠️ Using DEPRECATED run() mode. Sourcing images for HTML sections...")
        
        async def _run_async_wrapper():
            for html_path_str in state.completed_html_sections:
                html_file = Path(html_path_str)
                content = html_file.read_text(encoding="utf-8")
                
                # Simple regex to find placeholders
                placeholder_regex = re.compile(r'(<div[^>]*class="img-placeholder"[^>]*data-img-id="([^"]+)"[^>]*>.*?<p[^>]*class="img-description">(.*?)</p>.*?</div>)', re.DOTALL | re.IGNORECASE)
                matches = placeholder_regex.findall(content)
                
                if matches:
                    tasks = []
                    for full_tag, img_id, description in matches:
                        d = VisualDirective(id=img_id, description=description, raw_block=full_tag, start_pos=0, end_pos=0)
                        tasks.append(self.fulfill_directive_async(d, state, target_file=html_file))
                    
                    results = await asyncio.gather(*tasks)
                    for i, (success, asset, html_code) in enumerate(results):
                        if success and html_code:
                            content = content.replace(matches[i][0], html_code)
                    
                    html_file.write_text(content, encoding="utf-8")
            return state

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(lambda: asyncio.run(_run_async_wrapper())).result()
            return loop.run_until_complete(_run_async_wrapper())
        except RuntimeError:
            return asyncio.run(_run_async_wrapper())


def create_image_sourcing_agent(client: Optional[GeminiClient] = None) -> ImageSourcingAgent:
    """Create an ImageSourcingAgent instance."""
    return ImageSourcingAgent(client=client)
