# Specification: Global Markdown Gatekeeper (Phase E-1)

## Overview
Introduce a dedicated **Global Markdown QA** stage into the SOTA 2.0 publication engine. This stage acts as the final "quality gate" after individual chapters have completed asset fulfillment but before the HTML transformation begins. It ensures that the merged output is syntactically perfect, contextually coherent, and structurally sound.

## Functional Requirements

### 1. Physical Merging Logic
- **Task**: Implement a merging mechanism that concatenates all `completed_md_sections` into a single `final_full.md`.
- **Formatting**: Ensure sections are separated by clear markers (e.g., `<!-- SECTION: s1 -->`) to maintain traceability during the QA process.

### 2. Upgraded SOTA 2.0 Agent Architecture
- **Agent**: Leverage and extend the `EditorialQAAgent`, refactoring it to follow the polished **Critic-Advicer-Fixer** pattern used in Stage 3.2.
- **Alignment with Prior Art**:
    - **From SanityAgent**: Incorporate fast, local regex-based pre-checks for JSON and container integrity.
    - **From MarkdownQA**: Implement the **Advicer** component to translate global critiques into granular, per-section editing instructions.
    - **From VisualQA**: Utilize **Spatial/Contextual Anchoring** in patches to ensure 100% replacement accuracy in large files.
- **Resilience**: Enforce use of the `Universal Patcher` (with fuzzy-literal fallback) and `StuckDetector` to handle complex "math-hell" or nested container repairs.

### 3. Full-Context Audit Scope
- **Macro-Audit**: Focus on:
    - **Structural Integrity**: Logical heading hierarchy (H1 -> H2 -> H3) across the entire book.
    - **Contextual Flow**: Smooth transitions between merged sections and logical narrative progression.
    - **Terminology Alignment**: Consistent use of technical/medical terms across all chapters.
    - **Asset Integration**: Verify all fulfilled images and SVGs are correctly linked and positioned in the merged file.

### 4. Hybrid Escalation & Repair
- **Minor Issues**: The agent shall attempt automatic repair using high-precision JSON patching.
- **Major Issues**: For fundamental structural failures or severe logical contradictions, the agent must generate a report and trigger an interrupt for manual intervention.
- **Iteration Limit**: Cap the automated repair loop at 3 iterations.

### 5. Workflow Integration
- **Node Position**: Insert a `global_markdown_qa` node in the LangGraph workflow after `BatchFulfillment` and before `DesignTokens`/`Transformer`.
- **SSOT Commitment**: Once audited, the `final_full.md` becomes the **Single Source of Truth** for the subsequent HTML transformation pipeline.

## Non-Functional Requirements
- **Observability**: Save detailed QA reports (`qa_report_global.json`) and captures of the `Thinking` tokens to understand the "Why" behind structural changes.
- **Persistence**: Snapshots of the merged file before and after repair must be stored in the workspace for auditing.

## Acceptance Criteria
- [ ] A `final_full.md` is generated containing all book content.
- [ ] Cross-chapter terminology inconsistencies are detected and corrected via the Advicer-Fixer loop.
- [ ] Heading levels follow a logical hierarchy across the entire merged file.
- [ ] The workflow successfully proceeds to HTML transformation using the audited merged file.
