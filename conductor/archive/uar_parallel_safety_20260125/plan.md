# Implementation Plan: UAR Parallel Safety & Reporting

## Phase 1: Thread-Safe Aggregation Logic [checkpoint: ec77e4e]
- [x] Task: Refactor `AssetFulfillmentAgent` for deferred registration
    - [x] Create `tests/test_fulfillment_aggregation.py` to verify in-memory collection of assets.
    - [x] Modify `_fulfill_directive_async` to return `AssetEntry` objects instead of calling `register_immediate`.
    - [x] Update `run_parallel_async` to collect these returned assets and perform a bulk registration at the end.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Thread-Safe Aggregation' (Protocol in workflow.md) (ec77e4e)

## Phase 2: Enhanced Reporting & Accounting [checkpoint: 16de3aa]
- [x] Task: Implement `FulfillmentReport` structure
    - [x] Update `AgentState` or `AssetFulfillmentAgent` to track `reused_assets` and `mermaid_charts` counts.
    - [x] Ensure `USE_EXISTING` and `GENERATE_MERMAID` actions properly increment these counters in the return values of `_fulfill_*` methods.
- [x] Task: Verify Reporting Accuracy (30f1754)
    - [x] Update `tests/debug_sota2_workflow.py` to print the detailed breakdown (New/Reused/Mermaid) at the end.
    - [x] Run the E2E test and verify the numbers match the directives in the Markdown. (SUCCESS: Confirmed batch registration of 5 assets and accurate 5/3/1 breakdown)
- [x] Task: Conductor - User Manual Verification 'Phase 2: Reporting' (Protocol in workflow.md) (16de3aa)
