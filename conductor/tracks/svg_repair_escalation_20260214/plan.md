# Implementation Plan: Robust SVG Repair Escalation Logic

This plan implements a multi-stage escalation strategy for SVG repairs, introducing rich feedback loops and a full-rewrite fallback to ensure 100% success rate in correcting scientific and visual issues.

## Phase 1: Foundation & Error Capture [ ]
- [ ] Task: Create reproduction test case for "Patch Matching Failure"
    - [ ] Create `tests/test_svg_patch_failure.py` that intentionally generates a mismatching patch.
    - [ ] Confirm the test fails as expected (Red Phase).
- [ ] Task: Enhance `apply_smart_patch` to return detailed error metadata
    - [ ] Modify `src/core/patcher.py` to return the specific reason for failure (e.g., "Search block not found").
    - [ ] Update unit tests to verify error reporting.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Foundation' (Protocol in workflow.md)

## Phase 2: Feedback Loop Implementation [ ]
- [ ] Task: Update `repair_svg_async` to manage the retry loop
    - [ ] Implement the 3-attempt loop logic in `src/agents/svg_generation/processor.py`.
    - [ ] Add state tracking for "Failed Patches" to include in subsequent prompts.
- [ ] Task: Implement Rich Feedback Prompting
    - [ ] Update `SVG_REPAIR_PROMPT` to accept error messages and previous failed attempts.
    - [ ] Ensure `rendered_image_b64` is passed in every retry iteration.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Feedback Loop' (Protocol in workflow.md)

## Phase 3: Fallback & Finalization [ ]
- [ ] Task: Implement "Full Rewrite" Fallback (Stage 3)
    - [ ] Add `full_code` field parsing logic to `repair_svg_async`.
    - [ ] Update prompt to explicitly demand full code if previous patching attempts failed twice.
- [ ] Task: Refactor and Clean up
    - [ ] Ensure all debug logs are professional and informative.
    - [ ] Verify that `SVGAgent` correctly handles the loop exit conditions.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Fallback' (Protocol in workflow.md)

## Phase 4: Final Verification [ ]
- [ ] Task: End-to-End Stress Test
    - [ ] Run `tests/test_svg_patch_failure.py` and verify it now succeeds via escalation.
    - [ ] Verify that the scientific audit score increases post-repair.
- [ ] Task: Verify Code Coverage (>80% for new logic)
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Verification' (Protocol in workflow.md)

## Phase: Review Fixes
- [x] Task: Apply review suggestions 90c962d
