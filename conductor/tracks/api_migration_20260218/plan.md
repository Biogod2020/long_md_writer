# Implementation Plan: API Provider Migration (geminicli2api -> AIClient-2-API)

## Phase 1: Environment & Test Scaffolding (Red Phase)
- [ ] Task: Create a failing smoke test `scripts/test_aiclient_migration.py`
    - [ ] Define expected connectivity to `http://localhost:3000`
    - [ ] Verify that it fails under current configuration
- [ ] Task: Update environment templates
    - [ ] Modify `.env.example` to reflect the new default port (3000)
    - [ ] Add `MODEL_PROVIDER` instructions for AIClient-2-API
- [ ] Task: Conductor - User Manual Verification 'Environment & Test Scaffolding' (Protocol in workflow.md)

## Phase 2: Core Client Adaptation (Green Phase)
- [ ] Task: Adapt `GeminiClient` configuration
    - [ ] Update `DEFAULT_BASE_URL` in `src/core/gemini_client.py` to `http://localhost:3000`
    - [ ] Ensure Port 8888 -> 3000 mapping is consistent throughout the class
- [ ] Task: Verify Authentication Compatibility
    - [ ] Confirm Bearer token format matches AIClient-2-API security requirements
    - [ ] Run the migration smoke test and confirm it passes (Green)
- [ ] Task: Conductor - User Manual Verification 'Core Client Adaptation' (Protocol in workflow.md)

## Phase 3: SOTA 2.0 Pipeline Validation
- [ ] Task: Execute Full E2E Verification
    - [ ] Run `tests/verification_v13.py` using the new API provider
    - [ ] Verify that "thinking" tokens are correctly captured in logs
    - [ ] Confirm successful asset fulfillment (SVG/Web/Mermaid) via AIClient-2-API
- [ ] Task: Audit Log Consistency
    - [ ] Check `editorial_qa_logs` to ensure global gatekeeper logic remains intact
    - [ ] Verify that Caption Refinement logic functions correctly
- [ ] Task: Conductor - User Manual Verification 'SOTA 2.0 Pipeline Validation' (Protocol in workflow.md)

## Phase 4: Finalization & Documentation
- [ ] Task: Update Setup Documentation
    - [ ] Create/Update a guide for setting up AIClient-2-API locally
    - [ ] Document the transition from legacy 8888 port to 3000
- [ ] Task: Final Cleanup
    - [ ] Remove any leftover hardcoded references to `8888` in scripts
    - [ ] Perform a final self-review of network resilience logic (retries/backoff)
- [ ] Task: Conductor - User Manual Verification 'Finalization & Documentation' (Protocol in workflow.md)
