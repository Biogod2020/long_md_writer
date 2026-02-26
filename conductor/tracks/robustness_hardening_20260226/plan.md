# Implementation Plan: Magnum Opus 2.1 (Robustness Hardening)

## Phase 1: 物理层加固 (ID 匹配与死锁防护) [checkpoint: e985c14]
**目标**：确保视觉资产能够精准“降落”到文档中，且并发流水线永不由于 I/O 竞争死锁。

- [ ] **Task: 实现基于 ID 的强力锚点匹配**
    - [ ] **编写失败测试**：模拟一个 `:::visual` 指令块，其描述文字已被 EditorialQA 修改过，导致字面匹配失败。
    - [ ] **代码实现**：修改 `src/agents/asset_management/fulfillment.py`，将基于 ID 的正则匹配 (`Regex-by-ID`) 提升为物理回写的第一优先级。
    - [ ] **验证**：确保即使文本相似度为 0%，只要 ID 匹配，图片标签就能正确注入。
- [x] **Task: 消除并发死锁 (e985c14)**
    - [ ] **编写测试**：进行高并发履约压力测试（同时处理 10+ 资产），观察 UAR 锁是否会触发死锁。
    - [ ] **代码实现**：在 `AssetFulfillmentAgent` 中将 `tqdm` 输出重定向至 `sys.stdout`；在履约 Worker 中全局屏蔽 `UserWarning`。
- [x] **Task: 专项压力测试 - 高并发锚点污染测试 (e985c14)**
    - [ ] **测试设计**：启动 20 个并发履约任务，并人为随机修改 Markdown 中 100% 的指令描述文字。
    - [ ] **通过标准**：100% 的生成资产必须通过 ID 匹配成功回写，且进程无死锁挂起。
- [x] **Task: Conductor - User Manual Verification 'Phase 1' (e985c14) (Protocol in workflow.md)**

## Phase 2: 分层 Editorial 重构 (核心任务)
**目标**：通过本地机械校验和任务量限制，提升 Editorial 阶段的稳定性。

- [x] **Task: 集成 SOTA 机械校验器**
    - [ ] **代码实现**：引入 `markdown-it-py` 或 `PyMarkdown` 库。
    - [ ] **验证**：确保能够物理识别所有 `:::` 容器的平衡性及 JSON 语法的合法性。
- [x] **Task: 重构 EditorialQAAgent 逻辑流**
    - [ ] **代码实现**：修改 `src/agents/editorial_qa_agent.py` 的 `run_async`，实现 Phase 1 (Static) -> Phase 2 (Logic) -> Phase 3 (Visual Intent) -> Phase 4 (Term) 的顺序调用。
    - [ ] **限制任务量**：在 `EditorialAdvicer` 中实现 **Atomic Quota**，确保单次修复迭代产生的指令不超过 5 条。
- [x] **Task: 专项压力测试 - 极端错误集下的 Quota 执行测试**
    - [ ] **测试设计**：输入一个包含 50+ 处刻意制造错误（含结构、术语、逻辑错误）的巨型文档。
    - [ ] **通过标准**：验证 Advicer 是否严格执行“每次仅 5 条”的限额，且机械校验相位能在 1s 内处理 5 万字文档。
- [ ] **Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)**

## Phase 3: 护栏与回滚机制
**目标**：实现 Patch 级别的物理免疫，防止结构损坏。

- [x] **Task: 实现“校验-应用-回滚”闭环 (提前完成)**
    - [ ] **代码实现**：修改 `src/agents/markdown_qa/fixer.py`，在应用补丁后立即触发机械校验相位。
    - [ ] **逻辑实现**：如果检测到 ERROR 级别错误，物理回滚该文件至 Patch 前的状态，并将错误上下文回传。
- [x] **Task: 专项压力测试 - 连续恶意补丁注入测试 (提前完成)**
    - [ ] **测试设计**：模拟 AI 连续生成 10 个破坏 JSON 结构或 LaTeX 平衡的错误补丁。
    - [ ] **通过标准**：系统必须 100% 成功拦截所有坏补丁，文档内容始终保持在 Patch 之前的最后一次稳定状态。
- [ ] **Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)**

## Phase 4: 工作流编排调整与集成 [complete]
**目标**：物理前移 Editorial 节点并完成全量验证。

- [x] **Task: 节点前移 (Shift-Left Editorial)**
    - [ ] **代码实现**：更新 `src/orchestration/workflow_markdown.py`，调整 Graph 边，使 `editorial_qa` 在 `batch_fulfillment` 之前运行。
- [ ] **Task: 专项压力测试 - 综合 E2E 极限生存测试 (v16 场景模拟)**
    - [ ] **测试设计**：模拟 `v16` 的深度技术写作场景，包含 15+ 复杂资产，并在履约中途随机触发 Editorial 干扰。
    - [ ] **通过标准**：全书 100% 履约成功，且产出的 `final_full.md` 无任何语法报错。
- [x] **Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)**