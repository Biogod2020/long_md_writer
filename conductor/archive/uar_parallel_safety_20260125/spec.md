# Specification: Universal Asset Registry Parallel Safety & Reporting

## 1. Overview
修复在并行资产履约（Asset Fulfillment）过程中，由于多线程同时写入 `assets.json` 导致的 UAR 数据丢失（Race Condition）问题。同时，完善最终资产产出统计，确保 "Generated", "Sourced", "Reused", "Mermaid" 等不同类型的资产都被准确记录。

## 2. Functional Requirements
- **Thread-Safe UAR Persistence**:
    - 在并行履约阶段，禁止 Worker 线程直接调用 `uar.register_immediate()` 进行磁盘写入。
    - 引入 **内存聚合 (In-Memory Aggregation)** 机制：所有 Worker 将产生的新资产暂存在线程安全的队列或列表结构中。
    - 在并行任务全部完成后，由主线程一次性批量将这些资产注册并持久化到 `assets.json`。
- **Comprehensive Asset Accounting**:
    - 在最终报告中，不仅要统计新增的资产，还要统计被成功复用的资产和生成的 Mermaid 图表。
    - `AssetFulfillmentAgent` 需要返回一个详细的 `FulfillmentReport` 对象，包含：
        - `new_assets`: 新生成/下载的资产列表
        - `reused_assets`: 复用的现有资产列表
        - `mermaid_charts`: 生成的 Mermaid 图表数量
        - `failed_directives`: 失败的任务列表

## 3. Acceptance Criteria
- **Zero Data Loss**: 在高并发（例如 5-10 线程）履约测试下，生成的 `assets.json` 必须包含所有成功产出的新资产，数量必须与 Trace Log 一致。
- **Accurate Reporting**: 工作流结束时的 "Final Assets Produced" 统计数必须等于 (新生成 + 新下载 + 复用 + Mermaid) 的总和，或者明确分类显示。
- **Trace Consistency**: `fulfillment_debug/` 目录下的 Trace 文件数量必须与最终报告中的任务总数一致。
