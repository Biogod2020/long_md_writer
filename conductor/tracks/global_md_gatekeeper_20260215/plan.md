# Implementation Plan: Global Markdown Gatekeeper (Phase E-1)

This plan implements a global quality gate for the Markdown publication pipeline, ensuring structural, technical, and narrative consistency in the final merged document before HTML transformation.

## Phase 1: Foundation & Physical Merging [checkpoint: a22b231]
- [x] Task: Implement `MarkdownMerger` Utility
    - [x] Create `src/core/merger.py` to concatenate `completed_md_sections` into `final_full.md`.
    - [x] Inject clear traceability markers (e.g., `<!-- SECTION: s1 -->`) between chapters.
- [x] Task: Write Unit Tests for `MarkdownMerger`
    - [x] Verify section ordering, marker preservation, and handle empty/missing files.
- [x] Task: Conductor - User Manual Verification 'Foundation & Physical Merging' (Protocol in workflow.md)

## Phase 2: EditorialQAAgent Architectural Upgrade [checkpoint: f2878ad]
- [x] Task: Refactor `EditorialQAAgent` to SOTA 2.0 Critic-Advicer-Fixer Pattern
    - [x] Decompose `src/agents/editorial_qa_agent.py` into modular components (Critic, Advicer, Fixer).
    - [x] Ensure it leverages the `Universal Patcher` from `src/core/patcher.py`.
- [x] Task: Integrate Local Sanity Pre-checks
    - [x] Port regex-based JSON and container validation logic from `MarkdownSanityAgent`.
- [x] Task: Implement Contextual/Spatial Anchoring for Large Files
    - [x] Enhance the Fixer to provide high-precision anchors suitable for the merged `final_full.md`.
- [x] Task: Write Tests for Refactored Editorial Agent
- [x] Task: Conductor - User Manual Verification 'EditorialQAAgent Architectural Upgrade' (Protocol in workflow.md)

## Phase 3: Global Audit Logic & Repair Loop
- [ ] Task: Implement Macro-Audit Intelligence
    - [ ] Add specific Critic rules for cross-chapter heading hierarchy (H1-H3).
    - [ ] Implement terminology alignment checks (e.g., medical term consistency).
- [ ] Task: Implement Multi-Iteration Repair Loop
    - [ ] Integrate `StuckDetector` to handle repair stagnation.
    - [ ] Implement the 3-iteration cap and failure reporting.
- [ ] Task: Implement QA Observability & Reporting
    - [ ] Generate `qa_report_global.json` and capture `Thinking` tokens for transparency.
- [ ] Task: Conductor - User Manual Verification 'Global Audit Logic & Repair Loop' (Protocol in workflow.md)

## Phase 4: Workflow Integration & SSOT
- [ ] Task: Update LangGraph Orchestration
    - [ ] Add `global_markdown_qa` node to `src/orchestration/workflow_markdown.py`.
    - [ ] Wire the node to execute after `batch_fulfillment` but before HTML phases.
- [ ] Task: Establish `final_full.md` as SSOT
    - [ ] Update downstream nodes (`DesignTokens`, `Transformer`) to prioritize the merged file if available.
- [ ] Task: End-to-End (E2E) Integration Testing
    - [ ] Create a test scenario involving terminology drift and unclosed containers across multiple chapters.
- [ ] Task: Conductor - User Manual Verification 'Workflow Integration & SSOT' (Protocol in workflow.md)
