# Implementation Plan: Repository Tidy-Up

## Phase 1: Analysis & Documentation Relocation [checkpoint: 9683f36]
- [x] Task: Analyze root-level files for relocation (c8369ad)
    - [x] Read and categorize all files in the root directory (excluding preserved ones: TODOs, requirements, configs).
    - [x] Determine the most appropriate target directory based on content and purpose.
- [x] Task: Relocate technical planning and roadmap documents (c8369ad)
    - [x] Move `SOTA_Upgrade_Plan_Detailed.md`, `omnimind_project.md`, `AGENTS.md` to `docs/archive/` or `docs/` as appropriate.
- [x] Task: Relocate ephemeral artifacts and raw outputs (c8369ad)
    - [x] Move `.log` files, `.out` files, and `architect_raw_response.txt` to a new `data/logs_and_artifacts/` directory.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Analysis & Documentation' (Protocol in workflow.md) (9683f36)

## Phase 2: Codebase Organization
- [ ] Task: Analyze and relocate entry-point scripts to `scripts/`
    - [ ] Read `main.py`, `main_markdown.py`, `app.py` to identify hardcoded paths or dependency assumptions.
    - [ ] Move them to `scripts/`.
    - [ ] Inject `sys.path` adjustments or update internal imports to ensure they still work from the new location.
- [ ] Task: Analyze and relocate root-level test files to `tests/`
    - [ ] Read `test_architect.py` and other root tests.
    - [ ] Move to `tests/`.
    - [ ] Verify test discovery and execution still works.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Codebase' (Protocol in workflow.md)

## Phase 3: Final Sweep & Verification
- [ ] Task: Verify project root cleanliness
    - [ ] Confirm only essential config files (`.gitignore`, `requirements.txt`, etc.) and preserved TODOs remain.
- [ ] Task: Verify original functions
    - [ ] Run a smoke test for `scripts/main.py` and `scripts/main_markdown.py` to ensure they execute correctly.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Sweep' (Protocol in workflow.md)
