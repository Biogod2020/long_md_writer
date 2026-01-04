# Magnum Opus HTML Agent

An advanced, multi-stage AI agent system for generating SOTA (State-of-the-Art) technical lectures, academic documents, and long-form HTML content with rich aesthetics and interactive components.

## 🚀 Overview

Magnum Opus HTML Agent decomposes complex technical writing and design into a modular pipeline. It uses proactive clarification to eliminate ambiguity and a global "SOTA Description" to ensure consistent quality across all downstream agents.

## 🏗️ Architecture

The system follows a multi-stage decomposition pattern (ADaPT/LLM Chaining) to ensure high-quality output through specialized agents.

### Overall Workflow

```mermaid
graph LR
    A[Raw Input] --> B[Clarifier]
    B -->|Questions| C[User Answers]
    C --> D[Refiner]
    D -->|Project Brief| E[Outline]
    E -->|Structure| F[TechSpec]
    F -->|SOTA Spec| G[Production Pipeline]
    
    subgraph "Production Pipeline"
    G --> H[Writer]
    H --> I[Designer]
    I --> J[Transformer]
    J --> K[SVG Creator]
    K --> L[Assembler]
    end
    
    style K fill:#f9f,stroke:#a855f7,stroke-width:3px
```

### Node Input/Output Specifications

The following diagram details the specific data flow between each agent node:

```mermaid
graph TD
    classDef agent fill:#f9f,stroke:#333,stroke-width:2px;
    classDef data fill:#bbf,stroke:#333,stroke-width:1px;
    classDef newagent fill:#f9f,stroke:#a855f7,stroke-width:3px;

    subgraph Planning ["Planning & Alignment Phase"]
        In[Raw Materials]:::data --> Clarifier[Clarifier Agent]:::agent
        Clarifier --> Q[Clarifying Questions]:::data
        Q --> Ans[User Answers]:::data
        In & Ans --> Refiner[Refiner Agent]:::agent
        Refiner --> Brief[Project Brief]:::data
        In & Brief --> Outline[Outline Agent]:::agent
        Outline --> Manifest[Manifest: Structure]:::data
        In & Brief & Manifest --> TechSpec[TechSpec Agent]:::agent
        TechSpec --> Spec[SOTA Description]:::data
    end

    subgraph Production ["Production & Execution Phase"]
        Brief & Manifest & Spec --> Writer[Writer Agent]:::agent
        Writer --> MD[Markdown Content]:::data
        Brief & MD & Spec --> Designer[Design Agent]:::agent
        Designer --> Assets[CSS/JS/Mapping]:::data
        MD & Assets & Spec & PrevHTML[Completed HTML] --> Transformer[Transformer Agent]:::agent
        Transformer --> Frags[HTML Fragments + SVG Placeholders]:::data
        Frags & Spec & Brief --> SVGCreator[SVG Creator Agent]:::newagent
        SVGCreator --> ValidatedHTML[Validated HTML]:::data
        ValidatedHTML & Assets --> Assembler[Assembler Agent]:::agent
        Assembler --> Out[Final HTML]:::data
    end
```

## 🛠️ Core Agents

| Agent | Responsibility | Key Output |
| :--- | :--- | :--- |
| **Clarifier** | Analyzes input and asks 3-5 targeted questions to resolve ambiguity. | Clarifying Questions |
| **Refiner** | Synthesizes raw input and user answers into a domain-agnostic Project Brief. | Project Brief |
| **Outline** | Designs the high-level document structure (sections, knowledge map). | Manifest (Structure) |
| **TechSpec** | Generates detailed technical specifications (the "SOTA Description"). | Global Instructions |
| **Writer** | Generates exhaustive Markdown content for each section using full-context awareness. | Markdown Files |
| **Designer** | Creates a custom visual design system (CSS/JS) based on the TechSpec. | Style Guide / Assets |
| **Transformer** | Converts Markdown into semantic HTML fragments following strict style mappings. | HTML Fragments |
| **Assembler** | Integrates all components into a single, production-ready HTML document. | Final.html |

---

## 📊 Detailed Node Input/Output Diagrams

### 1. Clarifier Agent

```mermaid
graph LR
    subgraph Inputs
        I1[raw_materials]
        I2[reference_docs]
        I3[reference_images]
    end
    
    subgraph ClarifierAgent
        C[Analyze ambiguity]
    end
    
    subgraph Outputs
        O1[questions: list]
        O2["Each question: {id, category, question}"]
    end
    
    I1 --> C
    I2 --> C
    I3 --> C
    C --> O1
    C --> O2
```

### 2. Refiner Agent

```mermaid
graph LR
    subgraph Inputs
        I1[raw_materials]
        I2[clarification_answers]
    end
    
    subgraph RefinerAgent
        R[Synthesize structured brief]
    end
    
    subgraph Outputs
        O1[project_brief: string]
        O2["Contains: goal, audience, style, depth"]
    end
    
    I1 --> R
    I2 --> R
    R --> O1
    R --> O2
```

### 3. Outline Agent

```mermaid
graph LR
    subgraph Inputs
        I1[project_brief]
    end
    
    subgraph OutlineAgent
        O[Design document skeleton]
    end
    
    subgraph Outputs
        O1[Manifest JSON]
        O2["sections: [{id, title, summary, estimated_words}]"]
        O3[knowledge_map: section-to-topics mapping]
    end
    
    I1 --> O
    O --> O1
    O --> O2
    O --> O3
```

### 4. TechSpec Agent

```mermaid
graph LR
    subgraph Inputs
        I1[project_brief]
        I2[Manifest structure]
    end
    
    subgraph TechSpecAgent
        T[Generate SOTA Instructions]
    end
    
    subgraph Outputs
        O1[SOTA Description]
        O2["Contains: visual style, CSS effects, SVG animations, interactivity"]
    end
    
    I1 --> T
    I2 --> T
    T --> O1
    T --> O2
```

### 5. Writer Agent

```mermaid
graph LR
    subgraph Inputs
        I1[project_brief]
        I2[Manifest structure]
        I3[SOTA Description]
        I4[completed_md_sections]
        I5[raw_materials]
    end
    
    subgraph WriterAgent
        W[Full-context writing]
    end
    
    subgraph Outputs
        O1["sec-{n}.md file"]
        O2["Markdown: headers, body, formulas, code blocks"]
    end
    
    I1 --> W
    I2 --> W
    I3 --> W
    I4 --> W
    I5 --> W
    W --> O1
    W --> O2
```

### 6. Design Agent

```mermaid
graph LR
    subgraph Inputs
        I1[SOTA Description]
        I2[All Markdown content]
    end
    
    subgraph DesignAgent
        D1[Designer: Visual Guide]
        D2[CSS Coder: Generate CSS]
        D3[JS Scripter: Generate JS]
    end
    
    subgraph Outputs
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

### 7. Transformer Agent

```mermaid
graph LR
    subgraph Inputs
        I1[SOTA Description]
        I2["sec-{n}.md content"]
        I3[style_mapping.json]
        I4[Used ID list]
    end
    
    subgraph TransformerAgent
        T[Markdown to semantic HTML]
    end
    
    subgraph Outputs
        O1["sec-{n}.html fragment"]
        O2["Semantic HTML: section, article, figure"]
    end
    
    I1 --> T
    I2 --> T
    I3 --> T
    I4 --> T
    T --> O1
    T --> O2
```

### 8. Assembler Agent

```mermaid
graph LR
    subgraph Inputs
        I1[All HTML fragments]
        I2[style.css]
        I3[main.js]
        I4[Manifest metadata]
    end
    
    subgraph AssemblerAgent
        A[Assemble full document]
    end
    
    subgraph Outputs
        O1[final.html]
        O2["Complete document: head, body, inline CSS/JS"]
    end
    
    I1 --> A
    I2 --> A
    I3 --> A
    I4 --> A
    A --> O1
    A --> O2
```

## 🎨 Design Principles

- **Deductive Reasoning**: Content is derived from first principles, ensuring deep logical consistency.
- **Rich Aesthetics**: High-end dark themes, glassmorphism, and premium typography by default.
- **Interactive SOTA**: Seamless integration of SVG animations, interactive models, and responsive layouts.
- **Domain Agnostic**: Prompts are generic; specificity is driven by the AI's understanding of user context.

## 🏁 Getting Started

1.  **Installation**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Environment**:
    Ensure your Gemini API Proxy is running (default `http://localhost:7860`).
3.  **Run App**:
    ```bash
    streamlit run app.py
    ```

## 📄 License

MIT
