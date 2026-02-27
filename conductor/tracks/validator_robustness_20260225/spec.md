# Track Specification: Validator Robustness & Block-Aware Upgrade

## 1. Overview
当前系统的 `MarkdownStructureValidator` 采用硬编码的“单行假设”，要求 `:::visual` 后必须紧跟单行 JSON。这与 AI 喜欢输出多行格式化 JSON 的本性相冲突，导致了“修复越改越错”的恶性循环。本任务旨在升级校验器，使其具备“块感知（Block-Aware）”能力，在放宽排版限制的同时，严守核心资产规范。

## 2. Functional Requirements

### 2.1 块感知扫描 (Block-Aware Scanning)
- **进入模式**：当校验器扫描到 `:::visual` 或 `:::script` 标记时，不再仅检查当前行后缀，而是进入“内容收集模式”。
- **结束标记**：持续收集行内容，直到遇到对应的 `:::` 结束标记。
- **跨行提取**：将收集到的多行文本合并，利用鲁棒的 JSON 提取工具（如 `extract_json_from_text`）从中识别配置对象。

### 2.2 “外松内紧”校验策略
- **放宽项 (Flexible)**：
    - 允许 JSON 配置跨多行存在。
    - 忽略冗余的空格、缩进及空行。
    - 兼容 AI 可能生成的非标准缩进。
- **严守项 (Strict)**：
    - **资产 ID (`id`)**：必须存在，且必须符合当前章节的命名空间前缀（如 `s1-`）。
    - **容器类型**：明确区分 `visual` 与 `script`，不允许混淆。
    - **JSON 合法性**：最终提取的内容必须能解析为合法的 JSON 对象。
    - **闭合要求**：每一个块必须有明确的结束标记 `:::`。

### 2.3 逻辑同步 (Orchestration Sync)
- 确保 `src/core/validators.py` 中的校验逻辑与 `AssetFulfillmentAgent` 中的解析提取逻辑在算法层面保持 100% 一致。

## 3. Acceptance Criteria

### 3.1 鲁棒性验证 (Robustness Tests)
- **极端排版测试**：构造包含混乱缩进、大量空行、特殊字符转义的多行 `:::visual` 块，校验器必须能正确通过。
- **故障现场重现**：使用之前导致系统崩溃的“多行美化 JSON”文本进行测试，必须不再报错。

### 3.2 规范性验证 (Compliance Tests)
- **ID 偏移测试**：若 `id` 不包含命名空间前缀或 `id` 缺失，校验器必须能准确识别并报错。
- **非法 JSON 测试**：若块内包含无法解析的 JSON 片段，校验器必须报错并提供清晰的错误位置。

### 3.3 端到端一致性
- 经过校验器认定的“合法”文本，必须能被 `AssetFulfillmentAgent` 成功解析并执行资产履约，中间不产生任何解析错误。

## 4. Out of Scope
- 修改 `:::visual` 或 `:::script` 的基础语法定义。
- 更改现有的资产 ID 命名规则或命名空间分配逻辑。
