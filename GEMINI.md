# 🧬 Magnum Opus HTML Agent - SOTA 2.0 全量工程手册

## 📖 系统定位
Magnum Opus 2.0 是一套**意图驱动的专业级 AI 出版引擎**。它通过“全量上下文感知”、“分层语义叠流”与“资产先行闭环”技术，将用户意图精准转化为具备工业级审美、高度交互性且逻辑严密的 HTML5 产物。

---

## 🏗️ 核心架构与 SSOT 契约 (Single Source of Truth)

系统运行依赖于五套核心“契约”，确保 Agent 协作的绝对同步与逻辑闭环：

### 1. 统一资产注册表 (Universal Asset Registry, UAR)
*   **角色**：系统的“视觉大脑”。
*   **标准**：记录资产的 ID、物理路径、语义标签、质量等级 (`quality_level`)、**裁切参数 (`crop_metadata`)** 及复用标记。
*   **逻辑**：支持“产出即持久化”，写手通过 UAR 摘要实现跨章节资产复用，杜绝重复采购。

### 2. 全量上下文感知 (Full-Context Perception)
*   **准则**：在创作任何章节时，写手节点强制输入 **[全量大纲 + 提炼意图 (Brief) + 全量原材料 + 实时 UAR + 已完成章节全量文本]**。
*   **价值**：这是消除 AI 幻觉、确保全书术语一致性与逻辑连贯性的物理级护栏。

### 3. 项目快照与实验 Profile (Phase C - Persistence)
*   **存储结构**：每次运行的环境（Prompt 快照、Input Blueprint、UAR Checkpoint）均序列化为本地 Profile。
*   **实验复现**：支持通过 `--profile <id>` 一键回溯环境，实现“控制变量”的局部重写实验与资产决策链追踪。

### 4. 章节命名空间隔离 (Namespace Isolation)
*   **组件**：`NamespaceManager` 自动分配前缀（如 `s1`, `s2`）。
*   **契约**：所有章节内的元素 ID 与资产 ID 强制注入命名空间前缀，防止在最终 Assembler 阶段发生 ID 碰撞。

### 5. 广义行动协议 (Action Protocol)
*   **契约形式**：使用 `data-controller` 属性取代随机 ID，配合 `:::script` 指令。
*   **覆盖范围**：从图片缩放、多图画廊到公式推导步进器，所有交互均通过 `components.json` 定义的 Schema 进行约束。

---

## 🤖 意图驱动的五层创作流

系统将创作压力解耦为五个专业阶段，核心决策在 Markdown 语义层闭环：

### 🟢 阶段 1：规划与地基 (Phase A)
*   **核心节点**：Architect, TechSpec, AssetIndexer。
*   **关键任务**：用户资产语义贴标与质量初评、章节 Namespace 注入、SOTA 执行契约 (TechSpec) 生成。

### 🔵 阶段 2：全量深度创作 (Phase B - Layer 1)
*   **核心节点**：SME Writer (多模态感知型写手)。
*   **Direct-Inject 协议**：若 UAR 已有高质量素材，**直接注入 `<img>` 裁切标签**；否则进行 `:::visual` 意图打桩。

### 🟡 阶段 3：脚本标注与增强 (Phase B - Layer 2)
*   **核心节点**：Script Decorator。
*   **关键任务**：分析 Markdown 语义特征，针对性叠加 `:::script` 指令，注入交互控制器钩子。

### 🟠 阶段 4：资产先行闭环 (Phase D - Shift-Left)
*   **核心节点**：Asset Fulfillment, Asset Critic。
*   **关键逻辑**：在 HTML 转换前完成 SVG 生成、图片采购及**资产级 VQA**（验证 AI 产出是否符合描述意图）。

### 🔴 阶段 5：全量语义综审 (Phase E - Gatekeeper)
*   **核心节点**：Editorial QA (总编辑)。
*   **职责**：执行全量多模态终审，校验裁切范围是否命中文字焦点，审计通过后提炼 `GhostBuffer` 语义骨架。

---

## 🛠️ 技术实现细节

### 1. 四重本地静态安检 (Static Analysis)
*   **MarkdownStructureValidator**：正则验证 `:::` 容器闭合性及 JSON 配置语法。
*   **EmbeddedHTMLValidator**：严格核验写手生成的 `<img>` 标签及 CSS 裁切数值合法性。
*   **LaTeXBalanceValidator**：本地校验 `$` 符号配对，防止数学公式导致渲染崩溃。
*   **NamespaceValidator**：确保所有生成的 ID 严格遵循章节前缀契约。

### 2. 智能焦点计算与图像采购
*   **Focus Locator**：利用视觉 API 分析下载图，自动计算重点区域的坐标重心并回写 UAR 的 `crop_metadata`。
*   **多层级采购**：`ImageSourcingAgent` 采用“策略生成 -> 并行搜索 -> VLM 筛选”的三段式架构。

### 3. 双流水线编排 (Dual-Pipeline)
*   **Markdown Pipeline**：侧重内容逻辑与资产履约（`workflow_markdown.py`）。
*   **HTML Pipeline**：侧重 SOTA 设计系统注入与视觉 Bug 修复（`workflow_html.py`）。

---

## 🚦 实验与开发指南

### 目录结构标准
*   `src/core/persistence.py`: 实验快照与 Profile 持久化。
*   `src/core/tools/namespace_manager.py`: 命名空间自动化管理。
*   `src/agents/writer_agent.py`: 实现 `Writer-Direct-Inject` 协议。

### 启动实验
*   **语义创作**：`python tests/run_sota2_workflow.py`
*   **视觉修复**：`python scripts/test_visual_qa.py`

### 调试规范
1.  **资产偏离**：检查 `UAR (assets.json)` 中的 `quality_level` 和 `quality_notes`。
2.  **交互失效**：检查 Markdown 末尾注入的 `:::script` 块是否通过了 `validate_all_scripts`。
3.  **持久化异常**：检查 `workspace/<job_id>/profile/input_blueprint.json` 中的内容哈希。
