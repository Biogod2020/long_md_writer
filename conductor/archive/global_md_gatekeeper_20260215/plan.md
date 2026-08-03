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

## Phase 3: Global Audit Logic & Repair Loop [checkpoint: 8c33a74]
- [x] Task: Implement Macro-Audit Intelligence
    - [x] Add specific Critic rules for cross-chapter heading hierarchy (H1-H3).
    - [x] Implement terminology alignment checks (e.g., medical term consistency).
- [x] Task: Implement Multi-Iteration Repair Loop
    - [x] Integrate `StuckDetector` to handle repair stagnation.
    - [x] Implement the 3-iteration cap and failure reporting.
- [x] Task: Implement QA Observability & Reporting
    - [x] Generate `qa_report_global.json` and capture `Thinking` tokens for transparency.
- [x] Task: Conductor - User Manual Verification 'Global Audit Logic & Repair Loop' (Protocol in workflow.md)

## Phase 4: Workflow Integration & SSOT [checkpoint: f8a2fc4]
- [x] Task: Update LangGraph Orchestration
    - [x] Add `global_markdown_qa` node to `src/orchestration/workflow_markdown.py`.
    - [x] Wire the node to execute after `batch_fulfillment` but before HTML phases.
- [x] Task: Establish `final_full.md` as SSOT
    - [x] Update downstream nodes (`DesignTokens`, `Transformer`) to prioritize the merged file if available.
- [x] Task: End-to-End (E2E) Integration Testing
    - [x] Create a test scenario involving terminology drift and unclosed containers across multiple chapters.
- [x] Task: Conductor - User Manual Verification 'Workflow Integration & SSOT' (Protocol in workflow.md)

## Phase: Review Fixes
- [x] Task: Apply review suggestions
