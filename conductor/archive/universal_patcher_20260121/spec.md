# Specification: Universal High-Precision Patcher & QA Loop Hardening

## Overview
This track aims to resolve the "getting stuck" bug in SOTA 2.0 QA loops by replacing brittle exact-match logic with a robust, fuzzy-matching Universal Patcher. It also hardens the workflow by implementing "Stuck Detection" and a "Backoff & Retry" strategy for failed fixes.

## Functional Requirements
1.  **Universal High-Precision Patcher**:
    *   Create a centralized utility in `src/core/patcher.py`.
    *   Integrate **`diff-match-patch`** for fuzzy text matching (80%+ similarity threshold).
    *   Implement **Indentation-Agnostic Matching**: Normalize leading whitespace in `SEARCH` blocks while preserving target file indentation style in `REPLACE` blocks.
2.  **QA Loop Hardening**:
    *   **Stuck Detection**: Implement content hashing before and after patch application. If the hash remains identical after a "successful" fix, mark the fix as effectively failed.
    *   **Backoff & Retry Logic**: If a fix fails or results in a collision, trigger one additional attempt with an "Enhanced Context" prompt before escalating to a human interrupt.
3.  **System-Wide Migration**:
    *   Refactor all components using search-replace logic to use the new Patcher, including `EditorialQAAgent`, `VisualQAAgent`, `AssetFulfillmentAgent` (for SVG/Mermaid repairs), and `AssemblerAgent`.

## Non-Functional Requirements
*   **Resilience**: The system must remain stable even when the LLM produces minor discrepancies in whitespace, newlines, or line endings.
*   **Observability**: Log detailed reasons for patch failures (e.g., "Similarity too low", "Ambiguous match", "No change in content").

## Acceptance Criteria
*   The Patcher successfully applies changes to files where the search block has different indentation than the raw file.
*   The system detects identical content hashes after a patch and triggers the retry mechanism.
*   The "getting stuck" infinite loop issue is no longer reproducible in `test_full_workflow_repair.py`.

## Out of Scope
*   Migrating entire-file-regeneration logic (like the primary `WriterAgent`) to patching.
*   Changing the underlying LangGraph topology (beyond existing interrupt nodes).
