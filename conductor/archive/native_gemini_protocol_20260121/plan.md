# Implementation Plan: Native Gemini Protocol Refactoring

## Phase 1: Native Client Core
- [x] Task: Create `tests/test_native_gemini_client.py` to define expected behavior for native payloads and response parsing.
- [x] Task: Implement Native Payload Builder in `src/core/gemini_client.py`.
    - [x] Support for `contents` and `parts` arrays.
    - [x] Support for `system_instruction` top-level field.
    - [x] Implementation of `inline_data` for raw Base64 bytes.
- [x] Task: Implement Native Response Parser.
    - [x] Extract and store `thought` tokens in `GeminiResponse.thoughts`.
    - [x] Handle `candidates` structure and multi-part text responses.
- [x] Task: Implement Resilience Layer.
    - [x] Configure persistent `httpx.AsyncClient` with custom limits.
    - [x] Implement exponential backoff for `RemoteProtocolError`.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Native Client Core' (Protocol in workflow.md)

## Phase 2: Agent & Logic Migration
- [x] Task: Update `ArchitectAgent` to use native JSON schema output.
- [x] Task: Update `WriterAgent` to use native multimodal parts for chapter-assigned imagery.
- [x] Task: Update `EditorialQAAgent` and `VisualQAAgent` to consume native responses.
- [~] Task: Update `AssetFulfillmentAgent` logic for SVG/Mermaid repair loops.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Agent & Logic Migration' (Protocol in workflow.md)

## Phase 3: High-Fidelity Audit & Stress Testing
- [x] Task: Refactor `src/agents/asset_management/processors/audit.py`.
    - [x] Remove resolution/context truncation.
    - [x] Update to send raw JPEG bytes via `inline_data`.
- [~] Task: Write `scripts/test_native_multimodal.py` to stress test高清图 + 全量上下文 payload.
- [ ] Task: Run all integration tests to verify protocol parity and stability.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: High-Fidelity Audit & Stress Testing' (Protocol in workflow.md)
