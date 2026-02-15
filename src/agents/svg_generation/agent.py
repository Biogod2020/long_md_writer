"""
SVGAgent: SOTA 2.0 SVG Generation Sub-Agent
Handles the full lifecycle of SVG creation: Generation -> Audit -> Repair (Reflection Loop).
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from ...core.gemini_client import GeminiClient
from ...core.types import (
    AgentState,
    AssetEntry,
    AssetSource,
    AssetVQAStatus,
)
from .processor import generate_svg_async, repair_svg_async
from ..asset_management.processors.audit import audit_svg_visual_async, render_svg_to_png_base64
from ..asset_management.utils import generate_figure_html


class SVGAgent:
    """
    Sub-Agent dedicated to SVG generation.
    Implements a formal Reflection Loop to improve SVG quality based on audit feedback.
    """

    MAX_REPAIR_ATTEMPTS = 5

    def __init__(self, client: Optional[GeminiClient] = None, debug: bool = False):
        self.client = client or GeminiClient()
        self.debug = debug

    async def fulfill_directive_async(
        self, 
        d: Any, # VisualDirective
        state: AgentState,
        target_file: Optional[Path] = None
    ) -> Tuple[bool, Optional[AssetEntry], str]:
        """
        Fulfills an SVG visual directive through a Generate-Audit-Repair loop.
        
        Returns:
            (success, asset_entry, html_code)
        """
        ws_path = Path(state.workspace_path)
        out_path = ws_path / "agent_generated"
        out_path.mkdir(parents=True, exist_ok=True)
        
        namespace = d.id.split('-')[0] if '-' in d.id else "s1"
        
        print(f"    [SVGAgent] 🚀 Starting SVG generation loop (ID: {d.id})...")
        
        # 1. Initial Generation
        full_context = d.get_full_context()
        svg_code = await generate_svg_async(
            self.client, 
            full_context, 
            state=state, 
            style_hints=d.style_hints or ""
        )
        
        if not svg_code:
            print(f"    [SVGAgent] ❌ Initial generation failed (ID: {d.id})")
            return False, None, f"<!-- SVG Generation failed for {d.id} -->"

        print(f"    [SVGAgent] ✨ Initial generation successful (len: {len(svg_code)})")
        
        attempt = 0
        is_valid = False
        file_path = out_path / f"{d.id}.svg"
        
        # 2. Reflection Loop: Audit & Repair
        while attempt < self.MAX_REPAIR_ATTEMPTS:
            attempt += 1
            print(f"    [SVGAgent] 📋 VLM Audit (Attempt {attempt}/{self.MAX_REPAIR_ATTEMPTS})...")
            
            # Persist to disk for auditing
            file_path.write_text(svg_code, encoding="utf-8")
            
            # SOTA: Cross-modal audit (Code + Visual)
            audit = await audit_svg_visual_async(
                self.client, 
                svg_code, 
                full_context, 
                state=state, 
                svg_path=file_path
            )

            if audit and audit.get("result") == "pass":
                is_valid = True
                print(f"    [SVGAgent] ✅ Audit PASSED (ID: {d.id})")
                break
            
            # If we reached here, audit failed or needs revision
            issues = audit.get("issues", ["Audit failed or timed out"]) if audit else ["API Timeout/Error"]
            suggestions = audit.get("suggestions", []) if audit else []
            
            print(f"    [SVGAgent] ⚠️ Audit NOT PASSED: {issues[0][:100]}...")
            
            if attempt < self.MAX_REPAIR_ATTEMPTS:
                print(f"    [SVGAgent] 🛠️ Attempting precise repair via Reflection Loop...")
                png_b64 = render_svg_to_png_base64(svg_code)
                new_svg = await repair_svg_async(
                    self.client, 
                    full_context, 
                    svg_code, 
                    issues, 
                    suggestions, 
                    state=state, 
                    rendered_image_b64=png_b64
                )
                
                if not new_svg:
                    print(f"    [SVGAgent] ⚠️ Repair Agent failed to return code, retrying with current version...")
                else:
                    svg_code = new_svg
                    print(f"    [SVGAgent] 🛠️ Repair complete (new len: {len(svg_code)})")
            else:
                print(f"\n⚠️ [SVGAgent] Exhausted {self.MAX_REPAIR_ATTEMPTS} attempts. Asset '{d.id}' remains un-audited.")

        # 3. Finalization
        asset = AssetEntry(
            id=d.id, 
            source=AssetSource.AI, 
            local_path=str(file_path.relative_to(ws_path)),
            semantic_label=d.description[:100], 
            content_hash=hashlib.md5(svg_code.encode()).hexdigest(),
            alt_text=d.description, 
            tags=["svg", namespace], 
            vqa_status=AssetVQAStatus.PASS if is_valid else AssetVQAStatus.FAIL
        )
        
        if asset.crop_metadata.object_fit == "cover":
            asset.crop_metadata.object_fit = "contain"
            
        html_code = generate_figure_html(
            asset, d.description, target_file=target_file, workspace_path=ws_path
        )
        
        return True, asset, html_code
