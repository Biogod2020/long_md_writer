# Implementation Plan: Resilient Asset Path Resolution

## Phase 1: Foundation & Absolute Path Logic
- [x] Task: Implement `get_project_root` utility
    - [x] Write unit test: `tests/test_path_utils.py` to verify root detection
    - [x] Implement `src/core/path_utils.py` with upward-search logic
- [x] Task: Enhance `AssetEntry` with absolute path property
    - [x] Write unit test: verify `entry.get_absolute_path(workspace_path)` correctly resolves different regions
    - [x] Update `src/core/types.py`: Add `get_absolute_path` method to `AssetEntry`
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Foundation' (Protocol in workflow.md)

## Phase 2: Refactoring to_img_tag
- [~] Task: Implement `to_img_tag` with relative path calculation
    - [ ] Write unit tests for `to_img_tag` with various target file locations (e.g., `md/sec-01.md`, `final.html`)
    - [ ] Implement `os.path.relpath` based logic in `AssetEntry.to_img_tag`
- [ ] Task: Implement Strict Existence Validation
    - [ ] Write unit tests: verify missing files trigger placeholder injection
    - [ ] Update `to_img_tag` to check `os.path.exists` and inject `<!-- ⚠️ FILE MISSING -->` on failure
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Path Refactoring' (Protocol in workflow.md)

## Phase 3: Integration & Stress Test
- [ ] Task: E2E Verification with deeply nested directories
    - [ ] Run `scripts/test_image_sourcing_scenarios.py` and verify image display in nested outputs
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Verification' (Protocol in workflow.md)
