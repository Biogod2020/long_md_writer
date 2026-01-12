# 🧬 Magnum Opus: Markdown Generation Pipeline (Semantics Flow)

This is part of the Magnum Opus system, focusing on the generation of high-quality, structured Markdown content from user intent. It covers requirements clarification, structural planning, multimodal writing, asset fulfillment, and editorial QA.

[← Back to Main Index](README.md) | [Go to HTML Conversion Pipeline →](README_HTML.md)

---

## 🏗️ Semantic Pipeline Architecture: Phase A, B & D

```mermaid
flowchart TD
    %% Styles
    classDef agent fill:#f9f5ff,stroke:#7c3aed,stroke-width:2px
    classDef artifact fill:#ecfdf5,stroke:#059669,stroke-dasharray:5 5
    classDef decision fill:#fef2f2,stroke:#dc2626,stroke-width:2px
    classDef userinput fill:#fef3c7,stroke:#d97706,stroke-width:2px
    classDef phase_new fill:#dbeafe,stroke:#2563eb,stroke-width:2px

    %% ========== PHASE A: Planning & Foundation ========== 
    subgraph PA["Phase A: Planning & Foundation"]
        direction TB
        UserIntent["🎯 User Intent + Assets"]:::artifact
        UserIntent --> AssetIndexer["Asset Indexer Agent"]:::phase_new
        AssetIndexer --> UAR["📦 Universal Asset Registry (UAR)"]:::artifact
        
        UserIntent --> Clarifier["Clarifier Agent"]:::agent
        Clarifier -->|"3-5 Questions"| UserQA["👤 User Answers"]:::userinput
        UserQA --> Refiner["Refiner Agent"]:::agent
        Refiner --> PB["📄 Project Brief"]:::artifact
        
        PB --> BriefGate{"👤 Approve?"}:::decision
        BriefGate -->|Rejected| Refiner
        BriefGate -->|Approved| Architect["Architect Agent"]:::agent
        
        Architect --> Manifest["📦 Manifest"]:::artifact
        Manifest --> OutlineGate{"👤 Approve?"}:::decision
        OutlineGate -->|Rejected| Architect
        OutlineGate -->|Approved| TechSpec["TechSpec Agent"]:::agent
        TechSpec --> SotaDesc["📜 SOTA Description"]:::artifact
    end

    %% ========== PHASE B: Deep Content Creation ========== 
    subgraph PB2["Phase B: Deep Content Creation"]
        direction TB
        
        %% Layer 1: Writer Loop
        SotaDesc -.-> Writer["Writer Agent (Multimodal)"]:::agent
        Writer -->|":::visual intent stubs"| WriterOut["📝 Markdown + Visual Directives"]:::artifact
        WriterOut --> WriterGate{"All Sections Done?"}:::decision
        WriterGate -->|"No: Next"| Writer
        WriterGate -->|"Yes"| ScriptDeco
        
        %% Layer 2: Script Decoration
        ScriptDeco["Script Decorator Agent"]:::phase_new
        ScriptDeco -->|":::script injection"| DecoratedMD["📝 Enhanced Markdown"]:::artifact
        DecoratedMD --> MdQA
        
        %% Markdown QA (Critic-Advicer-Fixer)
        subgraph MdQABox["Markdown QA Loop"]
            direction LR
            MdQA["Critic"]:::agent -->|"MODIFY"| Advicer["Advicer"]:::agent
            Advicer --> Fixer["Fixer"]:::agent
            Fixer -->|"patch"| MdQA
        end
        
        MdQA -->|"REWRITE"| Writer
        MdQA -->|"APPROVE / Max Iterations"| MdReview{"👤 Markdown Review"}:::decision
        MdReview -->|Rejected + Feedback| MdQA
    end
    
    %% ========== PHASE D: Asset-First Closure ========== 
    subgraph PD["Phase D: Asset-First Closure"]
        direction TB
        MdReview -->|Approved| AssetFulfill["Asset Fulfillment Agent"]:::phase_new
        AssetFulfill -->|"SVG Gen / Image Search"| AssetResult["🖼️ Generated Assets"]:::artifact
        AssetResult --> AssetCritic["Asset Critic Agent"]:::phase_new
        AssetCritic --> CriticGate{"Asset Quality OK?"}:::decision
        CriticGate -->|"No: Regenerate"| AssetFulfill
        CriticGate -->|"Yes"| EditorialQA
        
        %% Full Semantic Review
        EditorialQA["Editorial QA Agent (VLM)"]:::phase_new
        EditorialQA -->|"GhostBuffer Extraction"| VerifiedMD["📝 Verified Markdown"]:::artifact
    end

    %% Connections between phases
    PA --> PB2
    PB2 --> PD
```

---

## 🛠️ Specialized Agent Nodes (Semantics & Assets)

| Agent | Capability | Key SOTA Output |
| :--- | :--- | :--- |
| **Asset Indexer** | Scans user assets, generates semantic labels and quality assessments via VLM. | `assets.json` (UAR) |
| **Clarifier** | Ambiguity resolution via 3-5 targeted questions. | `clarification_questions.json` |
| **Refiner** | Synthesizes user input + clarification into structured Project Brief. | Project Brief (Markdown) |
| **Architect** | Intellectual hierarchy design; prevents "shallow" content. | `manifest.json` |
| **TechSpec** | Generates execution contract with design specs and interactivity requirements. | SOTA Description |
| **Writer** | Full-context multimodal writer; outputs `:::visual` intent stubs. | Markdown + Visual Directives |
| **Script Decorator** | Identifies interactive elements, injects `:::script` directive blocks. | Enhanced Markdown |
| **Markdown QA** | AI self-correction + Human-in-the-Loop review of Markdown content. | Validated Markdown |
| **Asset Fulfillment** | Parses `:::visual` directives, executes SVG generation/image search. | Fulfilled Assets |
| **Asset Critic** | VLM visual matching audit, verifies assets match intent descriptions. | Audit Reports |
| **Editorial QA** | Full semantic review + GhostBuffer skeleton extraction. | Semantic Summary |

---

## 📊 Data Contract Details

### Phase 1: Planning Agents

#### 1. Clarifier Agent
- **Input**: `AgentState.raw_materials`, `AgentState.images`, `AgentState.reference_docs`
- **Output**: `AgentState.clarifier_questions` (`list[ClarificationQuestion]`)

#### 2. Refiner Agent
- **Input**: `AgentState.raw_materials`, `AgentState.clarifier_answers`, `AgentState.user_brief_feedback`
- **Output**: `AgentState.project_brief`

#### 3. Outline Agent
- **Input**: `AgentState.project_brief`, `AgentState.user_outline_feedback`
- **Output**: `AgentState.manifest` (outline.json)

---

## 🔬 Deep Dive: Semantic Flow Core Logic

### 1. Full-Context Awareness
The Writer node doesn't just see the current section outline; it has access to all previously generated Markdown sections. This ensures terminology consistency and logical coherence across long documents.

### 2. Intent-Driven Asset Production
Magnum Opus 2.0 no longer generates image URLs directly. Instead, the Writer generates "Visual Intents". These intents are fulfilled in Phase D by specialized agents that decide whether to generate precise SVG code or search for high-quality photos.

### 3. Human-in-the-Loop Propagation
Strategic checkpoints at Brief, Outline, and Markdown phases allow users to steer the AI. Feedback is propagated back to the respective agents with high priority.
