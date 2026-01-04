# Magnum Opus HTML Agent

一个先进的多阶段 AI Agent 系统，用于生成 SOTA (State-of-the-Art) 级别的技术讲义、学术文档和长篇 HTML 内容，具备卓越的视觉美感和交互组件。

## 🚀 项目概述

Magnum Opus HTML Agent 将复杂的技术写作和设计任务分解为模块化的流水线。它通过“主动澄清”机制消除需求歧义，并生成全局性的“SOTA Description”技术指标，确保后续所有 Agent 节点的输出质量高度一致。

## 🏗️ 系统架构

系统采用多阶段任务分解模式 (ADaPT/LLM Chaining)，通过专用 Agent 协作确保高质量产出。

### 整体工作流

```mermaid
graph LR
    A[原始输入] --> B[澄清者 Agent]
    B -->|提问| C[用户回答]
    C --> D[精炼者 Agent]
    D -->|项目简报| E[大纲 Agent]
    E -->|文档结构| F[技术规范 Agent]
    F -->|SOTA 规范| G[生产流水线]
    
    subgraph "生产流水线"
    G --> H[写手 Agent]
    H --> I[设计组 Agent]
    I --> J[转换器 Agent]
    J --> K[SVG 创作者 Agent]
    K --> L[装配者 Agent]
    end
    
    style K fill:#f9f,stroke:#a855f7,stroke-width:3px
```

### 节点输入/输出详情

下图详细描述了各 Agent 节点之间的数据流向：

```mermaid
graph TD
    classDef agent fill:#f9f,stroke:#333,stroke-width:2px;
    classDef data fill:#bbf,stroke:#333,stroke-width:1px;
    classDef newagent fill:#f9f,stroke:#a855f7,stroke-width:3px;

    subgraph Planning ["规划与对齐阶段"]
        In[原始素材]:::data --> Clarifier[澄清者 Agent]:::agent
        Clarifier --> Q[澄清问题集]:::data
        Q --> Ans[用户回答]:::data
        In & Ans --> Refiner[精炼者 Agent]:::agent
        Refiner --> Brief[项目简报]:::data
        In & Brief --> Outline[大纲 Agent]:::agent
        Outline --> Manifest[Manifest: 文档结构]:::data
        In & Brief & Manifest --> TechSpec[技术规范 Agent]:::agent
        TechSpec --> Spec[SOTA Description: 全局指令]:::data
    end

    subgraph Production ["生产与执行阶段"]
        Brief & Manifest & Spec --> Writer[写手 Agent]:::agent
        Writer --> MD[Markdown 内容]:::data
        Brief & MD & Spec --> Designer[设计组 Agent]:::agent
        Designer --> Assets[CSS/JS/样式映射]:::data
        MD & Assets & Spec & PrevHTML[已完成 HTML] --> Transformer[转换器 Agent]:::agent
        Transformer --> Frags[HTML 片段 + SVG 占位符]:::data
        Frags & Spec & Brief --> SVGCreator[SVG 创作者 Agent]:::newagent
        SVGCreator --> ValidatedHTML[验证后的 HTML]:::data
        ValidatedHTML & Assets --> Assembler[装配者 Agent]:::agent
        Assembler --> Out[最终 HTML]:::data
    end
```

## 🛠️ 核心 Agent 角色

| Agent | 职责 | 核心输出 |
| :--- | :--- | :--- |
| **Clarifier** | 分析输入，提出 3-5 个针对性问题以消除需求模糊性。 | 澄清问题集 |
| **Refiner** | 综合原始素材和用户回答，生成领域无关的详细项目简报。 | 项目简报 |
| **Outline** | 设计高水平的文档结构（章节预览、知识图谱）。 | Manifest (结构) |
| **TechSpec** | 生成详细的技术实现方案（即 "SOTA Description"）。 | 全局技术指令 |
| **Writer** | 基于全量上下文，撰写各章节详尽的 Markdown 内容。 | Markdown 文件 |
| **DesignTeam** | 根据技术规范，创建定制化的视觉设计系统（CSS/JS）。 | 风格指南 / 资产 |
| **Transformer** | 将 Markdown 转换为符合语义且严格遵循样式映射的 HTML 片段。 | HTML 片段 |
| **Assembler** | 将所有资产集成，生成最终的生产级 HTML 文档。 | Final.html |

---

## 📊 各节点输入/输出详解

### 1. 澄清者 Agent (ClarifierAgent)

```mermaid
graph LR
    subgraph 输入
        I1[原始素材 raw_materials]
        I2[参考文档 reference_docs]
        I3[参考图片 reference_images]
    end
    
    subgraph ClarifierAgent
        C[分析需求歧义点]
    end
    
    subgraph 输出
        O1[澄清问题列表 questions]
        O2["每个问题包含: id, category, question"]
    end
    
    I1 --> C
    I2 --> C
    I3 --> C
    C --> O1
    C --> O2
```

### 2. 精炼者 Agent (RefinerAgent)

```mermaid
graph LR
    subgraph 输入
        I1[原始素材 raw_materials]
        I2[用户回答 clarification_answers]
    end
    
    subgraph RefinerAgent
        R[综合信息生成结构化简报]
    end
    
    subgraph 输出
        O1[项目简报 project_brief]
        O2["包含: 目标, 受众, 风格, 深度要求"]
    end
    
    I1 --> R
    I2 --> R
    R --> O1
    R --> O2
```

### 3. 大纲 Agent (OutlineAgent)

```mermaid
graph LR
    subgraph 输入
        I1[项目简报 project_brief]
    end
    
    subgraph OutlineAgent
        O[设计文档骨架]
    end
    
    subgraph 输出
        O1[Manifest JSON]
        O2["sections: [{id, title, summary, estimated_words}]"]
        O3[knowledge_map: 章节知识点映射]
    end
    
    I1 --> O
    O --> O1
    O --> O2
    O --> O3
```

### 4. 技术规范 Agent (TechSpecAgent)

```mermaid
graph LR
    subgraph 输入
        I1[项目简报 project_brief]
        I2[Manifest 结构]
    end
    
    subgraph TechSpecAgent
        T[生成 SOTA 技术指令]
    end
    
    subgraph 输出
        O1[SOTA Description]
        O2["包含: 视觉风格, CSS 效果, SVG 动画, 交互逻辑"]
    end
    
    I1 --> T
    I2 --> T
    T --> O1
    T --> O2
```

### 5. 写手 Agent (WriterAgent)

```mermaid
graph LR
    subgraph 输入
        I1[项目简报 project_brief]
        I2[Manifest 结构]
        I3[SOTA Description]
        I4[已完成章节 completed_md_sections]
        I5[原始素材 raw_materials]
    end
    
    subgraph WriterAgent
        W[全量上下文写作]
    end
    
    subgraph 输出
        O1["sec-{n}.md 文件"]
        O2["Markdown 内容: 标题, 正文, 公式, 代码块"]
    end
    
    I1 --> W
    I2 --> W
    I3 --> W
    I4 --> W
    I5 --> W
    W --> O1
    W --> O2
```

### 6. 设计组 Agent (DesignAgent)

```mermaid
graph LR
    subgraph 输入
        I1[SOTA Description]
        I2[所有 Markdown 内容]
    end
    
    subgraph DesignAgent
        D1[Designer: 视觉风格指南]
        D2[CSS Coder: 生成 CSS]
        D3[JS Scripter: 生成 JS]
    end
    
    subgraph 输出
        O1[style.css]
        O2[main.js]
        O3[style_mapping.json]
    end
    
    I1 --> D1
    I2 --> D1
    D1 --> D2
    D2 --> D3
    D2 --> O1
    D2 --> O3
    D3 --> O2
```

### 7. 转换器 Agent (TransformerAgent)

```mermaid
graph LR
    subgraph 输入
        I1[SOTA Description]
        I2["sec-{n}.md 内容"]
        I3[style_mapping.json]
        I4[已使用 ID 列表]
    end
    
    subgraph TransformerAgent
        T[Markdown → HTML 语义转换]
    end
    
    subgraph 输出
        O1["sec-{n}.html 片段"]
        O2["语义化 HTML: section, article, figure"]
    end
    
    I1 --> T
    I2 --> T
    I3 --> T
    I4 --> T
    T --> O1
    T --> O2
```

### 8. 装配者 Agent (AssemblerAgent)

```mermaid
graph LR
    subgraph 输入
        I1[所有 HTML 片段]
        I2[style.css]
        I3[main.js]
        I4[Manifest 元数据]
    end
    
    subgraph AssemblerAgent
        A[拼接完整 HTML 文档]
    end
    
    subgraph 输出
        O1[final.html]
        O2["完整文档: head, body, 内联 CSS/JS"]
    end
    
    I1 --> A
    I2 --> A
    I3 --> A
    I4 --> A
    A --> O1
    A --> O2
```

## 🎨 设计原则

- **演绎推理 (Deductive Reasoning)**：内容从第一性原理出发，确保深层的逻辑一致性。
- **极致美学 (Rich Aesthetics)**：预设高端暗色主题、玻璃拟态效应和优质字体系统。
- **交互式 SOTA**：无缝集成 SVG 动画、交互模型和响应式布局。
- **领域无关 (Domain Agnostic)**：提示词通用化，具体专业深度由 AI 对用户上下文的理解驱动。

## 🏁 快速开始

1.  **环境安装**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **API 配置**:
    确保 Gemini API 代理服务已运行（默认地址 `http://localhost:7860`）。
3.  **启动应用**:
    ```bash
    streamlit run app.py
    ```

## 📄 许可证

MIT
