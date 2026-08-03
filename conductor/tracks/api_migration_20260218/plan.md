# Implementation Plan: API Provider Migration (geminicli2api -> AIClient-2-API)

## Phase 1: Environment & Test Scaffolding (Red Phase)
- [x] Task: Create a failing smoke test `scripts/test_aiclient_migration.py`
    - [ ] Define expected connectivity to `http://localhost:3000`
    - [ ] Verify that it fails under current configuration
- [x] Task: Update environment templates
    - [ ] Modify `.env.example` to reflect the new default port (3000)
    - [ ] Add `MODEL_PROVIDER` instructions for AIClient-2-API
- [x] Task: Conductor - User Manual Verification 'Environment & Test Scaffolding' (Protocol in workflow.md)

## Phase 2: Core Client Adaptation (Green Phase)
- [x] Task: Adapt `GeminiClient` configuration
    - [x] Update `DEFAULT_BASE_URL` in `src/core/gemini_client.py` to `http://localhost:3000`
    - [x] Create centralized config `src/core/config.py`
    - [x] Remove non-standard `maxthinking` suffixes and logic
    - [x] Implement standard `thinkingLevel` injection logic (default HIGH for Gemini 3)
    - [x] Ensure `responseModalities: ["TEXT"]` is added for thinking-enabled requests
- [x] Task: Verify Authentication Compatibility
    - [x] Confirm Bearer token format matches AIClient-2-API security requirements
    - [x] Run the migration smoke test and confirm it passes (Green)
- [x] Task: Conductor - User Manual Verification 'Core Client Adaptation' (Protocol in workflow.md)

## Phase 3: SOTA 2.0 Pipeline Validation
- [~] Task: Execute Full E2E Verification
    - [ ] Run `tests/verification_v13.py` using the new API provider
    - [x] Verify that "thinking" tokens are correctly captured in logs
    - [x] Confirm successful asset fulfillment (SVG/Web/Mermaid) via AIClient-2-API
- [x] Task: Audit Log Consistency
    - [x] Check `editorial_qa_logs` to ensure global gatekeeper logic remains intact
    - [x] Verify that Caption Refinement logic functions correctly
- [x] Task: Conductor - User Manual Verification 'SOTA 2.0 Pipeline Validation' (Protocol in workflow.md)

## Phase 4: Finalization & Documentation
- [x] Task: Update Setup Documentation
    - [x] Create/Update a guide for setting up AIClient-2-API locally
    - [x] Document the transition from legacy 8888 port to 3000
- [x] Task: Final Cleanup
    - [x] Remove any leftover hardcoded references to `8888` in scripts
    - [x] Perform a final self-review of network resilience logic (retries/backoff)
- [x] Task: Conductor - User Manual Verification 'Finalization & Documentation' (Protocol in workflow.md)
