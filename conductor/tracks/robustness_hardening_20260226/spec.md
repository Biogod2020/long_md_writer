# Specification: 鲁棒性与质量加固 (Magnum Opus 2.1)

## 1. Overview
本 Track 旨在通过“分层审计”和“原子化修复”重构 Editorial 流程，并将其前置于资产履约阶段。核心目标是消除文档结构损坏，并确保文字与视觉意图在物理生成前达成高度一致。

## 2. Functional Requirements

### 2.1 前置分层 Editorial 管道 (Pre-Fulfillment Pipeline)
在 `Writer` 节点后，引入以下顺序运行的审计相位：
*   **Phase 1 (Mechanical)**: 集成 `PyMarkdown` 库。对 Markdown 进行静态扫描，拦截所有语法/渲染错误。
*   **Phase 2 (Logic)**: AI 审计员验证叙事逻辑、知识点覆盖度（对齐 Manifest）以及语言质量。
*   **Phase 3 (Visual Intent)**: 审计 `:::visual` 指令。检查描述是否精准、是否与正文矛盾、是否存在跨章重复。
*   **Phase 4 (Terminology)**: 基于项目 `Glossary`（术语表）执行最终一致性检查。

### 2.2 原子化修复协议 (Atomic Edit Quota)
*   **任务限额**: `EditorialAdvicer` 每次迭代产生的修改指令不得超过 5 条。
*   **优先级排序**: `Critic` 对发现的问题进行 `P0 (Critical)` 到 `P2 (Nitpick)` 的排序，系统优先修复 P0。

### 2.3 验证驱动的物理回滚 (Safety Shield)
*   **回滚机制**: 任何 Patch 应用后，若 Phase 1 校验失败（ structural error），系统自动执行 `git-style` 回滚并向 AI 报错。

### 2.4 ID 锚点回填 (Robust Fulfillment)
*   **回写逻辑**: `AssetFulfillmentAgent` 必须使用正则表达式通过 `id` 字段定位指令块，彻底废弃基于全文描述的字面匹配。

## 3. Non-Functional Requirements
*   **性能**: Phase 1 机械校验需在 500ms 内完成。
*   **稳定性**: 彻底消除 `tqdm` 与 `stderr` 的死锁竞争。

## 4. Acceptance Criteria
- [ ] 视觉资产即使在描述被编辑后也能正确注入。
- [ ] 最终文档中不存在结构性损坏（未闭合块/JSON）。
- [ ] 流水线 100% 完成任务，无需手动终止进程。
- [ ] 并行履约不再死锁。