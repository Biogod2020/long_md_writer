# Plan: Render-Aware Full-Context Editorial QA

This plan follows the TDD and verification protocols defined in `conductor/workflow.md`.

## Phase 1: Infrastructure & Render Simulation

- [x] Task: Create a mock renderer for Editorial QA tests (simulating Playwright output) 5d8203b
- [x] Task: Implement full-context text gathering utility (merging preceding chapters) 0ac551b
- [~] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure & Render Simulation' (Protocol in workflow.md)

## Phase 2: Render-Aware Critic Upgrade

- [ ] Task: Write tests for visual audit (identifying crop mismatches in rendered images)
- [ ] Task: Upgrade `EditorialCritic` to accept visual inputs (screenshots)
- [ ] Task: Write tests for full-context semantic consistency
- [ ] Task: Upgrade `EditorialCritic` to process full preceding text
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Render-Aware Critic Upgrade' (Protocol in workflow.md)

## Phase 3: Editorial Fixer Implementation

- [ ] Task: Write tests for `EditorialFixer` surgical patching
- [ ] Task: Implement `EditorialFixer` (Search/Replace logic for semantic fixes)
- [ ] Task: Integrate Critic and Fixer into a closed loop in `EditorialQAAgent`
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Editorial Fixer Implementation' (Protocol in workflow.md)

## Phase 4: Integration & SOTA Verification

- [ ] Task: End-to-end test: Audit a section with a "broken" crop and "wrong" term, verify auto-fix
- [ ] Task: Performance optimization for full-context injection
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Integration & SOTA Verification' (Protocol in workflow.md)
