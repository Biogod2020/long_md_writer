# Specification: Unified Fulfillment QA & Mermaid Loop implementation

## Overview
This track addresses the "Blind Proceed" bug by migrating visual auditing and repair logic directly into the asset fulfillment process. We will remove the redundant post-chapter audit node and implement a dedicated QA/Repair loop for Mermaid charts, ensuring that no chapter proceeds until all its visual assets are verified and compliant.

## Functional Requirements

### 1. Workflow Cleanup
- **Remove `critic_node`**: Delete the redundant audit node from `src/orchestration/workflow_markdown.py`.
- **Remove `AssetCriticAgent` Reference**: Clean up the LangGraph routing logic to eliminate the passive audit phase (Phase 3.3).

### 2. Mermaid QA & Repair Loop (New)
- **Validation Layers**:
    - **Layer 1 (Syntax)**: Local regex/parser check to intercept broken Mermaid code.
    - **Layer 2 (Visual)**: Temporary render via Playwright -> Vision API audit against description.
- **Autonomous Repair**: Max 3 attempts using `original_intent`, `issues`, and `failed_code`.

### 3. SVG Loop implementation
- **Iterative Fulfillment**: Refactor `_fulfill_generate_svg_async` in `AssetFulfillmentAgent` to include a verify-and-fix cycle.
- **Repair Logic**: Utilize existing `repair_svg_async`, providing multimodal feedback.

### 4. Blocking Failure & HITL Escalation
- **State Enforcement**: If an asset fails its 3-repair limit, set a `state.asset_revision_needed` flag.
- **Workflow Interrupt**: LangGraph must detect this flag and trigger an interrupt.

## Acceptance Criteria
- [ ] Redundant Phase 3.3 removed.
- [ ] Mermaid charts verified for syntax and visual accuracy before injection.
- [ ] SVG generation autonomously retries upon VQA failure using visual feedback.
- [ ] Persistent failures successfully pause the workflow.
