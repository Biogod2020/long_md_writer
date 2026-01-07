# 🧬 Magnum Opus HTML Agent - SOTA 2.0 全量工程手册

## 📖 系统定位
Magnum Opus 2.0 是一套**意图驱动的专业级 AI 出版引擎**。它通过“全量上下文感知”与“分层语义叠流”技术，将用户意图精准转化为具备工业级审美、高度交互性且逻辑严密的 HTML5 产物。

---

## 🏗️ 核心架构与 SSOT 契约 (Single Source of Truth)

系统运行依赖于四套核心“契约”，确保 Agent 协作的绝对同步与逻辑闭环：

### 1. 统一资产注册表 (Universal Asset Registry, UAR)
*   **角色**：系统的“视觉大脑”。
*   **标准**：记录资产的 ID、物理路径、语义标签、**裁切参数 (`crop_metadata`)** 及复用标记。
*   **逻辑**：支持“即产即存”，写手可通过查表实现跨章节资产复用，杜绝重复搜图。

### 2. 全量上下文感知 (Full-Context Perception)
*   **准则**：在创作任何章节时，写手节点强制输入 **[全量大纲 + 提炼意图 + 全量原材料 + 全量原始图像 Part + 实时 UAR + 历史章节文本]**。
*   **价值**：这是消除 AI 幻觉、确保全书术语一致性的物理级护栏。

### 3. 项目快照与实验 Profile (Project Lifecycle)
*   **存储结构**：每次运行的环境（Prompt 快照、Raw 数据版本、UAR 状态）均序列化为本地 Profile。
*   **实验复现**：支持通过 `--profile <id>` 一键回溯环境，实现“控制变量”的局部重写实验。

### 4. 广义行动协议 (Action Protocol)
*   **契约形式**：使用 `data-controller` 属性取代随机 ID。
*   **覆盖范围**：涵盖从图片动画到全局 UI 联动（弹出解释、多媒体同步、状态切换）的所有交互。

---

## 🤖 意图驱动的五层创作流

系统将创作压力解耦为五个专业阶段，所有决策均在 Markdown 语义层完成：

### 🟢 阶段 1：规划与地基 (Phase A)
*   **核心节点**：Architect, TechSpec, AssetIndexer。
*   **关键任务**：用户资产语义贴标、章节 Namespace 隔离前缀注入、全局组件白名单确定。

### 🔵 阶段 2：全量深度创作 (Phase B - Layer 1)
*   **核心节点**：SME Writer (多模态感知型写手)。
*   **直出协议**：若发现 UAR 已有素材，**直接写出 `<img style="...">` 裁切标签**；否则进行意图打桩。

### 🟡 阶段 3：脚本标注与增强 (Phase B - Layer 2)
*   **核心节点**：Script Decorator。
*   **关键任务**：针对 MD 元素叠加 `:::script` 指令，注入 GSAP 动画协议或广义交互钩子。

### 🟠 阶段 4：资产先行闭环 (Phase D - Shift-Left)
*   **核心节点**：Asset Fulfillment, Asset Critic。
*   **关键逻辑**：在 HTML 转换前，完成 SVG 生成、图片采购及**资产级 VQA**（验证裁切坐标是否准确对准描述焦点）。

### 🔴 阶段 5：全量语义综审 (Phase E - Gatekeeper)
*   **核心节点**：Editorial QA (总编辑)。
*   **职责**：进行最终的图文校对与逻辑对齐审计，审计通过后提炼 `GhostBuffer` 骨架。

---

## 🛠️ 技术实现细节

### 1. 本地静态安检 (Static Analysis)
*   **Markdown 指令校验**：正则验证 `:::` 容器闭合性及 JSON 配置语法。
*   **LaTeX 平衡检查**：本地校验 `$` 符号配对，防止数学公式导致渲染崩溃。
*   **嵌入式 HTML 核验**：严格检查写手生成的 `<img>` 标签及 CSS 裁切数值合法性。

### 2. 图像采购与智能定位
*   **文本解耦**：采购 Agent 仅凭 `:::visual` 意图描述进行搜索，不再依赖 HTML 上下文。
*   **Focus Locator**：利用视觉 API 分析下载图，自动计算重点区域的坐标重心并回写 UAR。

### 3. 严格 HTML 校验
*   **编译器级报错**：使用 `lxml` 严格模式（`recover=False`）捕获标签未闭合或非法嵌套错误。
*   **样式契约对齐**：本地核验最终类名是否与 `style_mapping.json` 100% 对齐。

---

## 🚦 实验与开发指南

### 目录结构标准
*   `src/core/validators.py`: 本地静态分析逻辑。
*   `src/assets/schemas/`: 组件与指令的硬约束 Schema。
*   `workspace/<job_id>/profile/`: 本次实验的配置与提示词快照。

### 启动实验
*   **初次运行**：`python main.py --input <raw_dir>`
*   **复用 Profile**：`python main.py --profile <job_id>` (直接进入局部调整模式)

### 调试规范
1.  **资产问题**：检查 `UAR (assets.json)` 中的 `crop_metadata`。
2.  **交互问题**：检查 HTML 中的 `data-controller` 是否匹配 `components.json`。
3.  **逻辑问题**：检查 `GhostBuffer` 提取的快照是否覆盖了核心结论。