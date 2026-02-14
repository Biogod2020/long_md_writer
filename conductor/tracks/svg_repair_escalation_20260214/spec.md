# Specification: Robust SVG Repair Escalation Logic

## 1. Overview
Current SVG repair mechanism relies on high-precision JSON patches. However, AI-generated `search` strings often fail to match due to minor whitespace or formatting discrepancies. This track implements a multi-stage escalation strategy with detailed feedback loops to ensure 100% repair success.

## 2. Functional Requirements

### 2.1 Escalation Retry Loop
- **Stage 1 & 2 (Refined Patching)**: If a patch fails to apply, the system must capture the specific failure (e.g., "Search string not found") and feed it back to the AI.
- **Stage 3 (Full Rewrite Fallback)**: If Stage 2 also fails, the system must explicitly instruct the AI to provide the COMPLETE repaired SVG code in a `full_code` field.

### 2.2 Rich Feedback Payload
When a repair attempt fails, the next prompt to the AI must include:
1. **The Error Message**: Exact reason why the previous patch failed.
2. **The Failed Patch**: The specific `search` and `replace` blocks that caused the error.
3. **Current Source Code**: The full, immutable source of the current SVG.
4. **Visual Evidence**: A base64-encoded PNG rendering of the *current* (broken) state to help the AI visually locate the elements.

### 2.3 Success Handling
- Successfully applied patches (or full rewrite) must be persisted to the workspace.
- The system must exit the loop as soon as a valid SVG is produced and verified.

## 3. Non-Functional Requirements
- **Max Retries**: Strictly capped at 3 attempts to prevent token-drain and infinite loops.
- **Observability**: Every retry attempt and the specific reason for escalation must be logged in the console and debug traces.

## 4. Acceptance Criteria
- [ ] `SVGAgent.repair_svg_async` no longer returns `None` simply because a patch didn't match.
- [ ] The system can recover from a "Search string not found" error by successfully applying a revised patch or a full rewrite.
- [ ] VLM Auditor score increases after a successful escalation cycle.
- [ ] No infinite loops; system terminates with a result after max 3 retries.
