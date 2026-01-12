# 🧬 Magnum Opus HTML Agent

一个企业级的多 Agent AI 系统，旨在自主生产 **State-of-the-Art (SOTA)** 级别的技术文档、学术教科书和交互式讲义。Magnum Opus 通过集成递归视觉验证、深度结构规划和专用设计系统，弥合了原始 LLM 文本生成与专业出版标准之间的鸿沟。

---

## 🏗️ 核心工作流

系统将复杂的生产压力解耦为两个主要的专业流水线：

### 1. [📝 语义生成流水线 (Markdown Pipeline)](README_MARKDOWN_CN.md)
**端到端语义创作：Phase 0 → 2**
- **Phase 0: 资产索引**：AssetIndexer (VLM 语义贴标)。
- **Phase 1: 需求规划**：Clarifier, Refiner & Architect (包含人工审核循环)。
- **Phase 2: 内容生产**：Writer (全量上下文感知), Fulfillment & AssetCritic (资产闭环)。

### 2. [🎨 视觉转换流水线 (HTML Pipeline)](README_HTML_CN.md)
**视觉工程与验收：Phase 3 → 4**
- **Phase 3: 视觉设计与转换**：Design Tokens, Transformer & Assembler。
- **Phase 4: 视觉质检与修复**：Visual QA (VLM Critic & Code Fixer 闭环)。

---

## 🏗️ 全景逻辑工作流 (Full Operational Workflow)

```mermaid
flowchart TD
    %% 样式定义
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px
    classDef artifact fill:#f0fdf4,stroke:#16a34a,stroke-width:1px
    classDef decision fill:#fff7ed,stroke:#ea580c,stroke-width:2px
    classDef loop_edge stroke:#dc2626,stroke-width:2px,stroke-dasharray: 5 5

    %% ========== Phase 0: 资产索引 ==========
    S1([🏁 开始]) --> Indexer[资产索引: VLM 贴标]
    Indexer --> Clarifier{澄清者 Agent}
    
    %% ========== Phase 1: 需求规划 ==========
    Clarifier -->|"3-5 个问题"| UserBrief[👤 用户回答]
    UserBrief --> Refiner[精炼者: Project Brief]
    Refiner --> Architect[架构师: Manifest/Outline]
    
    Architect --> OutlineReview{"⚖️ 流程审批"}:::decision
    OutlineReview --"重写"--> Architect
    OutlineReview --"通过"--> TechSpec[技术规格]

    %% ========== Phase 2: 内容与资产循环 ==========
    subgraph Phase2 ["Phase 2: 内容与资产闭环"]
        Writer[SME 写手: 生成 MD]
        Writer --> Fulfillment[资产履约: SVG/Web 采购]
        Fulfillment --> Critic{资产审计员}
        Critic --"修复"--> Fulfillment
        Critic --"完成"--> Editorial[总编辑: 语义综审]
    end

    TechSpec --> Writer

    %% ========== Phase 3: 视觉转换 ==========
    subgraph Phase3 ["Phase 3: 视觉转换"]
        Tokens[设计令牌: design_tokens.json]
        Tokens --> StyleEng[样式引擎: CSS/JS 生成]
        StyleEng --> Transformer[编译转换: MD -> HTML]
        Transformer --> Assembler[装配者: 注入拼装]
    end

    Editorial --> Tokens

    %% ========== Phase 4: 视觉验收循环 ==========
    subgraph Phase4 ["Phase 4: 视觉验收循环"]
        VQA{视觉批评家: VLM 巡检}
        VQA --"发现 Bug"--> VFixer[代码修复者: Surgical Patch]
        VFixer --> Assembler
    end

    VQA --"视觉完美"--> Deployment([🚀 部署就绪 SOTA 文档])

    %% 循环样式应用
    linkStyle 10,13,17,21 stroke:#dc2626,stroke-width:2px,stroke-dasharray: 5 5;
```

---

## 🚦 快速开始

### 1. 环境搭建
```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium
```

### 2. 启动方式
- **全量流水线 (End-to-End)**: `python main.py --input "需求文件.md"`
- **语义生成流 (SOTA 2.0)**: `python main_markdown.py --input "需求文件.md"`
- **GUI 交互界面**: `streamlit run app.py` (强烈推荐，支持人工审核断点)

---

## 📂 项目结构
```text
.
├── src/
│   ├── agents/          # 专业 AI Agent 节点 (Writer, Critic, VQA 等)
│   ├── core/            # 核心通信、类型定义与持久化 (UAR, Profile)
│   └── orchestration/   # LangGraph 流程定义 (Markdown 流 vs HTML 流)
├── docs/                # 详细技术手册
├── main.py              # 全量流水线入口
├── main_markdown.py     # 语义流独立入口
└── app.py               # Streamlit 仪表盘
```

## 📄 许可证
内部 SOTA 开发项目。保留所有权利。
