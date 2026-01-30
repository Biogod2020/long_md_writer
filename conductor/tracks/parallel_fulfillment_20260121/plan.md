# Implementation Plan: Centralized Parallel Fulfillment & Section-Level QA Refactor

## Phase 1: Agent Logic & TDD
- [x] Task: Create `tests/test_writer_directives.py` to verify new `:::visual` output format.
- [x] Task: Update `WriterAgent` in `src/agents/writer_agent.py`.
    - [x] Remove all HTML `<img>` and `<figure>` tag generation logic.
    - [x] Update system prompt to mandate `:::visual` blocks.
    - [x] Add requirement for `reuse_score` and `reason` when selecting existing assets.
- [x] Task: Create `tests/test_fulfillment_patching.py` to verify in-place Markdown updates.
- [x] Task: Upgrade `AssetFulfillmentAgent` in `src/agents/asset_management/fulfillment.py`.
    - [x] Implement batch scanning: ability to gather directives from multiple files.
    - [x] Implement parallel execution using `asyncio.gather` with semaphore control.
    - [x] Implement `apply_fulfillment_to_file`: a utility to replace `:::visual` with finalized HTML tags on disk.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Agent Logic & TDD' (Protocol in workflow.md)

## Phase 2: Orchestration & Workflow Redesign
- [x] Task: Update `src/orchestration/workflow_markdown.py` Node Topology.
    - [x] Relocate `markdown_qa` and `markdown_review` nodes to execute immediately after `writer` for each section.
    - [x] Create `batch_fulfillment_node` to execute after the completion of all chapter text.
    - [x] Create `batch_asset_review_node` to aggregate and present all VQA failures at the end of the workflow.
- [x] Task: Update `src/orchestration/edges.py` routing logic.
    - [x] Implement section-level loop: `writer` -> `markdown_qa` -> `markdown_review` -> (back to `writer` OR move to next section).
    - [x] Ensure fulfillment only triggers once all sections are finalized.
- [x] Task: Update `AgentState` in `src/core/types.py`.
    - [x] Add fields to track batch fulfillment status and aggregated failures.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Orchestration Refactor' (Protocol in workflow.md)

## Phase 3: Integration & Finalization
- [x] Task: Write E2E Integration Test `tests/test_parallel_workflow_e2e.py`.
    - [x] Verify the "Text First, Assets Last" execution order.
    - [x] Verify parallel API calls are stable.
    - [x] Verify final Markdown files contain injected tags.
- [x] Task: Run full project build and linting checks.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Integration & Finalization' (Protocol in workflow.md)
