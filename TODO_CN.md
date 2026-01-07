# 🧬 Magnum Opus SOTA 升级：实战路线图 (TODO_CN) - 工程师精细版

本路线图采用**单线程顺序执行**，旨在通过极致的工程细节（契约化、资产化、分层化、本地校验）确保产出达到工业级 SOTA 水准。

---

## 📚 核心术语与工程标准 (名词解释)

1.  **UAR (Universal Asset Registry)**：全局资产注册表。一个跨 Agent 的“单一事实来源（SSOT）”，存储所有资产的唯一 ID、本地物理路径、内容语义描述（Semantic Label）及 VQA 质检状态。它让 Agent 能够“查表后决策”，彻底解决素材重复生成的痛点。
2.  **GhostBuffer (语义骨架)**：一种增量上下文同步机制。在生成第 N 章时，不再传输 1...(N-1) 章的全量文本（节省 Token），而是只传输包含**核心推导结论、已定义的数学符号表、已占用的 ID 锚点索引**的轻量级骨架，确保逻辑不漂移。
3.  **Shift-Left (左移质检策略)**：将资产（SVG/图片）的生产与内容审计提前到 Markdown 阶段。在 HTML 转换前，必须确保资产已在注册表中通过视觉审计（Asset VQA），从而将布局与内容逻辑解耦。
4.  **Action Protocol (行动契约)**：使用 `data-controller` 属性取代传统的随机 ID 模式。这是一套声明式协议，让生成的 JavaScript 脚本通过“功能标识”精准捕获 HTML 元素，确保交互逻辑在内容修改后依然稳健。
5.  **Static Analysis (本地静态分析)**：指无需调用 API、仅靠 Python 本地代码执行的快速检查（如正则匹配、JSON 解析、HTML 树遍历）。

---

## 🏁 Phase A: 架构重塑与协议基石 (地基工程)
*目标：建立严谨的数据结构、自动化工具与本地校验护栏。*

### 1. 核心数据结构升级 (Core Data Models)
**文件**: `src/core/types.py`

- [ ] **定义 `AssetEntry` 模型**:
    - 字段: `id` (str), `source` (Enum: USER/AI/WEB), `local_path` (Optional[str]), `semantic_label` (str), `vqa_status` (Enum: PENDING/PASS/FAIL), `usage_count` (int)。
- [ ] **定义 `UniversalAssetRegistry` (UAR) 容器**:
    - 字段: `assets` (Dict[str, AssetEntry])。
    - 方法: `get_asset(id)`, `register_asset(entry)`, `to_json()`, `from_json()`。
- [ ] **定义 `GhostBuffer` 结构**:
    - 字段: `claims` (List[str] - 核心结论), `symbols` (Dict[str, str] - 符号表), `anchors` (List[str] - 已占 ID)。
- [ ] **扩展 `SectionInfo`**:
    - 新增字段: `namespace` (str - 如 "s1"), `status` (Enum: DRAFT/LINTED/AUDITED/RENDERED)。
- [ ] **扩展 `AgentState`**:
    - 新增字段: `asset_registry` (UniversalAssetRegistry), `ghost_buffer` (GhostBuffer)。

### 2. 协议与 Schema 定义 (Protocol Schemas)
**目录**: `src/assets/schemas/` (需新建)

- [ ] **创建 `src/assets/schemas/directives.json`**:
    - 定义 `:::visual` 和 `:::script` 的 JSON Schema。
    - 规范: `visual` 必须含 `id`, `type`; `script` 必须含 `target`, `action`。
- [ ] **创建 `src/assets/schemas/components.json`**:
    - 定义交互组件白名单（如 `InteractiveChart`, `ImageSlider`）。
    - 规范: 组件名, 必填 `data-props`, 对应的 `data-controller` 名称。

### 3. 本地静态校验器开发 (Local Validators)
**文件**: `src/core/validators.py` (需新建)

- [ ] **实现 `MarkdownDirectiveValidator`**:
    - 功能: 使用正则 (`re`) 扫描 Markdown 内容。
    - 检查 1: `:::` 块是否正确闭合。
    - 检查 2: 提取 `:::{json}` 中的 JSON 字符串，尝试 `json.loads()`，捕获语法错误。
- [ ] **实现 `LaTeXBalanceValidator`**:
    - 功能: 扫描 Markdown，计数 `$` 和 `$$`，确保成对出现（偶数个）。
- [ ] **实现 `NamespaceValidator`**:
    - 功能: 扫描 Markdown 中的 HTML 标签 ID（如 `id="s1-xxx"`）。
    - 检查: 所有 ID 是否以当前章节的 `namespace` 开头。

### 4. 系统级自动化工具 (System Tools)
**目录**: `src/core/tools/` (建议新建)

- [ ] **开发 `NamespaceManager`**:
    - 功能: 接收 `Manifest` 对象。
    - 逻辑: 遍历 `sections`，为 section `i` 分配 `namespace = f"s{i+1}"`。
    - 输出: 更新后的 `Manifest`。
- [ ] **开发 `AssetIndexerAgent` (Phase 0)**:
    - 位置: `src/agents/asset_indexer_agent.py`
    - 功能:
        1. 扫描 `inputs/` 目录下的所有图片文件。
        2. 调用 Vision API 生成语义描述 (`semantic_label`)。
        3. 生成唯一 ID (`u-img-{hash}`)。
        4. 初始化 `AgentState.asset_registry`。

### 5. 架构师 Agent 降噪 (Architect Refactor)
**文件**: `src/agents/architect_agent.py`

- [ ] **重构 System Prompt**:
    - 移除: 关于 ID 分配、具体技术参数（CSS/JS）的指令。
    - 强调: 仅输出逻辑大纲、章节摘要、以及高层的“视觉/交互意图”描述。
    - 目标: 减少 Token 消耗，降低幻觉，让 Architect 专注于“叙事结构”。

---

## 🖋️ Phase B: 分层专业化创作 (语义染色流)
*目标：在 Markdown 层面通过四阶段叠加，实现“关注点分离”，降低单次生成的复杂性。*

- [ ] **[Agent] 阶段 1：纯内容写作 (SME Writer)**:
    - [ ] 只负责深度文本叙述与严密的学术逻辑推导，使用 `[RESERVED: visual intent="..."]` 进行简单位置占位。
- [ ] **[New Agent] 阶段 2：视觉修饰师 (Visual Decorator)**:
    - [ ] 扫描文本占位符，优先匹配 UAR 中既有的用户资产；若未命中，则注入 `:::visual {json}` 搜图或 SVG 生成指令。
- [ ] **[New Agent] 阶段 3：脚本修饰师 (Script Decorator)**:
    - [ ] 针对视觉块叠加 `:::script {json}` 指令，注入动画协议参数（如 GSAP 时间轴）与声明式行动钩子 (`data-controller`)。
- [ ] **[Agent] 阶段 4：综合审计总编 (Editorial QA)**:
    - [ ] **前置环节**：先自动运行 `validators.py` 进行静态快检，若不通过则直接返回给上一层修复。
    - [ ] **核心环节**：升级 `MarkdownQAAgent`：利用 `GhostBuffer` 审计叠加后的全量语义 Markdown 是否出现逻辑冲突、术语不一或重复赘述。

## 🖼️ Phase C: 资产先行闭环 (Shift-Left 核心)
*目标：在 HTML 转换前，单线程完成所有“零件”的物理生产与语义验证。*

- [ ] **[Flow] 资产履约微循环**:
    - [ ] 顺序执行：提取单章 MD 指令 -> 驱动 SVG 生成 Agent / 图片搜索下载 Agent -> 更新 UAR 中的本地物理路径。
- [ ] **[New Agent] 资产级审计员 (Asset Critic)**:
    - [ ] 专门的视觉 Agent 对生成的 SVG 或图片进行内容匹配度审计。若验证不通过，立即在 Markdown 阶段触发修正，禁止错误进入转换层。
- [ ] **[Agent] 转换器 Agent 极致简化**:
    - [ ] `TransformerAgent` 转型为“协议转译器”：仅根据 UAR 路径和 `components.json` 注册表进行标签替换与 `data-attributes` 属性注入。

## 🛡️ Phase D: 稳健的一致性维护 (顺序逻辑)
*目标：确保单线程生成的章节之间逻辑严丝合缝。*

- [ ] **[Core] 骨架滑窗自动提取**:
    - [ ] 开发算法：每章通过 `MdQA` 后，自动扫描 MD 提取核心快照并更新至全局 `GhostBuffer`。
- [ ] **[Logic] 跨章引用与 ID 校验**:
    - [ ] 开发检查器：验证 Markdown 中的内部引用 `[REF:id]` 是否在全局资产表 UAR 或前序骨架中真实存在。

## 🕵️ Phase E: 组装与多模态审计
*目标：在最终组装阶段，检查交互的“生命体征”与跨章视觉“接缝”。*

- [ ] **[Modify] 改进本地 HTML 校验器 (`src/agents/assembler_agent.py`)**:
    - [ ] **严格报错捕获**：将 BeautifulSoup 解析升级为严格模式（使用 `lxml` 且 `recover=False`），提取具体的标签未闭合、非法嵌套等编译器级错误。
    - [ ] **样式契约核验**：本地扫描最终 HTML 中的所有类名，与 `style_mapping.json` 进行对比，标记违约样式。
- [ ] **[New Agent] JS 探测器 (JS Probe)**:
    - [ ] 利用 Playwright MCP 监听渲染过程中的控制台错误（Console Error）与资源加载失败（404）。
    - [ ] 验证交互触发：通过 DOM 状态检测点击/滚动是否真实触发了预期的样式属性变化。
- [ ] **[Agent] 接缝审计员 (Seam Auditor)**:
    - [ ] 扩展视觉 QA：专门采样章节交界处的截图，确保跨章视觉风格（页边距、背景颜色过渡）绝对连贯。

## 📦 Phase F: 生产提炼与分发
- [ ] **[New Agent] 提炼 Agent (Distiller)**:
    - [ ] 负责资产打包优化：单文件内联化、资产指纹化、以及基于 `knowledge_map` 的 SEO 结构化元数据注入。
- [ ] **[UI] 任务进度分层可视化**:
    - [ ] 更新 Streamlit 仪表盘，展示“内容-资产-脚本-审核”的各章节层级进度状态。
