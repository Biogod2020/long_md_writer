# Implementation Plan: Universal High-Precision Patcher & QA Loop Hardening

## Phase 1: Foundation & Core Utility
- [x] Task: Environment Setup - Install `diff-match-patch`
- [x] Task: Write Tests for Universal Patcher (Fuzzy matching, Indentation normalization)
- [x] Task: Implement `src/core/patcher.py`
    - [x] Implement `FuzzyMatcher` using `diff-match-patch`
    - [x] Implement `IndentationNormalizer` (Relative indentation logic)
    - [x] Implement `apply_smart_patch` core function
- [x] Task: Conductor - User Manual Verification 'Phase 1: Foundation' (Protocol in workflow.md)

## Phase 2: QA Loop Hardening Logic
- [x] Task: Write Tests for Stuck Detection and Backoff Strategy
- [x] Task: Implement `StuckDetector` utility (Content hashing logic)
- [x] Task: Update Agent Loop logic in `src/agents/editorial_qa_agent.py` to support Backoff & Retry
- [x] Task: Update Agent Loop logic in `src/agents/visual_qa/agent.py` to support Backoff & Retry
- [x] Task: Conductor - User Manual Verification 'Phase 2: QA Loop Hardening' (Protocol in workflow.md)

## Phase 3: System-Wide Migration
- [x] Task: Refactor `src/agents/markdown_qa/fixer.py` to use Universal Patcher
- [x] Task: Refactor `src/agents/visual_qa/fixer.py` to use Universal Patcher
- [x] Task: Refactor `src/agents/asset_management/fulfillment.py` (SVG/Mermaid repair) to use Universal Patcher
- [x] Task: Refactor `src/agents/assembler_agent.py` to use Universal Patcher
- [x] Task: Conductor - User Manual Verification 'Phase 3: System-Wide Migration' (Protocol in workflow.md)

## Phase 4: Validation & Stress Testing
- [x] Task: Write E2E Stress Test for "Indentation Discrepancy" scenario (fc04bd8)
- [x] Task: Run `scripts/test_full_workflow_repair.py` and verify zero "stuck" regressions (fc04bd8)
- [x] Task: Run full project build and linting checks (455d6a5)
- [x] Task: Conductor - User Manual Verification 'Phase 4: Validation' (Protocol in workflow.md) (455d6a5)

## Phase 5: Extreme Refinement & Integration
- [x] Task: Clean up debug print statements in `src/core/patcher.py` and convert to logging.
- [x] Task: Refactor `src/agents/asset_management/fulfillment.py` to completely replace legacy regex patching with `apply_smart_patch`.
- [x] Task: Integrate and run `tests/extreme_stress_test_patcher.py` to verify extreme fuzzy drift and large payload scenarios.
- [x] Task: Conductor - User Manual Verification 'Phase 5: Extreme Refinement' (Protocol in workflow.md)
