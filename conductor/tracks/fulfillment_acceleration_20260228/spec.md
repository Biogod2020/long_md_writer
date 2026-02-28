# Specification: Fulfillment 并发加速与异步可靠性加固 (v2)

## 1. Overview
针对 AIClient-2-API 的 429 冷却期、stale context 警告以及 Python 端的异步漏点，建立一套“物理级可靠”的履约链路。

## 2. Functional Requirements

### 2.1 异步链路完整性 (Async Integrity)
*   **修复未 await 漏洞**：物理定位并修复 `coroutine was never awaited` 警告（重点在 `StrategyGenerator`）。
*   **Stale Context 防护**：通过在 `GeminiClient` 内部建立更严格的 `requestId` 管理和 `timeout` 回收机制，减少 Proxy 端的 stale context 积压。

### 2.2 智能并发与 429 物理退避 (Smart Backoff)
*   **解除硬并发限制**：将 `_heavy_thinking_semaphore` 提升至 **3**，利用账号池并行承载 Thinking 负载。
*   **实现“物理冷静期”等待 (Physical Cool-down)**：
    *   捕获 429 报错中的 `reset after XXs`。
    *   系统不再判定账号不健康，而是直接 `await asyncio.sleep(XX + 2)`。
    *   等待期间，该协程保持活跃，不触发重试计数损耗。
*   **混合优先级调度**：
    *   **SVG 创作/审计**：维持 `Thinking: HIGH`，使用轮询模式平摊冷却。
    *   **搜索/图注优化**：降级为 `Thinking: MEDIUM`，利用 `antigravity` 池快速通行。

### 2.3 任务执行力 (Performance)
*   实现 4 分钟内全书履约闭环。

## 3. Acceptance Criteria
*   **无僵尸协程**：`tracemalloc` 追踪显示 0 个 un-awaited coroutines。
*   **无 ReadError**：通过全局信号量（3）与物理退避，彻底消除读取错误。
*   **4 分钟达标**：全量 v18 履约总时长 < 240s。
