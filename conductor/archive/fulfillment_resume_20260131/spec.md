# Specification: SOTA 2.0 Transactional Incremental Fulfillment

## 1. 概述 (Overview)
旨在解决资产履约过程中由于崩溃或超时导致的进度丢失问题。通过引入“工作副本（Working Copy）”机制和“物理资产检测”，实现任务级的断点续传和非破坏性回写。

## 2. 功能需求 (Functional Requirements)
*   **[FR1] 资产存在性幂等**：在启动 AI 任务前，先扫描 `agent_generated` 或 `agent_sourced`。若对应 ID 的物理文件已存在，则直接标记为 `Skipped` 并进入回写阶段，不再调用 API。
*   **[FR2] 增量工作副本**：针对每个待处理的 `.md` 文件，创建一个 `.working` 临时文件。所有实时的替换操作（Injection）均在 `.working` 文件上进行。
*   **[FR3] 事务级原子覆盖**：
    *   履约期间，`.working` 文件随进度实时保存。
    *   仅在 `AssetFulfillmentAgent` 确认该文件的所有指令处理完毕后，才将 `.working` 文件重命名为原文件名。
*   **[FR4] 自动恢复逻辑**：系统启动时，优先读取 `.working` 文件。若存在，则基于该副本的当前内容（已注入部分图片）继续寻找剩余的 `:::visual` 指令。

## 3. 非功能需求 (Non-Functional Requirements)
*   **安全性**：无论何时中断，原始 `.md` 文件在任务 100% 完成前不会被修改。
*   **性能**：利用物理文件检测，使得重试/继续操作的启动时间缩短 90% 以上。

## 4. 验收标准 (Acceptance Criteria)
1.  **断点验证**：处理 10 张图片，在第 5 张时手动中断。检查磁盘，应存在一个已注入 5 张图片的 `.working` 文件。
2.  **继续验证**：重新运行，前 5 张图片应显示 `Skipped`，系统从第 6 张开始处理。
3.  **最终闭环**：任务结束后，`.working` 文件消失，原始 `.md` 文件已被完整更新。
