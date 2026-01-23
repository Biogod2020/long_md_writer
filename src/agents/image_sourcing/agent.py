"""
ImageSourcingAgent: Orchestration of image sourcing workflow.
"""

import re
import json
import shutil
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from ...core.gemini_client import GeminiClient
from ...core.types import AgentState
from .browser import BrowserManager
from .strategy import StrategyGenerator
from .search import GoogleImageSearcher
from .downloader import ImageDownloader
from .vision import VisionSelector
from .local_selector import LocalSelector


class ImageSourcingAgent:
    """Agent that sources real images from the web for technical documents."""

    def __init__(self, client: Optional[GeminiClient] = None, debug: bool = False, headless: bool = True):
        self.client = client or GeminiClient()
        self.debug = debug
        self.headless = headless
        
        self.strategy_gen = StrategyGenerator(self.client, debug=debug)
        self.vision_selector = VisionSelector(self.client, debug=debug)
        self.local_selector = LocalSelector(self.client, debug=debug)

    def run(self, state: AgentState, preserve_candidates: bool = False) -> AgentState:
        """Process all HTML sections and replace image placeholders with real sourced images."""
        if self.debug:
            preserve_candidates = True
            print(f"  [ImageSourcing] DEBUG MODE ENABLED. Parallel processing with 8 workers.")

        if not state.completed_html_sections:
            return state

        # Base directory for images
        assets_dir = Path(state.workspace_path) / "assets" / "images"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Get UAR for local matching
        uar = state.get_uar()

        for html_path in state.completed_html_sections:
            try:
                html_file = Path(html_path)
                content = html_file.read_text(encoding="utf-8")
                updated_content = self._process_section(content, assets_dir, preserve_candidates, uar)
                html_file.write_text(updated_content, encoding="utf-8")
            except Exception as e:
                state.errors.append(f"ImageSourcingAgent: Error processing {html_path}: {e}")

        return state

    def _process_section(self, html_content: str, assets_dir: Path, preserve_candidates: bool = False, uar = None) -> str:
        """Finds placeholders and replaces them in parallel."""
        placeholder_regex = re.compile(
            r'(<div[^>]*class="img-placeholder"[^>]*data-img-id="([^"]+)"[^>]*>.*?'
            r'<p[^>]*class="img-description">(.*?)</p>.*?'
            r'</div>)',
            re.DOTALL | re.IGNORECASE
        )

        matches = placeholder_regex.findall(html_content)
        if not matches:
            return html_content

        print(f"  [ImageSourcing] Found {len(matches)} placeholders. Starting parallel processing (8 workers)...")

        # 1. Process each placeholder in a separate thread
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_placeholder = {
                executor.submit(
                    self._source_single_image, 
                    img_id, description, assets_dir, html_content, preserve_candidates, uar
                ): (full_tag, img_id) 
                for full_tag, img_id, description in matches
            }
            
            for future in concurrent.futures.as_completed(future_to_placeholder):
                full_tag, img_id = future_to_placeholder[future]
                try:
                    replacement_html = future.result()
                    if replacement_html:
                        results.append((full_tag, replacement_html))
                except Exception as e:
                    print(f"  [ImageSourcing] Error sourcing {img_id}: {e}")

        # 2. Sequential replacement in HTML content
        for original_tag, new_tag in results:
            html_content = html_content.replace(original_tag, new_tag)

        return html_content

    def _source_single_image(self, img_id: str, description: str, assets_dir: Path, 
                             html_context: str, preserve_candidates: bool, uar = None) -> Optional[str]:
        """Worker function to source a single image. Uses its own browser instance."""
        description = description.strip()
        print(f"    [Thread] Sourcing: {img_id}")

        # 1. Local Lookup (Priority)
        if uar:
            print(f"    [{img_id}] Checking local UAR...")
            import asyncio
            # In ThreadPoolExecutor, we need to handle async calls
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                candidates = uar.intent_match_candidates(description, client=self.client, limit=10)
                best_local, reasoning = loop.run_until_complete(
                    self.local_selector.select_best_async(candidates, description)
                )
                
                if best_local:
                    print(f"    [{img_id}] ✓ LOCAL HIT: {best_local.id} ({reasoning})")
                    # Use existing asset
                    replacement_html = f'<figure class="image-container" id="{img_id}">\n  {best_local.to_img_tag()}\n  <figcaption>{description}</figcaption>\n</figure>'
                    return replacement_html
                else:
                    print(f"    [{img_id}] No local match: {reasoning}")
            finally:
                loop.close()

        # 2. Web Search (Fallback)
        print(f"    [{img_id}] Starting web search...")
        with BrowserManager(headless=self.headless, debug=self.debug, block_resources=True) as bm:
            searcher = GoogleImageSearcher(bm, debug=self.debug)
            downloader = ImageDownloader(bm, debug=self.debug)
            
            max_sourcing_attempts = 3
            all_failed_queries = []
            best_image_path = None
            reason = ""
            best_desc = ""
            
            for attempt in range(max_sourcing_attempts):
                if attempt > 0:
                    print(f"    [{img_id} Retry {attempt+1}] Generating alternative queries...")

                # 1. Strategy (Query generation)
                strategy = self.strategy_gen.generate(
                    description,
                    html_context,  # Full context - no truncation
                    failed_queries=all_failed_queries if all_failed_queries else None
                )
                queries = strategy.get("queries", [description])
                guidance = strategy.get("guidance", "Image should accurately fit description.")
                
                # 2. Search
                image_candidates = searcher.search(queries)
                if not image_candidates:
                    all_failed_queries.extend(queries[:2])
                    continue

                # 3. Download (Top 20 images)
                temp_dir = assets_dir / f"candidates_{img_id}"
                if attempt > 0:
                    temp_dir = assets_dir / f"candidates_{img_id}_attempt{attempt+1}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                local_images = downloader.download_candidates(image_candidates[:20], temp_dir)
                if not local_images:
                    all_failed_queries.extend(queries[:2])
                    continue

                # 4. Selection (Vision API)
                descriptions_map = {}
                for img_path in local_images:
                    txt_path = img_path.with_suffix('.txt')
                    if txt_path.exists():
                        descriptions_map[img_path.name] = txt_path.read_text(encoding='utf-8')
                
                best_image_path, reason, best_desc = self.vision_selector.select_best(
                    local_images, description, guidance, descriptions_map
                )

                if best_image_path:
                    break
                else:
                    all_failed_queries.extend(queries[:2])
            
            if best_image_path:
                # 5. Archive and replace
                final_name = f"{img_id}{best_image_path.suffix}"
                final_path = assets_dir / final_name
                shutil.copy2(best_image_path, final_path)
                
                display_desc = best_desc if best_desc else description
                replacement_html = f'<figure class="image-container" id="{img_id}">\n  <img src="assets/images/{final_name}" alt="{display_desc}">\n  <figcaption>{display_desc}</figcaption>\n</figure>'
                
                # Debug info
                if self.debug:
                    self._write_debug_info(img_id, description, strategy, best_image_path, reason, best_desc, attempt, all_failed_queries, assets_dir)
                
                # Cleanup unless preserved
                if not preserve_candidates:
                    for d in assets_dir.glob(f"candidates_{img_id}*"):
                        if d.is_dir(): shutil.rmtree(d, ignore_errors=True)
                
                return replacement_html

        return None

    def _write_debug_info(self, img_id, description, strategy, best_image_path, reason, best_desc, attempt, all_failed_queries, assets_dir):
        """Helper to write debug metadata."""
        debug_info = {
            "img_id": img_id,
            "description": description,
            "strategy": strategy,
            "selected": best_image_path.name if best_image_path else None,
            "reasoning": reason,
            "selected_image_description": best_desc,
            "total_attempts": attempt + 1,
            "all_failed_queries": all_failed_queries
        }
        debug_file = assets_dir / f"debug_{img_id}.json"
        debug_file.write_text(json.dumps(debug_info, indent=2, ensure_ascii=False), encoding='utf-8')


def create_image_sourcing_agent(client: Optional[GeminiClient] = None) -> ImageSourcingAgent:
    """Create an ImageSourcingAgent instance."""
    return ImageSourcingAgent(client=client)
