# 🧬 Magnum Opus SOTA 升级：HTML 转换与交互审计篇 (HTODO_CN)

本规划专注于 **HTML 转换、动态交互注水与多维度视觉审计**。核心目标是将已定稿的语义 Markdown 转化为具备工业级审美、多态布局适配且逻辑闭环的交互式 Web 产物。

---

## 📚 本阶段核心工程标准 (名词解释)

1.  **Polymorphic Rendering (多态渲染)**：指同一份 Markdown 源码根据 `format_profile`（如 Slide, Blog, Dashboard）渲染为完全不同的 HTML 结构与 CSS 布局。
2.  **Hydration (交互注水)**：借鉴现代前端架构（如 Astro）。`Transformer` 仅生成静态骨架，`JSGenerator` 生成“注水脚本”，根据 HTML 中的 `data-controller` 钩子动态挂载交互行为（如 D3 图表、动画控制器）。
3.  **Action Protocol (行动契约)**：HTML 侧必须严格执行 `data-controller` 与 `data-action` 属性的注入。这是 JS 与 DOM 绑定的唯一合法路径，严禁使用随机生成的 ID。
4.  **Seam Audit (接缝审计)**：视觉质检的高级阶段。专门审计章节衔接处（Junctions）的视觉连续性，防止由于分章生成导致的背景跳变、页边距不一或叙述断层。
5.  **Interactive VQA (交互式质检)**：利用 `JS Probe Agent` 配合 Playwright 模拟用户点击、滚动，验证交互协议是否真实触发了预期的 DOM 状态变更。

---

## 🏗️ Phase F: 多态转换与样式注水 (执行层)
*目标：将语义指令转译为标准组件，实现“一次标注，多端适配”。*

### 1. 协议转译器深度改造 (`src/agents/transformer_agent.py`)
- [ ] **多态模板感知**:
    - 根据 `Manifest.config.format_profile` 切换基础 HTML 片段结构。
    - **Slide 模式**：强制将 `##` 标题包装为 `<section class="slide-page">`。
    - **Blog 模式**：强制生成符合 SEO 规范的语义标签（`<article>`, `<aside>`）。
- [ ] **指令转译逻辑 (Directive Resolver)**:
    - **:::visual 处理器**：查阅 UAR 注册表。若 `status` 为 `VERIFIED`，则根据 `crop_metadata` 渲染带行内样式的 `<img>`；若为 `svg`，则执行内联注入。
    - **:::script 处理器**：将指令参数转化为标准属性：`<div data-controller="{action}" data-props='{json}'>`。
- [ ] **Zero-JS 兜底模式**:
    - 当 `js_enabled: false` 时，自动将所有交互指令转化为 CSS-only 的回退方案（如：将幻灯片转为垂直长流布局）。

### 2. 样式生成与契约对齐 (`src/agents/css_generator_agent.py`)
- [ ] **三层设计令牌应用**:
    - **Primitive 层**：注入基础色板。
    - **Semantic 层**：将令牌映射为 `--color-bg-primary` 等业务变量。
    - **Component 层**：生成符合 BEM 规范的组件样式。
- [ ] **Layout-Base 自动注入**:
    - 在生成的 CSS 头部，根据 Profile 自动注入重置样式（如 Slide 的 16:9 固定比例容器）。

---

## 🕵️ Phase G: 交互审计与功能探测 (逻辑层)
*目标：利用黑盒测试验证脚本的“生命体征”。*

### 1. 脚本胶水生成 (`src/agents/js_generator_agent.py`)
- [ ] **混合注册制实现**:
    - 逻辑：读取 `src/assets/js_modules/` 下的本地核心库（如 SlideController）。
    - 动作：根据 Markdown 中的 `:::script` 指令，生成实例化胶水代码。
- [ ] **控制器绑定校验**:
    - 确保生成的脚本逻辑能够精准覆盖 HTML 中出现的所有 `data-controller`。

### 2. 开发 JS 探测器 (`src/agents/js_probe_agent.py` - 新建)
- [ ] **Playwright MCP 集成**:
    - 编写自动化剧本：`[加载页面, 模拟滚动, 采样点击, 检查控制台]`。
- [ ] **异常捕获算法**:
    - **Console Monitor**：捕获所有 `Uncaught ReferenceError` 或脚本执行异常。
    - **Network Auditor**：识别 404 图片、未加载的 SVG 资源。
    - **Animation Sniffer**：检测带动画的元素。若触发后 `getComputedStyle` 的属性值（如 `opacity`）在 500ms 内保持恒定，则判定为“死动画”。

---

## 🎨 Phase H: 视觉校验与接缝质检 (审美层)
*目标：检查跨章节的审美一致性。*

### 1. 视觉审计员升级 (`src/agents/visual_qa/critic.py`)
- [ ] **空间坐标精准定位 (Spatial VQA)**:
    - 逻辑：在截图前注入透明坐标网格。要求 Critic 返回 Bug 时必须携带坐标 `(x, y)` 或 ID 标签。
- [ ] **多模态交叉验证**:
    - 结合 `JS Probe` 的日志。若截图显示“图表空白”且日志显示“数据注水失败”，则判定为 Major Bug。

### 2. 接缝审计逻辑 (Seam Auditor)
- [ ] **重叠采样算法**:
    - 动作：对 `sec-N` 的末尾和 `sec-(N+1)` 的开头进行 200px 重叠截图。
    - 检查点：页边距是否对齐？背景颜色是否存在色差？字体大小在切换章节时是否突变？

---

## 📦 Phase I: 提炼、分发与实验总结
*目标：产出可交付的成品，并完成本次实验的完整闭环。*

### 1. 产出物提炼 (`src/agents/distiller_agent.py` - 新建)
- [ ] **资源内联化 (Self-Contained Mode)**:
    - 逻辑：将较小的图片转为 Base64，内联 CSS/JS，生成单文件 HTML，实现“开箱即读”。
- [ ] **资产指纹化**: 对外部引用的资源进行 Hash 重命名，解决浏览器缓存过时问题。
- [ ] **SEO 与 JSON-LD 注入**: 根据 `Manifest` 中的 `knowledge_map` 自动生成结构化 Schema 数据。

### 2. 实验复现与 Profile 闭环 (`src/core/persistence.py`)
- [ ] **最终快照存储**:
    - 自动将生成的 `final.html` 及其完整 Profile（含 UAR 最终状态、VQA 审计通过日志）打包存入 `workspace/<job_id>/final_release/`。
- [ ] **实验对比接口**: 支持加载两个不同 `job_id` 的 Profile，对比在不同 Prompt 下的视觉生成差异。

---

## 💡 工程师执行注意事项
*   **Debug 指南**：若交互失效，先检查 HTML 标签中的 `data-controller` 是否被 `Transformer` 漏掉。
*   **性能优化**：`JS Probe` 在单线程模式下运行时，应尽可能复用同一个 Browser Context，以减少渲染开销。
*   **契约优先**：任何时候 `Transformer` 生成的类名如果不在 `style_mapping.json` 中，必须抛出本地静态错误。
