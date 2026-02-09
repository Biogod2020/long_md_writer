# Track Specification: SOTA 2.0 Native Checkpoint & Artifact Audit Harness

## 1. Overview
This track implements a professional test harness utilizing LangGraph's native persistence and interruption features. It enables granular debugging, state re-entry, and manual artifact auditing.

## 2. Functional Requirements

### 2.1 Native Interruption & Persistence (Hybrid Model)
- **Logical Persistence**: Use `langgraph.checkpoint.sqlite.AsyncSqliteSaver` to persist the graph's state and history in a local `checkpoints.db`. This allows the engine to "remember" exactly where it left off across process restarts.
- **Thread Management**: Each run is assigned a unique `thread_id` (linked to `job_id`), enabling multiple independent production sessions.
- **Physical Grounding**: Every time a breakpoint is hit, the system triggers `SnapshotManager` to solidify the current workspace state.

### 2.2 Artifact Grounding (The "Look at it" requirement)
- **Snapshot Isolation**: When a breakpoint is reached, the system will physically copy current workspace artifacts (Markdown, UAR, etc.) to an isolated `snapshots/BP-N/` folder. This provides a human-readable "save point" for auditing.
- **Agent Audit Protocol**: The Agent (Me) must perform a mandatory `ls` and `read_file` audit of the `snapshots/` directory upon every interruption to verify production quality before resuming.

## 3. Technical Implementation
- **Checkpointer**: `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`.
- **Physical Auditor**: `src/orchestration/breakpoint_manager.py` (`SnapshotManager`).
- **Harness CLI**: `scripts/test_breakpoint_flow.py`, which manages thread resumption and HITL interaction.
- **Workflow Hook**: Integrate native checkpointing into `src/orchestration/workflow_markdown.py`.
