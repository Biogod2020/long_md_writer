# 🧬 Magnum Opus SOTA 升级：Markdown 创作与实验管理篇 (MTODO_CN)

本规划专注于 **Markdown 语义层** 的意图履约与**全生命周期实验管理**。核心目标是构建一个能够精准理解用户意图、高度健壮且支持快速实验复现的工业级生产流水线。

---

## 📚 核心术语与工程标准 (名词解释)

1.  **UAR (Universal Asset Registry)**：统一资产注册表。它是系统的“视觉大脑”，不仅记录物理路径，还存储资产的**意图描述、版权归属、裁切元数据及全局唯一指纹**。它允许 Agent 通过“语义匹配”实现跨章节资产复用。
2.  **Full-Context Perception (全量上下文感知)**：系统级健壮性要求。创作任何章节时，Agent 必须输入：**完整架构蓝图 (Manifest) + 提炼后的用户意图 (Brief) + 全量原材料 (Raw Materials) + 原始参考图 (Vision Part) + 实时资产注册表 + 已完成章节文本**。
3.  **Writer-Direct-Inject (写手直出协议)**：赋予写手资产处理的最高优先权。若发现已有资产符合意图，**直接生成带 `style` 裁切属性的 `<img ...>` 标签**，在创作瞬间锁定“视觉焦点”。
4.  **Action Protocol (广义行动协议)**：通过 `:::script` 注入 `data-controller`。它将交互逻辑从简单的“图片特效”扩展到**全局 UI 联动、多媒体同步、状态机切换**等广义交互场景。
5.  **Project Snapshot (项目快照/Profile)**：将运行时的所有 Prompts、Raw 数据、资产配置序列化为本地 Profile。它是实现“一键复现实验”和“局部重写”的核心。

---

## 🏁 Phase A: 架构重塑与底层契约 (地基工程)
*目标：建立严谨的数据结构、多模态注入底座与本地校验安检站。*

### 1. 核心模型重构 (`src/core/types.py`)
- [ ] **完善 `AssetEntry` Pydantic 模型**:
    - `id`: 携带 Namespace 的唯一标识。
    - `source`: `USER` (本地输入) | `AI` (SVG生成) | `WEB` (搜索获取)。
    - `semantic_label`: 视觉内容描述，用于 Agent 进行意图匹配。
    - **[重点]** `crop_metadata`: 存储 `{left: %, top: %, zoom: f}` 等百分比坐标，支持 CSS `object-position`。
    - `reuse_policy`: `ALWAYS` | `ONCE` | `NEVER`。
- [ ] **定义 `UniversalAssetRegistry` (UAR) 管理类**:
    - 实现 `register_immediate(entry)`：产出即持久化，立即写入 `assets.json`。
    - 实现 `intent_match(query)`：支持写手在创作时查询“库里是否有符合我当前描述的图”。
- [ ] **升级 `AgentState` 全量上下文挂载**:
    - 实现全量数据的内存视图，确保大规模上下文（Text + Vision）在 Agent 节点间无损流转。

### 2. 本地静态校验器开发 (`src/core/validators.py`)
- [ ] **实现 `MarkdownStuctureValidator`**:
    - **指令检查**：利用正则 `r"^:::\w+"` 确保容器块正确闭合。
    - **配置校验**：使用 `json.loads()` 核验指令首行的 `{json}` 语法，拦截因模型幻觉导致的引号、逗号错误。
- [ ] **实现 `EmbeddedHTMLValidator` (高优先级)**:
    - **标签解析**：扫描文本中的 `<img ...>`，确保其完全符合 HTML5 语法规范。
    - **样式核验**：确保 `style` 中的裁切参数（如 `object-position`）数值合法且带有单位。
- [ ] **实现 `LaTeXBalanceValidator`**: 本地检查数学公式符号平衡，防止前端渲染引擎崩溃。

### 3. 系统级自动化工具
- [ ] **开发 `NamespaceManager`**: Python 逻辑，根据大纲顺序自动为章节注入 Namespace 前缀（如 `s1-`, `s2-`），杜绝 ID 冲突。
- [ ] **开发 `AssetIndexerAgent` (Phase 0)**:
    - 职责：扫描 `inputs/` 目录，利用视觉 API 对用户提供的参考素材进行预贴标（Tagging）并初始化 UAR。

---

## 🖋️ Phase B: 意图驱动创作与分层交互 (创作核心)
*目标：在全量背景感知下，通过“打桩/直出”逻辑，在 Markdown 层面完成定稿。*

### 1. 阶段 1：全量感知深度创作 (Subject SME Writer)
**文件**: `src/agents/writer_agent.py`
- [ ] **多模态提示词重构 (The All-Seeing Writer)**:
    - **输入控制**：合并 [完整规划 + 提炼后的意图 + 全量文本原材料 + **全量图像素材(Vision Part)** + 实时 UAR + 历史章节]。
    - **核心职责**：在充分理解用户意图和现有原材料的基础上，进行高逻辑密度的文本创作。
- [ ] **资产注入算法 (Fulfillment Logic)**:
    - **分支 A (引用直出)**：若 UAR/参考图中已有素材符合意图 -> **直接写出带裁切样式的 `<img ...>` 标签**，并提供标准 Markdown 图片链接作为备用。
    - **分支 B (意图打桩)**：若库中无匹配 -> 写入 `:::visual {"intent": "详细描述", "focus": "局部焦点"}`，标记为 PENDING 状态供下游履约。
- [ ] **意图延续性检查**: 强制参考前序章节，确保术语统一、叙述逻辑严丝合缝。

### 2. 阶段 2：广义脚本设计与协议编排 (General Scripting)
**文件**: `src/agents/script_decorator_agent.py`
- [ ] **交互能力泛化**:
    - **不仅限于图**：定义段落联动、侧边栏弹出、全局状态切换（如：根据用户选择改变文档难度或主题）。
    - **行动契约注入**：针对 Markdown 元素注入标准的 `:::script {json}` 块。
    - **契约对齐**：强制从 `components.json` 选取合法的 `data-controller` 和参数 Schema。

---

## 💾 Phase C: 实验管理与 Profile 持久化 (管理升级)
*目标：构建“创作实验室”环境，支持配置一键复用与资产本地化浏览。*

### 1. 项目快照与档案系统 (`src/core/persistence.py`)
- [ ] **实现 `ProjectProfile` 系统**: 每次运行自动归档：
    - `prompts_snapshot.json`：记录本次各节点的系统提示词（用于回溯效果）。
    - `input_blueprint.json`：记录原始 Raw 数据的路径、版本和输入参数。
    - `uar_checkpoint.json`：存储当前的资产状态和裁切决策。
- [ ] **实现“Profile 重装载”模式**:
    - 逻辑：通过 `--profile <id>` 启动，系统跳过初始化，直接复用已有的资产匹配结果和规划，允许用户针对特定章节进行“控制变量”实验。

### 2. 资产管理与 interface 接口
- [ ] **开发 `AssetService` 后端接口**: 提供钩子供前端浏览：
    - 资产看板：展示“复用”与“新增”资产的比例。
    - 决策链：追踪该资产是由哪个用户意图驱动产生的。

---

## 🖼️ Phase D: 资产履约与左移 VQA (Shift-Left)
*目标：在 HTML 转换前，单线程顺序完成所有“零件”的物理生产与验证。*

### 1. 资产顺序履约循环 (`src/agents/asset_fulfillment_agent.py`)
- [ ] **补位生产逻辑**:
    - **静默过滤**：**自动跳过** 已被写手直接注入 `<img>` 的部分，仅处理 `:::visual` 块。
    - **采购与生成**：执行搜图（解耦 DOM）或生成 SVG。
- [ ] **智能焦点计算 (VLM-based)**: 对新图执行视觉定位，根据写手的 `focus` 描述，自动计算并注册 `crop_metadata` 的百分比坐标。

### 2. 资产级审计员 (Asset Critic)
- [ ] **视觉匹配审计**: 视觉 Agent 针对生成的资产执行 1:1 内容审计。若失败，立即在 Markdown 阶段触发修复循环，禁止错误资产流向下游。

---

## 🛡️ Phase E: 全量语义与逻辑综审 (The Gatekeeper)
- [ ] **1. 全量多模态终审 (Editorial QA)**:
    - 接收全量文本与资产流，核验写手生成的直出标签 `<img style="...">` 里的裁切范围是否准确击中了文字描述的焦点区域。
- [ ] **2. 语义摘要提取**: 审计通过后，自动更新全局结论快照，为后续项目复用提供基础。

---

## 🕵️ Phase F & G: HTML 转换与组装 (见 HTODO_CN.md)
*(HTODO 将仅关注：多态布局适配、JS 运行状态审计、响应式栅格检查及视觉衔接审计)*