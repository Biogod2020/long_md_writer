# Implementation Plan: Validator Robustness & Block-Aware Upgrade

本计划旨在升级 `src/core/validators.py` 中的 `MarkdownStructureValidator`，使其支持跨行 JSON 配置提取，解决校验器与 AI 格式化输出之间的契约冲突。

## Phase 1: 故障重现与测试地基 (Red Phase)
在修改代码前，必须先建立能够触发当前错误的测试用例。

- [x] Task: 创建回归测试文件 3c4d09a
    - [x] 在 `tests/` 目录下创建 `test_validator_robustness.py`。
    - [x] 收集之前 Iteration 1/2 中导致失败的原始 Markdown 片段（包含多行 JSON）。
- [ ] Task: 编写失效测试用例 (Failing Tests)
    - [ ] **用例 1 (多行配置)**：构造一个 `:::visual` 块，JSON 分布在多行。
    - [ ] **用例 2 (极端排版)**：构造包含大量冗余空格和空行的配置块。
    - [ ] **用例 3 (核心规范)**：编写故意缺少 `id` 或命名空间前缀错误的用例，确保“严守项”依然有效。
- [ ] Task: 执行测试并确认失败
    - [ ] 运行 `pytest tests/test_validator_robustness.py`。
    - [ ] 确认当前代码在处理多行用例时会抛出“缺少配置”或“JSON 解析错误”。
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: 校验器逻辑重构 (Green Phase)
重构 `src/core/validators.py`，引入“块感知”能力。

- [x] Task: 实现“块感知”收集逻辑 75a71e4
    - [x] 修改 `MarkdownStructureValidator` 的扫描循环。
    - [x] 当检测到 `:::visual` 或 `:::script` 时，进入循环收集状态直到 `:::`。
- [x] Task: 集成鲁棒的 JSON 提取器 75a71e4
    - [x] 确保调用项目中现有的 `extract_json_from_text` 工具处理收集到的文本块。
    - [x] 实现针对提取后对象的“核心属性（ID, 命名空间）”二次校验。
- [x] Task: 验证测试通过 75a71e4
    - [x] 再次运行 `pytest tests/test_validator_robustness.py`。
    - [x] 确保所有多行用例和极端排版用例全部变为 Green。
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md) 75a71e4

## Phase 3: 架构一致性与全量回归 (Refactor & Integration)
确保校验层与执行层完全同步，并进行全量安检。

- [x] Task: 逻辑同步检查 75a71e4
    - [x] 对比 `src/agents/asset_fulfillment.py`（或其他执行层逻辑）中的提取算法。
    - [x] 若有差异，将提取逻辑抽象为 `src/core/utils/` 中的统一组件。
- [x] Task: 执行全量工作流回归测试 75a71e4
    - [x] 运行现有的 SOTA2 流程测试（如 `tests/run_sota2_workflow.py` 的子集）。
    - [x] 确保升级后的校验器不会对现有的单行配置产生负面影响。
- [x] Task: 代码风格与文档更新 75a71e4
    - [x] 运行 `ruff` 进行静态检查。
    - [x] 为重构后的 `MarkdownStructureValidator` 编写详细的 docstrings。
- [x] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md) 75a71e4

## Phase 4: 任务交付 (Final Seal)
- [ ] Task: 提交代码并附加 Git Notes
- [ ] Task: 更新任务状态并标记 Checkpoint
