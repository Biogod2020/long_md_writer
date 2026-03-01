# Specification: API 架构归一化 - 迁移至 geminicli2api-async (8888 端口)

## 1. Overview
本 Track 旨在将系统的主 API 端口从 AIClient-2-API (3000 端口) 物理切换至 `geminicli2api-async` (8888 端口)。核心目标是实现“架构减负”，移除之前为了适配 3000 端口而引入的各种复杂重试、轮询及 Context 管理逻辑，回归到原生 Gemini 协议的高效、稳定调用。

## 2. Functional Requirements

### 2.1 API 端口切换 (Core Migration)
*   **全局基地址变更**：将 `GeminiClient` 的默认 `api_base_url` 从 `http://localhost:3000` 修改为 `http://localhost:8888`。
*   **全系统接入**：确保 Architect, Writer, QA, Fulfillment 等所有 Agent 节点均无缝对接 8888 端口。

### 2.2 逻辑“瘦身”与归档 (Logic Archival & Simplification)
*   **移除复杂微调**：清理 `GeminiClient` 中针对旧代理实现的 `x-skip-context`、全局 index 强制重置、特殊的 429 `Stay & Wait` 等“花哨”逻辑。
*   **代码解耦**：将这些为了兼容性而存在的逻辑物理剥离，并归档至 Track 目录下的 `archive/` 文件夹中，作为历史参考。
*   **回归标准协议**：利用 `geminicli2api-async` 原生支持的异步特性，简化请求拦截与响应解析流程。

### 2.3 8888 端口深度适配
*   **功能调研**：通过 `ls+cat` 查看 `../geminicli2api-async` 源码，确认其对 `generateContent` 和 `streamGenerateContent` 的具体实现细节。
*   **调试与优化**：针对 8888 端口进行压力测试，确保其在 SOTA 2.1 高并发履约场景下的表现优于旧代理。

## 3. Acceptance Criteria
*   **连接性**：100% 请求成功路由至 8888 端口。
*   **稳定性**：在高并发（3+ 并发）场景下，不再出现 `stale request context` 警告（因为不再依赖 3000 端口的 context 管理）。
*   **代码质量**：`GeminiClient` 源码复杂度显著降低，冗余逻辑被清除。

## 4. Out of Scope
*   修改 `../geminicli2api-async` 本身的源代码（仅进行外部调研与接入）。
*   调整 Agent 的业务逻辑（Prompt 等）。
