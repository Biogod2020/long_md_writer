# Plan: Render-Aware Full-Context Editorial QA

This plan follows the TDD and verification protocols defined in `conductor/workflow.md`.

## Phase 1: Infrastructure ## Phase 1: Infrastructure & Render Simulation Render Simulation [checkpoint: ed88f92]

- [x] Task: Create a mock renderer for Editorial QA tests (simulating Playwright output) 5d8203b
- [x] Task: Implement full-context text gathering utility (merging preceding chapters) 0ac551b
- [x] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure - [~] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure & Render Simulation' (Protocol in workflow.md) Render Simulation' (Protocol in workflow.md) ed88f92

## Phase 2: Render-Aware Critic Upgrade

- [x] Task: Write tests for visual audit (identifying crop mismatches in rendered images) 81e9481
- [x] Task: Upgrade `EditorialCritic` to accept visual inputs (screenshots) 81e9481
- [x] Task: Write tests for full-context semantic consistency 81e9481
- [x] Task: Upgrade `EditorialCritic` to process full preceding text 81e9481
- [~] Task: Conductor - User Manual Verification 'Phase 2: Render-Aware Critic Upgrade' (Protocol in workflow.md)

## Phase 3: Editorial Fixer Implementation [checkpoint: 9b993ad]

- [x] Task: Write tests for `EditorialFixer` surgical patching edc25a7
- [x] Task: Implement `EditorialFixer` (Search/Replace logic for semantic fixes) edc25a7
- [x] Task: Integrate Critic and Fixer into a closed loop in `EditorialQAAgent` edc25a7
- [x] Task: Conductor - User Manual Verification 'Phase 3: Editorial Fixer Implementation' (Protocol in workflow.md) 9b993ad

## Phase 4: Integration & SOTA Verification

- [~] Task: End-to-end test: Audit a section with a "broken" crop and "wrong" term, verify auto-fix
- [~] Task: Performance optimization for full-context injection
- [~] Task: Conductor - User Manual Verification 'Phase 4: Integration & SOTA Verification' (Protocol in workflow.md)
