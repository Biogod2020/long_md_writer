# Implementation Plan: Fulfillment 并发加速与异步可靠性加固

## Phase 1: 异步链路完整性加固 (Async Integrity)
**目标**：物理消除未 await 漏洞，确保 Proxy 端 context 及时清理。

- [ ] **Task: 静态分析与漏点扫描**
    - [ ] **扫描**：使用 `grep -r "generate_structured_async"` 扫描 `src/agents/`。
    - [ ] **修复**：确保 `src/agents/image_sourcing/strategy.py` 中的所有调用都带有 `await`。
- [ ] **Task: 强化 GeminiClient 的 Lifecycle 管理**
    - [ ] **代码实现**：在 `generate_async` 的 `finally` 块中确保 `httpx` 连接的正确释放，降低 stale context 风险。
- [ ] **Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)**

## Phase 2: 智能并发调度与 429 物理退避 (Smart Concurrency)
**目标**：提升 Thinking 并发上限，并实现对 429 冷却期的“物理感知”。

- [ ] **Task: 升级全局信号量**
    - [ ] **代码实现**：将 `GeminiClient._heavy_thinking_semaphore` 提升至 3。
- [ ] **Task: 实现 429 "Stay & Sleep" 逻辑**
    - [ ] **代码实现**：在 `GeminiClient.generate_async` 中，解析 429 错误中的 `reset after XXs`。
    - [ ] **逻辑实现**：如果检测到冷却期，直接 `await asyncio.sleep(XX + 2)`，随后原地重新发起请求，不计入重试损耗。
- [ ] **Task: 任务分流微调**
    - [ ] **代码实现**：在 `src/agents/asset_management/fulfillment.py` 中，将 `refine_caption_async` 的 `thinking_level` 强制设为 `MEDIUM`。
- [ ] **Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)**

## Phase 3: 全量性能达标验证 (Stress Test)
**目标**：在 Thinking HIGH 模式下完成 v18 全量履约，验证 4 分钟达标。

- [ ] **Task: 极速履约压力测试**
    - [ ] **测试设计**：运行 `tests/verification_v18.py`。
    - [ ] **通过标准**：Fulfillment 阶段总耗时 < 4 分钟，且无 `RuntimeWarning: coroutine was never awaited` 警告。
- [ ] **Task: 稳定性验收**
    - [ ] **检查**：验证所有 16 个资产 100% 履约，无 `ReadError` 崩溃。
- [ ] **Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)**
