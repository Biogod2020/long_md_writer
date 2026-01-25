# Specification: Resilient Asset Path Resolution

## 1. 概述 (Overview)
重构 `AssetEntry.to_img_tag` 的路径计算逻辑，解决当前工作流中 Markdown/HTML 图片路径因目录层级深浅不一而频繁失效的问题。

## 2. 功能需求 (Functional Requirements)
- **智能根目录探测**: 实现一个工具函数，通过向上查找特征文件（如 `.git` 或 `manifest.json`）来动态确定 `PROJECT_ROOT`。
- **动态相对路径计算**:
    - 在生成 `src` 属性时，先获取资产的绝对物理路径。
    - 结合当前正在写入的目标 Markdown 文件的绝对路径，计算两者之间的**最短相对路径**。
- **物理存在性校验 (Strict Mode)**:
    - 在回写标签前，检查目标路径下是否真的存在该文件。
    - 若缺失，则生成包含警告信息的 HTML 注释或特定的“Missing Asset”占位标签。
- **跨区支持**: 能够正确处理位于 `workspace/job_id/` 内部的生成资产，以及位于 `data/global_asset_lib/` 或项目根目录 `assets/` 下的复用资产。

## 3. 验收标准 (Acceptance Criteria)
- 在任何层级的 Markdown 文件（如 `md/sec-01.md`）中生成的图片链接，在本地预览或浏览器渲染时都能 100% 正确显示。
- 如果删除某张已索引的图片，再次运行履约时，Markdown 文稿中应出现显眼的错误占位符。
