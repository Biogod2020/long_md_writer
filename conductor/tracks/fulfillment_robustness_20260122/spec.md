# Specification: Parallel Fulfillment Robustness & VLM Local Search

## 1. 概述
修复并行履约中的技术崩溃，实现非破坏性文件回写，并恢复基于 VLM 的本地资产语义匹配逻辑。

## 2. 功能需求
- **非破坏性物理回写**: 
    - 履约失败时，`apply_fulfillment_to_file` 必须保留原始 `:::visual` 块。
    - 错误信息记录在 `AgentState.failed_directives` 中，供最后统一审计展示。
- **VLM 驱动的本地搜索 (恢复原有方案)**:
    - 补全 `UniversalAssetRegistry.intent_match_candidates` 方法。
    - 实现逻辑：利用 VLM (Gemini Flash) 对本地资产池进行第一层粗筛，返回最相关的候选者供后续打分。
- **稳定性修复**:
    - 修复 `AttributeError: 'UniversalAssetRegistry' object has no attribute 'intent_match_candidates'` 崩溃。
    - 在并行 worker 中捕获详细异常堆栈，并准确回写至 `trace.json`，确保 `None` 被真实错误替换。

## 3. 验收标准
- 失败章节内容不丢失、不重复（即 `:::visual` 块在失败时保持原样）。
- 系统能正确调用 VLM 识别本地已有资产（USE_EXISTING 命中率提升）。
- 最终生成的审计报告包含清晰的失败根因和前后文预览。
