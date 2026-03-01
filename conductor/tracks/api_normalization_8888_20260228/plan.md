# Implementation Plan: API 架构归一化 - 迁移至 geminicli2api-async (8888 端口)

## Phase 1: 调研与接口验证 (Research & Discovery)
**目标**：通过对 `../geminicli2api-async` 的物理审计，确认其支持的协议细节。

- [ ] **Task: 源码审计**
    - [ ] 使用 `ls -R ../geminicli2api-async` 和 `cat` 查看核心运行文件。
    - [ ] 确认其 `/v1beta/models/...` 路径的实现是否完全符合 Google Native 规范。
- [ ] **Task: 物理连接测试**
    - [ ] 使用 `curl` 对 8888 端口进行 `generateContent`（Unary）和 `streamGenerateContent`（Stream）测试。
- [ ] **Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)**

## Phase 2: 逻辑剥离与归档 (Logic Archival)
**目标**：将针对 3000 端口的复杂适配逻辑移动至存档区。

- [ ] **Task: 识别并提取旧逻辑**
    - [ ] 在 `src/core/gemini_client.py` 中定位 `x-skip-context` 注入逻辑。
    - [ ] 定位 `Rotate-First` 与账号池物理补丁逻辑。
- [ ] **Task: 物理归档**
    - [ ] 将上述逻辑的代码片段及设计意图保存至 `conductor/tracks/api_normalization_8888_20260228/archive/legacy_proxy_tweaks.md`。
- [ ] **Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)**

## Phase 3: 全局切换与代码归一化 (Migration & Cleanup)
**目标**：物理修改基地址，并清理 `GeminiClient` 源码。

- [ ] **Task: 基地址修改**
    - [ ] 修改 `src/core/config.py` 或 `GeminiClient` 构造函数，将默认端口改为 8888。
- [ ] **Task: 源码精简**
    - [ ] 移除 `GeminiClient` 中的冗余参数（如不再需要的 `extra_headers` 处理等，如果新端口不再需要）。
    - [ ] 确保 `prefer_first_provider` 逻辑回归简单轮询或直接由新端口处理。
- [ ] **Task: 单元测试验证**
    - [ ] 运行 `tests/test_aiclient_migration.py`（如果存在或新建）验证连接性。
- [ ] **Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)**

## Phase 4: 全量压力测试 (Validation)
**目标**：验证在 8888 端口加持下，SOTA 2.1 流水线的性能表现。

- [ ] **Task: v18 E2E 压力测试**
    - [ ] 运行 `tests/verification_v18.py`。
    - [ ] 观察日志，验证是否存在泄露或死锁。
- [ ] **Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)**
