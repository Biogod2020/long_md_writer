# Implementation Plan: SOTA 2.0 Native Checkpoint & Artifact Audit Harness

## Phase 1: Native Persistence & Workflow Integration [checkpoint: none]
- [ ] Task: Update `src/orchestration/workflow_markdown.py` to use `SqliteSaver`.
    - [ ] Initialize a local SQLite DB in the workspace.
    - [ ] Ensure all nodes are compatible with native serialization.
- [ ] Task: Enhance `scripts/test_breakpoint_flow.py` to support `checkpoint_id` resumption.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Native Persistence' (Protocol in workflow.md)

## Phase 2: Interruption & Physical Snapshotting [checkpoint: none]
- [ ] Task: Implement `PhysicalCheckpointHook`: a function that runs alongside interrupts to copy files to `snapshots/`.
- [ ] Task: Refactor the CLI to use LangGraph's `app.get_state()` to display logical state during pauses.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Interruption Logic' (Protocol in workflow.md)

## Phase 3: Time Travel & Agent Audit Testing [checkpoint: none]
- [ ] Task: Run the flow to BP-3, stop, and "travel back" to BP-1 to modify a user intent field.
- [ ] Task: Perform a full SME audit at BP-5, manually verifying the Markdown artifacts produced by the Writer.
- [ ] Task: Generate a final summary of the pipeline's state history using `app.get_state_history()`.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final E2E' (Protocol in workflow.md)
