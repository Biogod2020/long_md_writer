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
from typing import Optional, List, Tuple
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
from ...core.patcher import StuckDetector, apply_smart_patch
from ...core.json_utils import extract_json_from_text
from .models import VisualDirective
from .processors.svg import generate_svg_async, repair_svg_async
from .processors.mermaid import (
    generate_mermaid_async,
)
from .processors.audit import audit_svg_visual_async, render_svg_to_png_base64
from ..image_sourcing.agent import ImageSourcingAgent
from .utils import (
    generate_figure_html,
    generate_mermaid_html,
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
        self.uar_lock = asyncio.Lock() # SOTA: 用于确保 UAR 持久化线程安全
        self.stuck_detector = StuckDetector()
        self.sourcing_agent = ImageSourcingAgent(client=self.client, debug=debug)

    async def run_parallel_async(self, state: AgentState) -> AgentState:
        """并行执行全书资产履约 (解耦版)"""
        print(f"\n[AssetFulfillment] 🚀 启动并行生成 (并发: {self.DEFAULT_MAX_CONCURRENCY})")

        uar = state.get_uar()
        workspace_path = Path(state.workspace_path)
        debug_path = workspace_path / "fulfillment_debug"
        debug_path.mkdir(exist_ok=True)

        # 1. 收集任务与副本初始化
        all_tasks = []
        file_managers = {} # {original_path: WorkingCopyManager}

        for md_path_str in state.completed_md_sections:
            md_path = Path(md_path_str)
            if not md_path.exists(): continue
            
            from .utils import WorkingCopyManager
            manager = WorkingCopyManager(md_path)
            manager.start_session()
            file_managers[md_path] = manager

            content = md_path.read_text(encoding="utf-8")
            directives = self._parse_visual_directives(content)
            
            for d in directives:
                all_tasks.append({
                    "original_path": md_path,
                    "namespace": md_path.stem.replace("sec-", "s").replace("-", ""),
                    "directive": d
                })

        if not all_tasks:
            print("[AssetFulfillment] 📭 未发现待处理指令")
            return state

        # 2. 阶段一：并行生成 (Parallel Sourcing)
        async def worker(task):
            d = task["directive"]
            trace = {"id": d.id, "file": task["original_path"].name, "steps": []}
            async with self.semaphore:
                try:
                    if await self._check_asset_exists(d, uar, workspace_path):
                        return (task["original_path"], d, None)

                    d_final = await self._decide_fulfillment_strategy(d, uar, state)
                    result_d, new_asset = await self._fulfill_directive_async(
                        d_final, uar, 
                        workspace_path / "agent_generated", 
                        workspace_path / "agent_sourced", 
                        task["namespace"], workspace_path, state, trace,
                        target_file=task["original_path"]
                    )
                    
                    if new_asset:
                        async with self.uar_lock:
                            uar.register_immediate(new_asset)

                    return (task["original_path"], result_d, new_asset)
                except Exception as e:
                    import traceback
                    d.error = str(e)
                    trace["error"] = traceback.format_exc()
                    return (task["original_path"], d, None)

        print(f"[AssetFulfillment] 正在处理 {len(all_tasks)} 个视觉资产...")
        results = await tqdm.gather(*(worker(t) for t in all_tasks), desc="Fulfillment Progress")

        # 3. 阶段二：顺序物理回写 (Sequential Write-back)
        print("\n[AssetFulfillment] 💾 生成完成，开始顺序物理回写...")
        
        file_to_results = {}
        for fp, d, _ in results:
            if fp not in file_to_results: file_to_results[fp] = []
            file_to_results[fp].append(d)

        new_assets_count = 0
        reused_count = 0
        
        for md_path, directives in file_to_results.items():
            manager = file_managers[md_path]
            # 顺序读取当前副本内容
            current_content = manager.working_path.read_text(encoding="utf-8")
            
            for d in directives:
                if d.fulfilled:
                    if d.result_asset_id: new_assets_count += 1
                    else: reused_count += 1
                    
                    if d.result_html:
                        # SOTA: 利用 Universal Smart Patcher 自动处理物理偏移
                        new_content, success = apply_smart_patch(current_content, d.raw_block, d.result_html)
                        if success:
                            current_content = new_content
                        else:
                            # 最终保底：精确替换
                            if d.raw_block in current_content:
                                current_content = current_content.replace(d.raw_block, d.result_html, 1)
                            else:
                                print(f"    [Fulfillment] ❌ 回写失败: {d.id}")
                                state.failed_directives.append({"id": d.id, "file": md_path.name, "error": "Anchor lost"})
                else:
                    state.failed_directives.append({"id": d.id, "file": md_path.name, "error": d.error})
                    state.asset_revision_needed = True

            # 写入并提交该文件的最终修改
            manager.working_path.write_text(current_content, encoding="utf-8")
            manager.commit()

        print(f"[AssetFulfillment] ✅ 履约完成: 新增 {new_assets_count}, 复用 {reused_count}")
        state.batch_fulfillment_complete = True
        return state

    def apply_fulfillment_to_file(self, file_path: Path, directives: List[VisualDirective]):
        """
        SOTA 4.0 动态回写逻辑：使用 Universal Patcher 执行物理固化。
        """
        content = file_path.read_text(encoding="utf-8")
        modified_content = content
        
        for d in directives:
            if d.fulfilled and d.result_html:
                new_content, success = apply_smart_patch(modified_content, d.raw_block, d.result_html)
                if success:
                    modified_content = new_content
                    print(f"    [Fulfillment] 🚀 物理注入成功 (Smart): {d.id}")
                else:
                    # Final fallback to regex if smart patch rejected it
                    print(f"    [Fulfillment] ⚠️ Smart patch rejected {d.id}. Trying exact sub.")
                    if d.raw_block in modified_content:
                        modified_content = modified_content.replace(d.raw_block, d.result_html)
        
        if modified_content != content:
            file_path.write_text(modified_content, encoding="utf-8")
            print(f"  [Fulfillment] ✅ {file_path.name}: 已成功完成物理固化。")
        else:
            print(f"  [Fulfillment] ❌ {file_path.name}: 未检测到可替换内容。")

    async def _check_asset_exists(self, d: VisualDirective, uar, ws_path: Path) -> bool:
        """
        检查资产是否已经存在且有效。
        如果存在，则直接标记为 fulfilled 并返回 True。
        """
        asset = uar.get_asset(d.id)
        if not asset:
            return False
            
        # 验证物理文件是否存在
        abs_path = asset.get_absolute_path(workspace_path=ws_path)
        if abs_path and abs_path.exists():
            print(f"  [Fulfillment] ⚡ 资产已存在，跳过生成: {d.id} ({abs_path.name})")
            d.fulfilled = True
            d.result_html = generate_figure_html(
                asset, d.description, workspace_path=ws_path
            )
            return True
            
        return False

    async def _fulfill_directive_async(self, d, uar, gen_path, src_path, ns, ws_path, state, trace, target_file: Optional[Path] = None) -> Tuple[VisualDirective, Optional[AssetEntry]]:
        gen_path.mkdir(parents=True, exist_ok=True)
        src_path.mkdir(parents=True, exist_ok=True)

        if d.action == AssetFulfillmentAction.GENERATE_SVG:
            return await self._fulfill_svg_step(d, uar, gen_path, ns, ws_path, state, trace, target_file=target_file)
        if d.action == AssetFulfillmentAction.GENERATE_MERMAID:
            res_d = await self._fulfill_mermaid_step(d, ns, state, trace)
            return res_d, None
        if d.action == AssetFulfillmentAction.SEARCH_WEB:
            return await self._fulfill_search_step(d, uar, src_path, ns, state, trace, target_file=target_file)
        if d.action == AssetFulfillmentAction.USE_EXISTING:
            res_d = await self._fulfill_use_existing_step(d, uar, ns, ws_path, state, trace, target_file=target_file)
            return res_d, None
        
        d.fulfilled = True
        d.result_html = f"<!-- Action {d.action} skipped -->"
        return d, None

    async def _fulfill_svg_step(self, d, uar, out_path, ns, ws_path, state, trace, target_file: Optional[Path] = None) -> Tuple[VisualDirective, Optional[AssetEntry]]:
        trace["steps"].append({"type": "init", "intent": d.description})
        svg_code = await generate_svg_async(self.client, d.get_full_context(), state=state, style_hints=d.style_hints or "")
        
        if not svg_code:
            d.error = "Initial SVG generation failed"
            return d, None

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
            # SOTA: Return AssetEntry for aggregated registration
            asset = AssetEntry(
                id=d.id, source=AssetSource.AI, local_path=str(file_path.relative_to(ws_path)),
                semantic_label=d.description[:100], content_hash=hashlib.md5(svg_code.encode()).hexdigest(),
                alt_text=d.description, tags=["svg", ns], vqa_status=AssetVQAStatus.PASS if is_valid else AssetVQAStatus.FAIL
            )
            # uar.register_immediate(asset) # DEPRECATED: Don't call inside worker
            d.fulfilled, d.result_html = True, generate_figure_html(
                asset, d.description, target_file=target_file, workspace_path=ws_path
            )
            return d, asset
        return d, None

    async def _fulfill_mermaid_step(self, d, ns, state, trace):
        code = await generate_mermaid_async(self.client, d.get_full_context(), state=state)
        trace["steps"].append({"type": "init", "code": code})
        if code:
            d.fulfilled, d.result_html = True, generate_mermaid_html(code, d.description)
        return d

    async def _fulfill_search_step(self, d, uar, src_path, ns, state, trace, target_file: Optional[Path] = None) -> Tuple[VisualDirective, Optional[AssetEntry]]:
        import asyncio
        from functools import partial
        loop = asyncio.get_event_loop()
        f = partial(
            self.sourcing_agent._source_single_image, 
            img_id=d.id, 
            description=d.description, 
            assets_dir=src_path,
            html_context=d.get_full_context(), 
            uar=uar, 
            preserve_candidates=True
        )
        html = await loop.run_in_executor(None, f)
        trace["steps"].append({"type": "search", "success": bool(html)})
        
        if html:
            # SOTA: Try to find the actual physical file to create a proper AssetEntry
            found_files = list(src_path.glob(f"{d.id}.*"))
            if found_files:
                img_file = found_files[0]
                ws_path = Path(state.workspace_path)
                asset = AssetEntry(
                    id=d.id, 
                    source=AssetSource.WEB, 
                    local_path=str(img_file.relative_to(ws_path)),
                    semantic_label=d.description[:100], 
                    content_hash=hashlib.md5(img_file.read_bytes()).hexdigest(),
                    alt_text=d.description, 
                    tags=["sourced", ns], 
                    vqa_status=AssetVQAStatus.PENDING
                )
                # Regenerate HTML with robust paths
                html = generate_figure_html(
                    asset, d.description, target_file=target_file, workspace_path=ws_path
                )
                d.fulfilled, d.result_html = True, html
                return d, asset
            
            # Fallback if file matching logic failed but HTML was returned
            d.fulfilled, d.result_html = True, html
        return d, None

    async def _fulfill_use_existing_step(self, d, uar, ns, ws_path, state, trace, target_file: Optional[Path] = None):
        asset = uar.get_asset(d.matched_asset_id)
        trace["steps"].append({"type": "reuse", "asset_id": d.matched_asset_id, "found": bool(asset)})
        if asset:
            d.fulfilled, d.result_html = True, generate_figure_html(
                asset, d.description, target_file=target_file, workspace_path=ws_path
            )
        return d

    def _parse_visual_directives(self, content: str) -> list[VisualDirective]:
        """
        SOTA 4.0 增强型解析器：支持跨行 JSON、支持字段内换行、捕获位置偏移。
        """
        directives = []
        # 模式：:::visual [空白] {JSON内容} [任意直到下一个 :::]
        pattern = re.compile(r':::visual\s*(\{[\s\S]*?\})([\s\S]*?):::', re.DOTALL)
        
        for match in pattern.finditer(content):
            raw = match.group(0)
            json_str = match.group(1).strip()
            
            d = VisualDirective(
                raw_block=raw, 
                start_pos=match.start(), 
                end_pos=match.end()
            )
            try:
                # 预处理 JSON：移除真实换行符，防止 json.loads 崩溃
                sanitized_json = json_str.replace('\n', ' ').replace('\r', '')
                clean_json = extract_json_from_text(sanitized_json) or sanitized_json
                cfg = json.loads(clean_json)
                
                d.id = cfg.get("id", f"v-{len(directives)}")
                d.action = AssetFulfillmentAction(cfg.get("action", "GENERATE_SVG").upper())
                d.description = cfg.get("description", "").strip()
                d.matched_asset_id = cfg.get("matched_asset")
                d.reuse_score = int(cfg.get("reuse_score", 0))
            except Exception as e:
                d.error = f"JSON Error: {str(e)}"
            
            directives.append(d)
        return directives

    async def _decide_fulfillment_strategy(self, d, uar, state) -> VisualDirective:
        """
        SOTA 2.0 策略决策引擎
        
        原则：
        1. 尊重 Writer 的明确复用意图 (如果评分够高 >= 85)
        2. 如果 Writer 要求生成 (GENERATE_SVG) 或 搜索 (SEARCH_WEB)，
           除非本地有匹配得分极高 (>= 90) 的完美资产，否则严禁劫持 Writer 意图。
        """
        # 场景 A: Writer 已经决定要复用
        if d.action == AssetFulfillmentAction.USE_EXISTING and d.matched_asset_id:
            if d.reuse_score >= 85:
                return d
            
        # 场景 B: 寻找本地匹配 (作为第二意见)
        # SOTA: limit=1 提高效率，我们只需要最好的
        candidates = await uar.intent_match_candidates_async(d.description, client=self.client, limit=1)
        
        if candidates:
            best_asset = candidates[0]
            
            # 如果 Writer 要求生成 SVG 或 搜网图，我们非常谨慎
            if d.action in [AssetFulfillmentAction.GENERATE_SVG, AssetFulfillmentAction.SEARCH_WEB]:
                # 只有在本地发现得分极高的条目时才考虑“劫持”以节省资源
                # 目前由于 intent_match 没有返回具体分数，我们设定一个保守策略：
                # 仅当 best_asset 的 ID 与指令 ID 语义高度相关，或它是 MANDATORY 资产时才考虑。
                if best_asset.priority == AssetPriority.MANDATORY:
                    print(f"  [Fulfillment] 发现强制性匹配，执行动作劫持: {d.id} -> USE_EXISTING ({best_asset.id})")
                    d.action, d.matched_asset_id = AssetFulfillmentAction.USE_EXISTING, best_asset.id
                    return d
                
                print(f"  [Fulfillment] 尊重 Writer 决定: 保持 {d.action.value} 动作 ({d.id})")
                return d

            # 只有在 Writer 没把握 (USE_EXISTING 但分数低) 时，我们才尝试换成更好的本地资产
            d.action, d.matched_asset_id = AssetFulfillmentAction.USE_EXISTING, best_asset.id
            
        return d
