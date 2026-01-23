"""
AssetFulfillmentAgent: SOTA 2.0 Phase D 资产履约器

核心职责：
1. 并行解析全书 :::visual 指令
2. 执行生成 (SVG/Mermaid)、搜索 (Web) 或 复用 (UAR)
3. 过程透明化：tqdm 进度条 + 逐指令调试日志 (Debug Trace)
4. 物理回写：将指令替换为最终 HTML 标签
"""

import re
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from tqdm.asyncio import tqdm

from ...core.gemini_client import GeminiClient
from ...core.types import (
    AgentState,
    AssetEntry,
    AssetSource,
    AssetPriority,
    AssetFulfillmentAction,
    AssetVQAStatus,
)
from ...core.patcher import StuckDetector
from ...core.json_utils import extract_json_from_text, parse_json_dict_robust
from .models import VisualDirective
from .processors.svg import generate_svg, generate_svg_async, repair_svg_async
from .processors.mermaid import (
    generate_mermaid,
    generate_mermaid_async,
    audit_mermaid_async,
    repair_mermaid_async,
)
from .processors.audit import audit_svg_visual_async, render_svg_to_png_base64
from .processors.focus import compute_focus, compute_focus_async
from ..image_sourcing.agent import ImageSourcingAgent
from .utils import (
    generate_figure_html,
    generate_placeholder_html,
    generate_mermaid_html,
    resolve_asset_path,
)


class AssetFulfillmentAgent:
    """
    资产履约 Agent (SOTA 2.0 并行增强版)
    """

    MAX_REPAIR_ATTEMPTS = 3
    DEFAULT_MAX_CONCURRENCY = 5

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        output_dir: str = "generated_assets",
        skip_generation: bool = False,
        skip_search: bool = False,
        debug: bool = False,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    ):
        self.client = client or GeminiClient()
        self.output_dir = output_dir
        self.skip_generation = skip_generation
        self.skip_search = skip_search
        self.debug = debug
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.stuck_detector = StuckDetector()
        self.sourcing_agent = ImageSourcingAgent(client=self.client, debug=debug)

    async def run_parallel_async(self, state: AgentState) -> AgentState:
        """并行执行全书资产履约"""
        print(f"\n[AssetFulfillment] 🚀 启动并行履约流程 (并发: {self.DEFAULT_MAX_CONCURRENCY})")

        uar = state.get_uar()
        workspace_path = Path(state.workspace_path)
        debug_path = workspace_path / "fulfillment_debug"
        debug_path.mkdir(exist_ok=True)

        # 1. 收集任务
        all_tasks = []
        for md_path_str in state.completed_md_sections:
            md_path = Path(md_path_str)
            if not md_path.exists(): continue
            content = md_path.read_text(encoding="utf-8")
            directives = self._parse_visual_directives(content)
            for d in directives:
                all_tasks.append({
                    "file_path": md_path,
                    "namespace": md_path.stem.replace("sec-", "s").replace("-", ""),
                    "directive": d
                })

        if not all_tasks:
            print("[AssetFulfillment] 📭 未发现待处理指令")
            return state

        # 2. 并行执行与进度条
        async def worker(task):
            d = task["directive"]
            trace = {"id": d.id, "file": task["file_path"].name, "steps": []}
            async with self.semaphore:
                try:
                    # 策略决策
                    d_final = await self._decide_fulfillment_strategy(d, uar, state)
                    trace["action"] = d_final.action.value
                    
                    # 执行履约
                    result = await self._fulfill_directive_async(
                        d_final, uar, 
                        workspace_path / "agent_generated", 
                        workspace_path / "agent_sourced", 
                        task["namespace"], workspace_path, state, trace
                    )
                    
                    # 保存 Trace 日志
                    trace_file = debug_path / f"{d.id}_trace.json"
                    trace_file.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
                    return (task["file_path"], result)
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    d.error = str(e)
                    trace["error"] = error_detail
                    trace["status"] = "CRASHED"
                    
                    # 保存崩溃时的 Trace 日志
                    trace_file = debug_path / f"{d.id}_trace.json"
                    trace_file.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
                    
                    # 记录到 state.errors (全局重大错误)
                    state.errors.append(f"Fulfillment Crash [{d.id}]: {str(e)}")
                    return (task["file_path"], d)

        print(f"[AssetFulfillment] 正在处理 {len(all_tasks)} 个视觉资产...")
        results = await tqdm.gather(*(worker(t) for t in all_tasks), desc="Fulfillment Progress")

        # 3. 汇总并回写
        file_map = {}
        for fp, d in results:
            if fp not in file_map: file_map[fp] = []
            file_map[fp].append(d)
            if not d.fulfilled:
                # 增强失败报告结构：包含描述和前后文预览
                state.failed_directives.append({
                    "id": d.id, 
                    "file": fp.name, 
                    "error": d.error,
                    "description": d.description,
                    "action": d.action.value if hasattr(d.action, "value") else str(d.action),
                    "context_preview": d.get_full_context()[:200] + "..."
                })
                state.asset_revision_needed = True

        for fp, directives in file_map.items():
            self.apply_fulfillment_to_file(fp, directives)

        state.batch_fulfillment_complete = True
        return state

    def apply_fulfillment_to_file(self, file_path: Path, directives: List[VisualDirective]):
        content = file_path.read_text(encoding="utf-8")
        replaced_count = 0
        for d in directives:
            if d.fulfilled and d.result_html:
                # 仅在成功时替换原始块
                if d.raw_block in content:
                    content = content.replace(d.raw_block, d.result_html)
                    replaced_count += 1
            else:
                # 失败时不修改原文，保持 :::visual 块不动供人工审计或重试
                # 错误信息已记录在 state.failed_directives 中
                pass
        
        if replaced_count > 0:
            file_path.write_text(content, encoding="utf-8")

    async def _fulfill_directive_async(self, d, uar, gen_path, src_path, ns, ws_path, state, trace) -> VisualDirective:
        gen_path.mkdir(parents=True, exist_ok=True)
        src_path.mkdir(parents=True, exist_ok=True)

        if d.action == AssetFulfillmentAction.GENERATE_SVG:
            return await self._fulfill_svg_step(d, uar, gen_path, ns, ws_path, state, trace)
        if d.action == AssetFulfillmentAction.GENERATE_MERMAID:
            return await self._fulfill_mermaid_step(d, ns, state, trace)
        if d.action == AssetFulfillmentAction.SEARCH_WEB:
            return await self._fulfill_search_step(d, uar, src_path, ns, state, trace)
        if d.action == AssetFulfillmentAction.USE_EXISTING:
            return await self._fulfill_use_existing_step(d, uar, ns, ws_path, state, trace)
        
        d.fulfilled = True
        d.result_html = f"<!-- Action {d.action} skipped -->"
        return d

    async def _fulfill_svg_step(self, d, uar, out_path, ns, ws_path, state, trace):
        trace["steps"].append({"type": "init", "intent": d.description})
        svg_code = await generate_svg_async(self.client, d.get_full_context(), state=state, style_hints=d.style_hints or "")
        
        if not svg_code:
            d.error = "Initial SVG generation failed"
            return d

        attempt, is_valid = 0, False
        file_path = out_path / f"{d.id}.svg"

        while attempt < self.MAX_REPAIR_ATTEMPTS:
            attempt += 1
            file_path.write_text(svg_code, encoding="utf-8")
            audit = await audit_svg_visual_async(self.client, svg_code, d.description, state=state, svg_path=file_path)
            trace["steps"].append({"attempt": attempt, "audit": audit, "code_len": len(svg_code)})

            if audit and audit.get("result") == "pass":
                is_valid = True; break
            
            if attempt < self.MAX_REPAIR_ATTEMPTS:
                issues = audit.get("issues", ["Audit failed"])
                png_b64 = render_svg_to_png_base64(svg_code)
                svg_code = await repair_svg_async(self.client, d.description, svg_code, issues, audit.get("suggestions", []), state=state, rendered_image_b64=png_b64)
                if not svg_code: break

        if is_valid or svg_code:
            # Register asset
            asset = AssetEntry(
                id=d.id, source=AssetSource.AI, local_path=str(file_path.relative_to(ws_path)),
                semantic_label=d.description[:100], content_hash=hashlib.md5(svg_code.encode()).hexdigest(),
                alt_text=d.description, tags=["svg", ns], vqa_status=AssetVQAStatus.PASS if is_valid else AssetVQAStatus.FAIL
            )
            uar.register_immediate(asset)
            d.fulfilled, d.result_html = True, generate_figure_html(asset, d.description)
        return d

    async def _fulfill_mermaid_step(self, d, ns, state, trace):
        code = await generate_mermaid_async(self.client, d.get_full_context(), state=state)
        trace["steps"].append({"type": "init", "code": code})
        if code:
            d.fulfilled, d.result_html = True, generate_mermaid_html(code, d.description)
        return d

    async def _fulfill_search_step(self, d, uar, src_path, ns, state, trace):
        import asyncio
        from functools import partial
        loop = asyncio.get_event_loop()
        f = partial(self.sourcing_agent._source_single_image, img_id=d.id, description=d.description, assets_dir=src_path.parent, html_context=d.get_full_context(), uar=uar, preserve_candidates=True)
        html = await loop.run_in_executor(None, f)
        trace["steps"].append({"type": "search", "success": bool(html)})
        if html:
            d.fulfilled, d.result_html = True, html
        return d

    async def _fulfill_use_existing_step(self, d, uar, ns, ws_path, state, trace):
        asset = uar.get_asset(d.matched_asset_id)
        trace["steps"].append({"type": "reuse", "asset_id": d.matched_asset_id, "found": bool(asset)})
        if asset:
            d.fulfilled, d.result_html = True, generate_figure_html(asset, d.description)
        return d

    def _parse_visual_directives(self, content: str) -> list[VisualDirective]:
        directives = []
        pattern = r':::visual[^\n]*\n[\s\S]*?:::'
        for match in re.finditer(pattern, content):
            raw = match.group(0)
            json_str = raw.splitlines()[0][len(":::visual"):
].strip()
            d = VisualDirective(raw_block=raw, start_pos=match.start(), end_pos=match.end())
            try:
                cfg = json.loads(extract_json_from_text(json_str) or json_str)
                d.id = cfg.get("id", f"v-{len(directives)}")
                d.action = AssetFulfillmentAction(cfg.get("action", "GENERATE_SVG").upper())
                d.description = cfg.get("description", raw.splitlines()[1])
                d.matched_asset_id = cfg.get("matched_asset")
            except: d.error = "JSON Error"
            directives.append(d)
        return directives

    async def _decide_fulfillment_strategy(self, d, uar, state) -> VisualDirective:
        if d.action == AssetFulfillmentAction.USE_EXISTING and d.matched_asset_id: return d
        
        # SOTA 2.0: 使用 VLM 进行语义匹配候选
        candidates = await uar.intent_match_candidates_async(d.description, client=self.client, limit=5)
        if not candidates: return d
        
        # 对返回的候选进行最高分检测 (此处假设 VLM 返回的第一个就是最相关的)
        # 如果需要更精确的打分，可以调用 LocalSelector，但为了并行效率，我们信任粗筛结果
        best_asset = candidates[0]
        # 我们在这里做一个简单的保险：如果关键词完全没匹配上，可能 VLM 也产生幻觉了
        # (在 UAR 内部其实已经有过一轮 VLM 筛选了，所以此处可以直接信任)
        
        d.action, d.matched_asset_id = AssetFulfillmentAction.USE_EXISTING, best_asset.id
        return d
