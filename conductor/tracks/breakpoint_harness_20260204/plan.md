# Implementation Plan: SOTA 2.0 Native Checkpoint & Artifact Audit Harness

## Phase 1: Native Persistence & Workflow Integration [checkpoint: e283afd]
- [x] Task: Ensure `src/orchestration/workflow_markdown.py` is fully compatible with `AsyncSqliteSaver`. e283afd
    - [x] Standardize the `checkpoints.db` location within the job's workspace. e283afd
    - [x] Verify that all node functions handle state updates without breaking SQLite serialization. e283afd
- [x] Task: Integrate `SnapshotManager` into the workflow entry point. e283afd
    - [x] Automatically trigger a snapshot when any `interrupt_before` node is reached. e283afd
- [x] Task: Standardize `scripts/test_breakpoint_flow.py` as the primary test harness. e283afd
- [x] Task: Conductor - User Manual Verification 'Phase 1: Hybrid Persistence' (Protocol in workflow.md) e283afd

## Phase 2: Interruption & Physical Auditing [checkpoint: e283afd]
- [x] Task: Enhance the Harness CLI to support `audit` command: automatically listing and reading files from the latest snapshot. e283afd
- [x] Task: Implement "Jump to Breakpoint": Use Snapshot restoration + logic sync to resume from any previous state. e283afd
- [x] Task: Integrate `SnapshotManager` call into the core `workflow_markdown.py` node logic. e283afd
- [x] Task: Conductor - User Manual Verification 'Phase 2: Audit Logic' (Protocol in workflow.md) e283afd

## Phase 3: Time Travel & Final E2E [checkpoint: e283afd]
- [x] Task: Run the flow through the full production cycle (Writing -> QA -> Fulfillment). e283afd
- [x] Task: Perform a "Mid-production Jump": Backtrack from Writer to Architect to verify logic consistency. e283afd
- [x] Task: Generate a final summary of the pipeline's state history and snapshots. e283afd
- [x] Task: Conductor - User Manual Verification 'Phase 3: Final E2E' (Protocol in workflow.md) e283afd