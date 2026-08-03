# Specification: Root Workspace Directory Cleanup & Standardization

## 1. Overview
项目的根目录目前散布着多个以 `workspace` 和 `temp_` 开头的临时目录，导致目录结构混乱。本 Track 旨在通过将这些目录整合到统一的父目录 `workspaces/` 中，并同步更新代码中的路径引用，来规范化项目结构。

## 2. Functional Requirements
- **目录迁移**: 
    - 在项目根目录下创建 `workspaces/` 文件夹。
    - 将以下目录物理移动至 `workspaces/` 下：
        - `workspace/` -> `workspaces/workspace/`
        - `workspace_debug/` -> `workspaces/workspace_debug/`
        - `workspace_test/` -> `workspaces/workspace_test/`
        - `workspace_e2e_parallel/` -> `workspaces/workspace_e2e_parallel/`
    - 将根目录下所有符合 `temp_*` 模式的文件或文件夹移动至 `workspaces/` 下。
- **路径重构**:
    - 遍历 `src/` 和 `scripts/` 目录下的所有源文件。
    - 识别并替换硬编码的路径字符串（如 `"workspace/"` 替换为 `"workspaces/workspace/"`），确保现有逻辑（包括测试脚本、核心编排逻辑）在迁移后仍能正常运行。

## 3. Non-Functional Requirements
- **向后兼容性**: 通过自动重构确保核心脚本的功能不受路径变更影响。
- **原子性**: 确保目录移动与代码更新同步完成，避免中间状态导致脚本崩溃。

## 4. Acceptance Criteria
- [ ] 根目录下不再直接存在多个 `workspace*` 文件夹。
- [ ] 所有原有的工作区数据完整保留在 `workspaces/` 目录下。
- [ ] 运行核心测试（如 `pytest`）或主要脚本（如 `main.py`）时，不会因找不到目录而报错。
- [ ] 根目录下的 `temp_` 文件被成功清理。

## 5. Out of Scope
- 删除任何现有的工作区数据。
- 自动化清理 `data/` 或 `assets/` 目录下的内容。
