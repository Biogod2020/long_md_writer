# Implementation Plan: Fulfillment Robustness

## Phase 1: 核心能力恢复 (Core Restoration) [checkpoint: 7b62746]
- [x] **Task: 补全 UAR 接口** (65039a3)
    - 在 `src/core/types.py` 的 `UniversalAssetRegistry` 类中重新实现 `intent_match_candidates`。
    - 使用 Gemini Flash 进行语义粗筛逻辑。
- [x] **Task: 物理回写逻辑加固** (65039a3)
    - 修改 `src/agents/asset_management/fulfillment.py` 中的 `apply_fulfillment_to_file`。
    - 增加“失败保留”逻辑，确保 `raw_block` 在失败时不被错误替换，仅记录错误。
- [x] **Task: 修复策略劫持逻辑 (Fix Strategy Hijacking)** (bfb355f)
    - 修改 `fulfillment.py` 中的 `_decide_fulfillment_strategy`。
    - 尊重 Writer 提供的 `reuse_score`：如果分数低于阈值 (如 80) 或原始 Action 是 `GENERATE_SVG`/`SEARCH_WEB`，不应强制改为 `USE_EXISTING`。
- [x] **Task: 优化网络采购成功率 (Optimize Web Sourcing Success Rate)** (Final Restoration)
    - 升级 `src/agents/image_sourcing/downloader.py`。
    - 增强 Session 注入逻辑，确保 Referer 与目标域名匹配。
    - 移除不稳定的浏览器原生下载，统一使用 Session Injection。
- [x] **Task: Conductor - User Manual Verification 'Core Restoration' (Protocol in workflow.md)** (7b62746)

## Phase 2: 并行观测与异常增强 (Observability) [checkpoint: ebdcf62]
- [x] **Task: 增强异常捕获** (85f8526)
    - 在 `fulfillment.py` 的并行 `worker` 函数中，捕获所有异常并使用 `traceback` 或详细信息填充 `d.error`。
    - 确保 `trace.json` 中的 `steps` 记录每一个阶段的详细结果。
- [x] **Task: 完善失败报告结构** (85f8526)
    - 在 `AgentState` 中确保 `failed_directives` 记录了足够的人类审计信息（前后文预览）。
- [x] **Task: Conductor - User Manual Verification 'Observability' (Protocol in workflow.md)** (ebdcf62)

## Phase 3: 验证与 E2E 测试 (Verification) [checkpoint: 07ffb91]
- [x] **Task: 编写针对性单元测试** (3b275fd)
    - 模拟 `intent_match_candidates` 场景，验证本地搜索逻辑。
- [x] **Task: 运行 E2E 验证任务** (07ffb91)
    - 使用 `tests/debug_sota2_workflow.py` 重新运行，确认 500 错误被优雅捕获且文件内容安全。
- [x] **Task: Conductor - User Manual Verification 'Final Verification' (Protocol in workflow.md)** (07ffb91)
