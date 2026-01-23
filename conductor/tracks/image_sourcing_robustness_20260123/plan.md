# Implementation Plan: Image Sourcing Robustness

## Phase 1: Diagnosis & Instrumentation [checkpoint: 080cfcd]
- [x] Task: Instrument `ImageDownloader` for deep diagnosis (98bf02d)
    - [x] Write unit test to verify diagnostic logging capture
    - [x] Implement enhanced logging of response headers, status codes, and error types in `_download_single_requests`
- [x] Task: Conductor - User Manual Verification 'Phase 1: Diagnosis' (Protocol in workflow.md) (080cfcd)

## Phase 2: Hybrid Bypassing Implementation
- [ ] Task: Implement Domain-Aware Referer & Request Logic
    - [ ] Write unit tests for dynamic Referer generation
    - [ ] Update `_download_single_requests` to use domain-specific Referer and optimized header sets
- [ ] Task: Implement Browser-to-Session Credential Injection (Layer 2)
    - [ ] Write integration test for cookie/UA extraction from DrissionPage
    - [ ] Refine `download_candidates` Layer 2 to robustly inject browser state into the concurrent `requests.Session`
- [ ] Task: Implement Image Integrity Validation
    - [ ] Write unit tests for file type and size validation
    - [ ] Add post-download check to verify magic numbers and minimum file size (>2KB) to filter out block pages
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Hybrid Bypassing' (Protocol in workflow.md)

## Phase 3: Final Verification & E2E Stress Test
- [ ] Task: Run E2E Stress Test against high-failure domains
    - [ ] Execute `tests/debug_sota2_workflow.py` and verify 100% success rate for `SEARCH_WEB` actions
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Verification' (Protocol in workflow.md)
