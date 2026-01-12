# 🧬 Magnum Opus: SOTA 2.0 语义创作流水线 (Markdown Flow)

这是 Magnum Opus 系统最核心的语义大脑，负责从原始灵感到高质量、结构化内容的转化。系统通过五个高度专业化的阶段 (Phase 0-4) 运行。

[← 返回主索引](../README_CN.md) | [前往 HTML 转换流水线 →](README_HTML_CN.md)

---

## 🏗️ 核心架构：分阶段详细深度视图

我们采用了 **“左侧数据/资产 (Data) - 右侧执行流 (Workflow)”** 的分块设计，确保数据驱动的逻辑清晰透明。

### 🟢 Phase 0: 资产索引评估 (Asset Indexing)
**核心逻辑**：在开始协作前，先让 AI “看一眼”你提供了哪些素材，并进行语义贴标。

```mermaid
flowchart LR
    %% 样式
    classDef data fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#15803d
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px,color:#7c3aed

    subgraph Data ["📂 资产与输入"]
        direction TB
        D1[("📷 原始素材<br/>(images/ + docs/)")]
    end

    subgraph Workflow ["🔄 索引流程"]
        direction TB
        A1["🔍 AssetIndexer Agent<br/>(VLM 扫描与贴标)"]
        W1{"索引决策"}
        W1 -->|"通过"| O1[("📦 UAR 注册表<br/>(assets.json)")]
        W1 -->|"质量低"| O2[("⚠️ 质量警告")]
    end

    D1 -.-> A1
    A1 --> W1
    
    class D1,O1,O2 data
    class A1 agent
```

---

### 🔵 Phase 1: 需求深度规划 (Planning)
**核心逻辑**：通过 3 轮交互，将模糊的需求变成精确的目录架构。

```mermaid
flowchart LR
    %% 样式
    classDef data fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#15803d
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px,color:#7c3aed
    classDef review fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#92400e

    subgraph Data ["📂 规划数据"]
        direction TB
        D1[("📄 原始需求 & 素材")]
        D2[("💾 澄清回答 (Answers)")]
        D3[("📝 Project Brief (Markdown)")]
        D4[("📋 Manifest (outline.json)")]
    end

    subgraph Workflow ["🔄 规划流程"]
        direction TB
        A1["❓ Clarifier<br/>(生成澄清提问)"]
        A2["📝 Refiner<br/>(合成项目简报)"]
        A3["🏗️ Architect<br/>(设计章节架构)"]
        
        R1{{"🧑‍💻 Brief 审核"}}
        R2{{"🧑‍💻 大纲审核"}}
        
        %% 循环逻辑
        A1 -.-> D2
        D2 --> A2
        A2 --> R1
        R1 -->|"批准 ✅"| D3
        R1 --"修改建议 ↺"--> A2
        
        D3 --> A3
        A3 --> R2
        R2 -->|"批准 ✅"| D4
        R2 --"修改建议 ↺"--> A3
    end

    D1 --> A1
    
    class D1,D2,D3,D4 data
    class A1,A2,A3 agent
    class R1,R2 review
```

---

### 🟡 Phase 2: 技术规格定义 (TechSpec)
**核心逻辑**：在动笔前，确定所有的排版规范和交互规则，作为后续“协作契约”。

```mermaid
flowchart LR
    %% 样式
    classDef data fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#15803d
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px,color:#7c3aed

    subgraph Data ["📂 规格文档"]
        direction TB
        D1[("📝 Project Brief")]
        D2[("📋 Manifest (大纲)")]
        D3[("🔧 SOTA 执行契约 (Contract)")]
    end

    subgraph Workflow ["🔄 规格定义"]
        direction TB
        A1["📋 TechSpec Agent<br/>(跨节点对齐契约生成)"]
    end

    D1 & D2 --> A1
    A1 --> D3
    
    class D1,D2,D3 data
    class A1 agent
```

---

### 🟠 Phase 3: 章节创作与资产闭环 (Creation)
**核心逻辑**：最繁忙的阶段，一边顺序写作，一边动态生成/采购资产并进行审计。

```mermaid
flowchart LR
    %% 样式
    classDef data fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#15803d
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px,color:#7c3aed

    subgraph Data ["📂 创作产物"]
        direction TB
        D1[("📚 完整上下文 (SSOT)")]
        D2[("📝 已写完章节 (sec-*.md)")]
        D3[("🖼️ 履约资产 (SVG/PNG)")]
        D4[("📦 更新后的 UAR")]
    end

    subgraph Workflow ["🔄 顺序创作与履约循环"]
        direction TB
        A1["✍️ Writer Agent<br/>(全量上下文写作)"]
        A2["🎨 Fulfillment Agent<br/>(意图履约/生成)"]
        A3["🔍 AssetCritic Agent<br/>(视觉合规审计)"]
        
        L1{"更多章节?"}
        
        %% 资产循环
        A1 -.->|":::visual 需求"| A2
        A2 --> A3
        A3 --"审核失败 ↺"--> A2
        A3 -->|"审核通过"| D4
        
        %% 章节循环
        A1 --> D2
        D2 --> L1
        L1 -->|"Yes"| A1
    end

    D1 --> A1
    
    class D1,D2,D3,D4 data
    class A1,A2,A3 agent
```

---

### 🔴 Phase 4: 全量语义综审 (QA)
**核心逻辑**：最后把关，修正数学公式错误、结构断裂及冗余。

```mermaid
flowchart LR
    %% 样式
    classDef data fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#15803d
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px,color:#7c3aed
    classDef review fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#92400e

    subgraph Data ["📂 最终数据"]
        direction TB
        D1[("📝 待审全量 MD")]
        D2[("👻 GhostBuffer (语义骨架)")]
        D3[("✅ 最终 MD (固化版)")]
    end

    subgraph Workflow ["🔄 综审与修复流程"]
        direction TB
        A1["📰 EditorialQA Agent<br/>(多模态全量联审)"]
        A2["🔬 MarkdownQA Agent<br/>(代码/公式自动修复)"]
        R1{{"🧑‍💻 最终 MD 审核"}}
        
        %% 修复循环
        A1 --> A2
        A2 --> R1
        R1 -->|"批准 ✅"| D3
        R1 --"修改建议 ↺"--> A2
    end

    D1 --> A1
    A1 --> D2
    
    class D1,D2,D3 data
    class A1,A2 agent
    class R1 review
```

---

## 📦 资产状态机：UAR 核心决策链

在 Phase 3 的创作中，资产的状态如何流转：

```mermaid
stateDiagram-v2
    [*] --> REGISTERED: P0 预索引 (USER)
    [*] --> INTENT_STAKE: P3 Writer 打桩 (visual 指令)
    
    REGISTERED --> DIRECT_INJECT: Writer 发现可用资产
    
    INTENT_STAKE --> FULFILLED_AI: Fulfillment (生成 SVG)
    INTENT_STAKE --> FULFILLED_WEB: Fulfillment (Web 采购)
    
    FULFILLED_AI --> PASS: AssetCritic 审计通过
    FULFILLED_AI --> FAIL: 审计未通过 (重试)
    
    PASS --> FINAL_MD: 注入最终文档
    DIRECT_INJECT --> FINAL_MD
```

---

## 🚀 启动命令

```bash
# 执行独立语义生成
python main_markdown.py --input inputs/prompt.txt
```

---

## 🔗 相关手册
- [← 返回主索引](../README_CN.md)
- [前往 HTML 转换流水线 →](README_HTML_CN.md)
