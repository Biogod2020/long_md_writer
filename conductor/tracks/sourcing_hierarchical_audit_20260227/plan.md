# Implementation Plan: WebSourcing Hierarchical Audit & Deadlock Prevention

## Phase 1: 浏览器下载稳定性加固 (Deadlock Prevention)
**目标**：通过物理熔断和标签回收机制，彻底消除浏览器下载过程中的死锁。

- [ ] Task: 编写失效测试 - 模拟下载挂起场景
    - [ ] 在 `tests/` 下创建 `test_sourcing_deadlock.py`。
    - [ ] 构造一个永远不返回的下载请求，验证当前系统会死锁。
- [ ] Task: 实现基于时间的物理熔断机制 (Timeout-based Circuit Breaker)
    - [ ] 在 `src/agents/image_sourcing/browser.py` 中为下载和导航增加严格的异步超时。
- [ ] Task: 实现自动化标签回收逻辑 (Tab Recycling)
    - [ ] 确保超时后物理关闭对应的 Tab 并释放资源，而非重启整个浏览器。
- [ ] Task: 验证测试通过 - 确保挂起不影响后续任务
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: 分层 VLM 审计逻辑实现 (Hierarchical Audit)
**目标**：实现 10选2 再 选1 的高精度视觉筛选。

- [ ] Task: 编写失效测试 - 验证分层筛选逻辑
    - [ ] 创建 `tests/test_hierarchical_audit.py`。
    - [ ] 模拟 10 个候选资产，验证筛选结果的层次性。
- [ ] Task: 实现搜索结果的随机化与强制 10 项收集
    - [ ] 修改 `src/agents/image_sourcing/search.py`，加入 Shuffle 逻辑。
    - [ ] 实现不足 10 项时的自动补全重试。
- [ ] Task: 实现第一层 10-to-2 审计逻辑
    - [ ] 在 `src/agents/image_sourcing/vision.py` 中定义多图打分与排序逻辑。
- [ ] Task: 实现第二层 2-to-1 审计逻辑
    - [ ] 实现针对两张决赛图的深度对比 Prompt。
- [ ] Task: 验证测试通过
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: 综合集成与全量回归 (Integration & Stress Test)
**目标**：将优化后的逻辑合入主流水线并进行压力测试。

- [ ] Task: 逻辑同步与集成
    - [ ] 更新 `src/agents/image_sourcing/agent.py` 启用新流程。
    - [ ] 确保不触动认证相关的 Cookie/Headers 逻辑。
- [ ] Task: 执行全量工作流压力测试
    - [ ] 运行 `tests/run_sota2_workflow.py` 并开启大规模图片采集。
    - [ ] 验证在高负载下依然无死锁、无认证丢失、资产质量提升。
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
