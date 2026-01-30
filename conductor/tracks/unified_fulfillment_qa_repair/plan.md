# Implementation Plan: Unified Fulfillment QA & Mermaid Loop

## Phase 1: Infrastructure & Core Logic
1. [x] **[TDD] Mermaid Repair Utility**: Create `tests/test_mermaid_repair.py` to verify syntax and visual repair logic.
2. [x] **Implement Mermaid Audit/Repair**:
    - Update `src/agents/asset_management/processors/mermaid.py` with `audit_mermaid_async` and `repair_mermaid_async`.
    - Integrate Playwright rendering for visual feedback.
3. [x] **Upgrade AssetFulfillmentAgent**:
    - Refactor `_fulfill_generate_svg_async` to include a 3-attempt retry loop using `repair_svg_async`.
    - Refactor `_fulfill_generate_mermaid_async` to include a 3-attempt retry loop.
    - Ensure all repairs receive Base64 visual context if available.

## Phase 2: Workflow Refactoring
1. [x] **State Update**: Add `asset_revision_needed` and `failed_asset_id` to `AgentState` in `src/core/types.py`.
2. [x] **Node Factory Cleanup**: 
    - Remove `critic_node` and its factory method in `SOTA2NodeFactory` (`src/orchestration/workflow_markdown.py`).
3. [x] **Routing Logic**:
    - Update `should_continue_section_loop` to check for `state.asset_revision_needed`.
    - Inject an `interrupt_before` for the fulfillment node if revision is needed.

## Phase 3: Verification & UX
1. [x] **Integration Test**: Run a "forced failure" scenario where an asset cannot be fixed, ensuring the workflow pauses.
2. [x] **CLI Update**: Ensure `run_sota2_workflow` handles the new interrupt state gracefully, prompting the user for manual asset correction.

## Risk Assessment
- **Token Usage**: Multiple Vision API calls for repairs can be expensive. *Mitigation: Use lower resolution for audit renders.*
- **Time**: Playwright startup time for every asset. *Mitigation: Keep browser instance persistent within the fulfillment run.*