# Implementation Plan: Magnum Opus 2.1 (Robustness Hardening)

## Phase 1: 物理层加固 (ID 匹配与死锁防护) [checkpoint: e985c14]
**目标**：确保视觉资产能够精准“降落”到文档中，且并发流水线永不由于 I/O 竞争死锁。

- [x] **Task: 实现基于 ID 的强力锚点匹配**
    - [x] **编写失败测试**：模拟一个 `:::visual` 指令块，其描述文字已被 EditorialQA 修改过，导致字面匹配失败。
    - [x] **代码实现**：修改 `src/agents/asset_management/fulfillment.py`，将基于 ID 的正则匹配 (`Regex-by-ID`) 提升为物理回写的第一优先级。
    - [x] **验证**：确保即使文本相似度为 0%，只要 ID 匹配，图片标签就能正确注入。
- [x] **Task: 消除并发死锁 (e985c14)**
    - [x] **代码实现**：在 `AssetFulfillmentAgent` 中将 `tqdm` 输出重定向至 `sys.stdout`；在履约 Worker 中全局屏蔽 `UserWarning`。
- [x] **Task: 专项压力测试 - 高并发锚点污染测试 (e985c14)**
    - [x] **通过标准**：100% 的生成资产必须通过 ID 匹配成功回写，且进程无死锁挂起。
- [x] **Task: Conductor - User Manual Verification 'Phase 1' (e985c14) (Protocol in workflow.md)**

## Phase 2: 分层 Editorial 重构 (核心任务) [checkpoint: 39f6656]
**目标**：通过本地机械校验和任务量限制，提升 Editorial 阶段的稳定性。

- [x] **Task: 集成 SOTA 机械校验器**
    - [x] **代码实现**：在 `EditorialQAAgent` 中引入 `MarkdownValidator` 进行前置 AST 扫描。
- [x] **Task: 重构 EditorialQAAgent 逻辑流**
    - [x] **代码实现**：实现 Phase 1 (Static) -> Phase 2 (Logic) -> Phase 3 (Visual Intent) -> Phase 4 (Term) 的顺序调用。
- [x] **Task: 限制任务量**
    - [x] **代码实现**：在 `EditorialAdvicer` 中实现 **Atomic Quota (5 slots)**。
- [x] **Task: 专项压力测试 - 极端错误集下的 Quota 执行测试**
    - [x] **通过标准**：验证 Advicer 是否严格执行“每次仅 5 条”的限额。
- [x] **Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)**

## Phase 3: 护栏与回滚机制 [checkpoint: 39f6656]
**目标**：实现 Patch 级别的物理免疫，防止结构损坏。

- [x] **Task: 实现“校验-应用-回滚”闭环**
    - [x] **代码实现**：在 `MarkdownQAAgent` 中应用补丁后立即触发机械校验，失败则回滚。
- [x] **Task: 专项压力测试 - 连续恶意补丁注入测试**
    - [x] **通过标准**：系统必须 100% 成功拦截所有导致结构损坏的补丁。
- [x] **Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)**

## Phase 4: 工作流编排调整与集成 [complete]
**目标**：物理前移 Editorial 节点并完成全量验证。

- [x] **Task: 节点前移 (Shift-Left Editorial)**
    - [x] **代码实现**：更新 `src/orchestration/workflow_markdown.py`，使 `editorial_qa` 在 `batch_fulfillment` 之前运行。
- [x] **Task: 专项压力测试 - 综合 E2E 极限生存测试 (v16 场景模拟)**
    - [x] **通过标准**：全书 100% 履约成功，且产出的 `final_full.md` 无任何语法报错。
- [x] **Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)**
