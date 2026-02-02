# Implementation Plan: Transactional Incremental Fulfillment & Breakpoint Resume

## Phase 1: Foundation & Idempotency Logic [checkpoint: 79d33c6]
- [x] Task: Create `tests/test_fulfillment_idempotency.py` to verify asset skip logic. (ec77e4e)
- [x] Task: Implement `_check_asset_exists` in `src/agents/asset_management/fulfillment.py`. (16de3aa)
    - [x] Logic: Check both UAR and physical disk (`agent_generated`/`agent_sourced`).
- [x] Task: Create `tests/test_working_copy_manager.py` to verify the "Working Copy" lifecycle. (30f1754)
- [x] Task: Implement `WorkingCopyManager` utility in `src/agents/asset_management/utils.py`. (1099d15)
    - [x] Logic: Handle `.working` file creation, incremental updates, and final atomic rename (commit).
- [x] Task: Conductor - User Manual Verification 'Phase 1: Foundation' (Protocol in workflow.md) (79d33c6)

## Phase 2: Agent Orchestration Refactor [checkpoint: 0c9a5a1]
- [x] Task: Update `AssetFulfillmentAgent.run_parallel_async` to use the Working Copy strategy. (748fd6a)
    - [x] Logic: Scan for existing `.working` files at startup to enable resume capability.
- [x] Task: Refactor parallel `worker` to perform "Live-Patching". (748fd6a)
    - [x] Logic: Instead of gathering all results at the end, each worker triggers a thread-safe update to the `.working` file immediately upon success.
- [x] Task: Implement `asyncio.Lock` for thread-safe Markdown writes. (748fd6a)
- [x] Task: Update UAR persistence to trigger after every successful asset fulfillment. (748fd6a)
- [x] Task: Conductor - User Manual Verification 'Phase 2: Agent Refactor' (Protocol in workflow.md) (0c9a5a1)

## Phase 3: Validation & Stress Testing
- [~] Task: Write E2E test `tests/test_fulfillment_resume_e2e.py`.
    - [ ] Scenario: Run 50% of tasks, simulate a `SIGKILL`, restart, and verify zero redundant API calls and 100% file integrity.
- [ ] Task: Verify final file cleanup (ensure `.working` files are removed on successful completion).
- [ ] Task: Run full project build and linting checks.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Validation' (Protocol in workflow.md)
