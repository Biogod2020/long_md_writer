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
import warnings
from pathlib import Path
from typing import Optional, List, Tuple
from tqdm.asyncio import tqdm

# SOTA Fix: Suppress PIL and other UserWarnings that can cause stderr deadlock in concurrent tasks
warnings.filterwarnings("ignore", category=UserWarning)

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
from .processors.mermaid import (
    generate_mermaid_async,
    render_mermaid_to_png,
)
from .processors.audit import refine_caption_async, render_svg_to_png_base64
from ..image_sourcing.agent import ImageSourcingAgent
from ..svg_generation.agent import SVGAgent
from .utils import (
    generate_figure_html,
    generate_mermaid_html,
)


class AssetFulfillmentAgent:
    """
    资产履约 Agent (SOTA 2.0 并行增强版)
    """

    MAX_REPAIR_ATTEMPTS = 5
    DEFAULT_MAX_CONCURRENCY = 5

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        output_dir: str = "generated_assets",
        skip_generation: bool = False,
        skip_search: bool = False,
        debug: bool = False,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        headless: bool = True
    ):
        self.client = client or GeminiClient()
        self.output_dir = output_dir
        self.skip_generation = skip_generation
        self.skip_search = skip_search
        self.debug = debug
        self.semaphore = asyncio.Semaphore(max_concurrency)
        # SOTA: Dedicated semaphore for web search to avoid CAPTCHA
        self.search_semaphore = asyncio.Semaphore(1) 
        self.uar_lock = asyncio.Lock() # SOTA: 用于确保 UAR 持久化线程安全
        self.stuck_detector = StuckDetector()
        
        # SOTA: Defer agent creation to runtime to ensure unique PID-based profiles
        self._headless_setting = headless
        self.svg_agent = SVGAgent(client=self.client, debug=debug)

    async def run_parallel_async(self, state: AgentState) -> AgentState:
        """并行执行全书资产履约 (解耦版)"""
        print(f"\n[AssetFulfillment] 🚀 启动并行生成 (并发: {self.DEFAULT_MAX_CONCURRENCY})")

        # SOTA: 物理同步。强制从磁盘 assets.json 加载，防止逻辑状态 (Checkpoint) 落后于物理状态
        uar_path = Path(state.workspace_path) / "assets.json"
        if uar_path.exists():
            print(f"  [Fulfillment] 🔄 正在从物理磁盘同步资产注册表: {uar_path.name}")
            from ...core.types import UniversalAssetRegistry
            state.asset_registry = UniversalAssetRegistry.load_from_file(str(uar_path))

        # SOTA: 每次运行前重置失败状态，防止死循环
        state.failed_directives = []
        state.asset_revision_needed = False

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
            # Capture the full content of the current file for context
            full_section_content = task["original_path"].read_text(encoding="utf-8")
            
            async with self.semaphore:
                try:
                    if await self._check_asset_exists(d, uar, workspace_path):
                        return (task["original_path"], d, None)

                    d_final = await self._decide_fulfillment_strategy(d, uar, state)
                    
                    # SOTA Fix: Wrap fulfillment in a timeout to prevent proxy/VLM hangs from stopping the whole book
                    try:
                        result_d, new_asset = await asyncio.wait_for(
                            self._fulfill_directive_async(
                                d_final, uar, 
                                workspace_path / "agent_generated", 
                                workspace_path / "agent_sourced", 
                                task["namespace"], workspace_path, state, trace,
                                target_file=task["original_path"],
                                full_section_markdown=full_section_content
                            ),
                            timeout=300 # 5 minutes per asset
                        )
                    except asyncio.TimeoutError:
                        print(f"    [Fulfillment] ⏱️ TIMEOUT for {d.id} after 300s. Skipping.")
                        d.error = "Task timed out"
                        return (task["original_path"], d, None)
                    
                    return (task["original_path"], result_d, new_asset)
                except Exception as e:
                    import traceback
                    print(f"    [Fulfillment] ❌ Worker CRASHED for {d.id}: {e}")
                    traceback.print_exc()
                    d.error = str(e)
                    trace["error"] = traceback.format_exc()
                    return (task["original_path"], d, None)

        print(f"[AssetFulfillment] 正在处理 {len(all_tasks)} 个视觉资产...")
        # SOTA Fix: Redirect tqdm to sys.stdout to avoid stderr lock contention
        import sys
        results = await tqdm.gather(*(worker(t) for t in all_tasks), desc="Fulfillment Progress", file=sys.stdout)

        # SOTA: 统一原子化注册所有新产出的资产
        new_entries = [r[2] for r in results if r[2] is not None]
        if new_entries:
            print(f"  [Fulfillment] 📦 正在将 {len(new_entries)} 个新资产入库...")
            async with self.uar_lock:
                uar.register_batch(new_entries)

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
                if d.fulfilled and d.result_html:
                    # SOTA 2.1: Robust ID-Based Backfill (Primary Strategy)
                    # We look for any :::visual block containing this specific ID.
                    # This makes the process immune to description edits by Editorial QA.
                    import re
                    id_pattern = rf':::visual\s*\{{[^}}]*?"id":\s*"{re.escape(d.id)}"[^}}]*?\}}[\s\S]*?:::'
                    
                    success = False
                    if re.search(id_pattern, current_content):
                        # Use lambda to avoid re.sub interpreting backslashes in result_html (e.g., LaTeX)
                        current_content = re.sub(id_pattern, lambda _: d.result_html, current_content, count=1)
                        success = True
                        if self.debug: print(f"    [Fulfillment] 🎯 通过 ID 锚点成功注入资产: {d.id}")
                    
                    # Fallback to Smart Patch if ID matching fails (rare, but for legacy/malformed blocks)
                    if not success:
                        new_content, success = apply_smart_patch(current_content, d.raw_block, d.result_html)
                        if success:
                            current_content = new_content
                            if self.debug: print(f"    [Fulfillment] 🩹 通过 SmartPatch 兜底注入: {d.id}")
                    
                    # Last resort: Exact literal match
                    if not success and d.raw_block in current_content:
                        current_content = current_content.replace(d.raw_block, d.result_html, 1)
                        success = True

                    if success:
                        if d.result_asset_id: new_assets_count += 1
                        else: reused_count += 1
                    else:
                        print(f"    [Fulfillment] ❌ 严重错误：指令锚点完全丢失 (ID: {d.id})")
                        state.failed_directives.append({"id": d.id, "file": md_path.name, "error": "Anchor lost"})
                else:
                    if not d.fulfilled:
                        state.failed_directives.append({"id": d.id, "file": md_path.name, "error": d.error})
                        state.asset_revision_needed = True

            # 写入并提交该文件的最终修改
            manager.working_path.write_text(current_content, encoding="utf-8")
            manager.commit()

        # SOTA: 最终强制物理持久化 UAR，确保磁盘 assets.json 与内存同步
        async with self.uar_lock:
            uar._persist()

        print(f"[AssetFulfillment] ✅ 履约完成: 新增 {new_assets_count}, 复用 {reused_count}")
        state.batch_fulfillment_complete = True
        return state

    async def _check_asset_exists(self, d: VisualDirective, uar, ws_path: Path) -> bool:
        """
        检查资产是否已经存在且有效。
        """
        asset = uar.get_asset(d.id)
        if not asset:
            return False
            
        abs_path = asset.get_absolute_path(workspace_path=ws_path)
        if abs_path and abs_path.exists():
            print(f"  [Fulfillment] ⚡ 资产已存在，跳过生成: {d.id} ({abs_path.name})")
            d.fulfilled = True
            d.result_html = generate_figure_html(
                asset, d.description, workspace_path=ws_path
            )
            return True
            
        return False

    async def _fulfill_directive_async(self, d, uar, gen_path, src_path, ns, ws_path, state, trace, target_file: Optional[Path] = None, full_section_markdown: str = "") -> Tuple[VisualDirective, Optional[AssetEntry]]:
        gen_path.mkdir(parents=True, exist_ok=True)
        src_path.mkdir(parents=True, exist_ok=True)

        if d.action == AssetFulfillmentAction.GENERATE_SVG:
            success, asset, html = await self.svg_agent.fulfill_directive_async(
                d, state, target_file=target_file
            )
            if success and asset:
                # SOTA 2.0: Post-Fulfillment Semantic Alignment
                svg_path = ws_path / asset.local_path
                if svg_path.exists():
                    svg_code = svg_path.read_text(encoding="utf-8")
                    png_b64 = render_svg_to_png_base64(svg_code)
                    if png_b64:
                        print(f"    [Fulfillment] ✍️ Refining caption for SVG: {d.id}...")
                        refined_caption = await refine_caption_async(
                            self.client, png_b64, d.description, full_section_markdown or d.get_full_context(), state=state
                        )
                        if refined_caption:
                            asset.alt_text = refined_caption
                            asset.semantic_label = refined_caption[:100]
                            # Regenerate HTML with new caption
                            html = generate_figure_html(
                                asset, refined_caption, target_file=target_file, workspace_path=ws_path
                            )
                
                d.fulfilled, d.result_html = True, html
                d.result_asset_id = asset.id
                return d, asset
            return d, None

        if d.action == AssetFulfillmentAction.GENERATE_MERMAID:
            return await self._fulfill_mermaid_step(d, uar, gen_path, ns, ws_path, state, trace, target_file=target_file)
        if d.action == AssetFulfillmentAction.SEARCH_WEB:
            res_d, asset = await self._fulfill_search_step(d, uar, src_path, ns, state, trace, target_file=target_file)
            if res_d.fulfilled and asset:
                # SOTA 2.0: Refine caption for Web images too
                img_path = ws_path / asset.local_path
                if img_path.exists():
                    import base64
                    with open(img_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode("utf-8")
                    
                    print(f"    [Fulfillment] ✍️ Refining caption for Web image: {d.id}...")
                    refined_caption = await refine_caption_async(
                        self.client, img_b64, d.description, full_section_markdown or d.get_full_context(), state=state
                    )
                    if refined_caption:
                        asset.alt_text = refined_caption
                        asset.semantic_label = refined_caption[:100]
                        res_d.result_html = generate_figure_html(
                            asset, refined_caption, target_file=target_file, workspace_path=ws_path
                        )
            return res_d, asset
        if d.action == AssetFulfillmentAction.USE_EXISTING:
            res_d = await self._fulfill_use_existing_step(d, uar, ns, ws_path, state, trace, target_file=target_file)
            return res_d, None
        
        d.fulfilled = True
        d.result_html = f"<!-- Action {d.action} skipped -->"
        return d, None

    async def _fulfill_mermaid_step(self, d, uar, out_path, ns, ws_path, state, trace, target_file: Optional[Path] = None) -> Tuple[VisualDirective, Optional[AssetEntry]]:
        trace["steps"].append({"type": "init", "intent": d.description})
        print(f"    [Fulfillment] 🚀 开始初始 Mermaid 生成 (ID: {d.id})...")
        # SOTA: 传入全量上下文以提升 Mermaid 逻辑准确度
        full_context = d.get_full_context()
        mermaid_code = await generate_mermaid_async(self.client, full_context, state=state)
        
        if not mermaid_code:
            d.error = "Initial Mermaid generation failed"
            return d, None

        from .processors.mermaid import audit_mermaid_async, repair_mermaid_async
        attempt = 0
        is_valid = False
        while attempt < self.MAX_REPAIR_ATTEMPTS:
            attempt += 1
            print(f"    [Fulfillment] 📋 正在进行 Mermaid 审计 (尝试 {attempt}/{self.MAX_REPAIR_ATTEMPTS})...")
            # SOTA: 审计时也必须提供全量上下文
            audit = await audit_mermaid_async(self.client, mermaid_code, full_context, state=state)
            
            if audit and audit.get("result") == "pass":
                is_valid = True
                print(f"    [Fulfillment] ✅ Mermaid 审计通过 (ID: {d.id})")
                break
            
            if attempt < self.MAX_REPAIR_ATTEMPTS:
                issues = audit.get("issues", ["Mermaid syntax error"])
                print(f"    [Fulfillment] ⚠️ Mermaid 审计未通过，正在尝试修复...")
                mermaid_code = await repair_mermaid_async(self.client, full_context, mermaid_code, issues, audit.get("suggestions", []), state=state)
            else:
                print(f"\n⚠️ [WARNING] 已耗尽 {self.MAX_REPAIR_ATTEMPTS} 次修复尝试，Mermaid 资产 '{d.id}' 仍未通过 VLM 审计。")

        if mermaid_code:
            # SOTA: 即使审计不通过，只要有代码也创建一个资产对象，确保不丢失
            asset = AssetEntry(
                id=d.id, 
                source=AssetSource.AI, 
                local_path=None, # 原生 Mermaid 没有物理文件
                semantic_label=d.description[:100], 
                content_hash=hashlib.md5(mermaid_code.encode()).hexdigest(),
                alt_text=d.description, 
                tags=["mermaid", ns], 
                vqa_status=AssetVQAStatus.PASS if is_valid else AssetVQAStatus.FAIL
            )
            
            # SOTA: 改为标准 Markdown 栅栏代码块格式，消除渲染后的代码残留
            native_mermaid_block = f"\n```mermaid\n{mermaid_code}\n```\n"
            
            # 使用 <figure> 包装以保持样式一致性
            d.result_html = f"<figure>\n{native_mermaid_block}\n<figcaption>{d.description}</figcaption>\n</figure>"
            d.fulfilled = True
            d.result_asset_id = asset.id
            
            return d, asset
            
        return d, None

    async def _fulfill_search_step(self, d, uar, src_path, ns, state, trace, target_file: Optional[Path] = None) -> Tuple[VisualDirective, Optional[AssetEntry]]:
        """
        SOTA 2.0 Sub-Agent Integration:
        Calls ImageSourcingAgent as a pure async black box.
        Includes global throttling to avoid IP bans.
        """
        import random
        
        # SOTA: Ensure only one search happens at a time across all parallel fulfillment tasks
        async with self.search_semaphore:
            # Add random jitter to avoid fingerprinting
            jitter = random.uniform(2.0, 5.0)
            if self.debug: print(f"    [Fulfillment] 🕒 Search Jitter: {jitter:.2f}s for {d.id}")
            await asyncio.sleep(jitter)
            
            print(f"    [Fulfillment] 🔍 Calling Sub-Agent for Search: {d.id}")
            
            # SOTA: Create agent HERE to get unique PID-based profile path
            sourcing_agent = ImageSourcingAgent(
                client=self.client, 
                debug=self.debug, 
                headless=self._headless_setting
            )
            
            # Directly await the high-performance async interface
            success, asset, html = await sourcing_agent.fulfill_directive_async(
                d, state, target_file=target_file
            )
        
        if success and asset:
            # SOTA: Inject namespace tags into the returned asset for consistency
            if ns and ns not in asset.tags:
                asset.tags.append(ns)
            if "sourced" not in asset.tags:
                asset.tags.append("sourced")
                
            d.fulfilled, d.result_html = True, html
            d.result_asset_id = asset.id
            return d, asset
            
        print(f"    [Fulfillment] ❌ Sub-Agent failed to source image for {d.id}")
        return d, None

    async def _fulfill_use_existing_step(self, d, uar, ns, ws_path, state, trace, target_file: Optional[Path] = None):
        asset = uar.get_asset(d.matched_asset_id)
        if asset:
            d.fulfilled, d.result_html = True, generate_figure_html(asset, d.description, target_file=target_file, workspace_path=ws_path)
        return d

    def _parse_visual_directives(self, content: str) -> list[VisualDirective]:
        """
        SOTA 2.0 Line-Based State Machine Parser.
        Robustly extracts :::visual ... ::: blocks and captures surrounding context.
        """
        directives = []
        lines = content.splitlines(keepends=True)
        
        in_block = False
        current_block_lines = []
        start_pos = 0
        current_global_pos = 0
        
        # 定义上下文抓取范围 (字符数)
        CONTEXT_WINDOW = 800
        
        for line in lines:
            stripped = line.strip()
            
            if not in_block:
                if stripped.startswith(':::visual'):
                    in_block = True
                    current_block_lines = [line]
                    start_pos = current_global_pos
            else:
                current_block_lines.append(line)
                if stripped == ':::':
                    raw_block = "".join(current_block_lines)
                    end_pos = current_global_pos + len(line)
                    
                    from ...core.json_utils import extract_json_from_text, parse_json_dict_robust
                    raw_json = extract_json_from_text(raw_block)
                    
                    if raw_json:
                        d = VisualDirective(raw_block=raw_block, start_pos=start_pos, end_pos=end_pos)
                        try:
                            cfg = parse_json_dict_robust(raw_json)
                            if not cfg:
                                raise ValueError("Empty or malformed JSON")
                                
                            extracted_id = str(cfg.get("id", "")).strip()
                            d.id = extracted_id if extracted_id else f"v-{len(directives)}"
                            d.action = AssetFulfillmentAction(cfg.get("action", "GENERATE_SVG").upper())
                            d.description = cfg.get("description", "").strip()
                            d.matched_asset_id = cfg.get("matched_asset")
                            d.reuse_score = int(cfg.get("reuse_score", 0))
                            
                            # SOTA: 物理抓取前后文，解决“图不对文”的根本问题
                            d.context_before = content[max(0, start_pos - CONTEXT_WINDOW):start_pos].strip()
                            d.context_after = content[end_pos:min(len(content), end_pos + CONTEXT_WINDOW)].strip()
                            
                            directives.append(d)
                        except Exception as e:
                            print(f"    [Fulfillment] ⚠️ JSON 解析失败: {str(e)} | ID: {d.id}")
                    
                    in_block = False
                    current_block_lines = []
            
            current_global_pos += len(line)
            
        return directives

    async def _decide_fulfillment_strategy(self, d, uar, state) -> VisualDirective:
        """
        SOTA 2.0 智能履约决策器
        平衡“资产一致性”与“创作意图准确性”
        """
        if d.action == AssetFulfillmentAction.USE_EXISTING and d.matched_asset_id:
            if d.reuse_score >= 85: return d
            
        # 1. 语义搜索潜在候选资产
        candidates = await uar.intent_match_candidates_async(d.description, client=self.client, limit=1)
        if not candidates:
            return d

        best_asset = candidates[0]
        
        # 2. 严格意图保护逻辑
        # 保护名单：GENERATE_SVG, GENERATE_MERMAID, SEARCH_WEB
        # 只有在库中存在 MANDATORY (用户强制) 资产或类型完全一致的高分资产时，才允许复用
        if d.action in [AssetFulfillmentAction.GENERATE_SVG, AssetFulfillmentAction.GENERATE_MERMAID, AssetFulfillmentAction.SEARCH_WEB]:
            # 情况 A: 用户强制要求使用的资产，必须服从
            if best_asset.priority == AssetPriority.MANDATORY:
                d.action, d.matched_asset_id = AssetFulfillmentAction.USE_EXISTING, best_asset.id
                return d
            
            # 情况 B: 检查类型一致性。严禁将 Mermaid 意图替换为 SVG 资产
            is_same_type = False
            if d.action == AssetFulfillmentAction.GENERATE_MERMAID and "mermaid" in best_asset.tags:
                is_same_type = True
            elif d.action == AssetFulfillmentAction.GENERATE_SVG and "svg" in best_asset.tags:
                is_same_type = True
            
            # 只有类型一致且匹配度极高时才在生成阶段拦截
            if is_same_type:
                # 这里我们假设语义搜索返回的结果如果排在第一且类型匹配，可以考虑复用
                # 但为了保险，生成阶段我们通常倾向于重新生成以保证 context 的精准匹配
                pass 

            return d # 默认返回原始指令，继续生成/搜索流程

        # 3. 兜底：如果指令本身没指定具体 Action，则尝试使用库资产
        d.action, d.matched_asset_id = AssetFulfillmentAction.USE_EXISTING, best_asset.id
        return d
