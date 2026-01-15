# Plan: Intelligent Asset Reuse and Deduplication

This plan follows the TDD and verification protocols defined in `conductor/workflow.md`.

## Phase 1: Contextual Scoring & UAR Lookup

- [x] Task: Create `tests/test_asset_reuse_scoring.py` to verify scoring logic against mock UAR data. ef71f07
- [x] Task: Implement `AssetFulfillmentAgent._calculate_reuse_score()` using VLM/LLM semantic comparison. ef71f07
- [x] Task: Implement `AssetFulfillmentAgent._query_uar_for_candidates()` to retrieve potential matches. ef71f07
- [~] Task: Conductor - User Manual Verification 'Phase 1: Contextual Scoring & UAR Lookup' (Protocol in workflow.md)

## Phase 2: Reuse Logic & Frequency Control

- [ ] Task: Create `tests/test_asset_reuse_logic.py` to verify decision making (Reuse vs. Create vs. Suppress).
- [ ] Task: Implement `AssetFulfillmentAgent._decide_fulfillment_strategy()` to handle the 90+ score threshold and usage frequency check.
- [ ] Task: Update `AssetFulfillmentAgent.run()` to execute the chosen strategy (inject ID vs. call creation tools).
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Reuse Logic & Frequency Control' (Protocol in workflow.md)

## Phase 3: Integration & E2E Testing

- [ ] Task: Create `tests/test_asset_reuse_e2e.py` simulating a workflow with repeated visual intents.
- [ ] Task: Verify that identical intents reuse the file ID.
- [ ] Task: Verify that distinct intents generate new files.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Integration & E2E Testing' (Protocol in workflow.md)
