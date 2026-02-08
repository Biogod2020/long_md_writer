# Track Specification: SOTA 2.0 Native Checkpoint & Artifact Audit Harness

## 1. Overview
This track implements a professional test harness utilizing LangGraph's native persistence and interruption features. It enables granular debugging, state re-entry, and manual artifact auditing.

## 2. Functional Requirements

### 2.1 Native Persistence (LangGraph Core)
- **Persistent Storage**: Use `SqliteSaver` to store every node transition in a local database (`checkpoints.db`).
- **Time Travel**: Support jumping to any historical `checkpoint_id` to re-run specific nodes.
- **Native Interrupts**: Use `interrupt_before` to implement the `--until` logic at the graph level.

### 2.2 Artifact Grounding (The "Look at it" requirement)
- **Snapshot Isolation**: When a breakpoint is reached, the system will physically copy current workspace artifacts to an isolated `snapshots/BP-N/` folder to prevent "state pollution" from later steps.
- **Agent Audit Protocol**: The Agent (Me) must perform a mandatory `ls` and `read_file` audit of the `snapshots/` directory upon every interruption.

## 3. Technical Implementation
- **Checkpointer**: `langgraph.checkpoint.sqlite.SqliteSaver`.
- **Harness CLI**: A tool that interfaces with the compiled graph's `get_state`, `get_state_history`, and `update_state` methods.
- **Workflow Hook**: Integrate native checkpointing into `src/orchestration/workflow_markdown.py`.
