# Specification: Centralized Parallel Fulfillment & Section-Level QA Refactor

## Overview
This track refactors the SOTA 2.0 workflow to decouple text creation from asset fulfillment. It deprecates the Writer's ability to directly inject HTML image tags, forcing all visual needs through `:::visual` directives. The workflow is reorganized to ensure high text quality via section-level AI self-correction and optional human review, followed by a high-performance parallel fulfillment phase for all visual assets at the end of the project.

## Functional Requirements
1.  **Deprecate Direct-Inject & Writer Reuse Scoring**: 
    *   Update `WriterAgent` to remove all `<img>` tag generation logic. 
    *   **New Rule**: When the Writer decides to reuse an existing asset from the UAR, it MUST include a `reuse_score` (0-100) and a brief `reason` inside the `:::visual` JSON configuration to explain the choice.
2.  **Section-Level Text QA**:
    *   Relocate `MarkdownQAAgent` from the end of the workflow to run immediately after each chapter's drafting.
    *   Implement an autonomous loop where the Agent self-corrects the chapter text until it meets quality standards (internal AI "PASS" or max iterations).
    *   Introduce an optional human-in-the-loop (HITL) interrupt point after the Agent's self-correction.
3.  **Parallel Fulfillment Node**:
    *   Create a new orchestration node that executes after ALL chapters have reached "Text Finalized" status.
    *   Process all gathered `:::visual` directives in parallel (using `asyncio.gather`).
    *   Include VQA (Visual Quality Assurance) auditing within this parallel phase.
4.  **Batch Human Intervention**:
    *   **New Logic**: Instead of interrupting the flow for every failed asset, the system will process ALL visual blocks first.
    *   Failed assets (those that did not pass VQA after max retries) will be aggregated into a single "Batch Review" node at the very end of the fulfillment phase for human decision (retry/skip/manual fix).
5.  **Markdown In-place Update**:
    *   After successful fulfillment, the system will physically update the `.md` files on disk, replacing `:::visual` directives with finalized tags.

## Acceptance Criteria
*   Writer produces `:::visual` blocks with `reuse_score` for existing assets.
*   Workflow handles text QA per section and gathers all visual failures for a single, final human review.
*   Final `.md` files on disk contain the actual image tags instead of `:::visual` directives.
