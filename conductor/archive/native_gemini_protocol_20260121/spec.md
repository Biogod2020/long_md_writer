# Specification: Native Gemini Protocol Refactoring

## Overview
This track involves a fundamental shift in the system's communication layer, moving from OpenAI-compatible endpoints to Google's Native Gemini API protocol. This change is driven by the need for better stability in multimodal transfers (resolving `RemoteProtocolError`), native support for thinking tokens (thoughts), and more reliable structured JSON output for core planning agents.

## Functional Requirements
1.  **Native Gemini Client (`src/core/gemini_client.py`)**:
    *   Switch endpoints from `/v1/chat/completions` to `/v1beta/models/{model}:generateContent` and `:streamGenerateContent`.
    *   Implement `contents` and `parts` array structures for request payloads.
    *   Migrate system prompts to the native `system_instruction` top-level field.
    *   Implement `inline_data` for multimodal inputs, sending raw Base64 bytes (no `data:` URI prefix).
    *   Set `gemini-3-flash-preview-maxthinking` as the default model.
2.  **Response Handling**:
    *   Update `GeminiResponse` to explicitly capture and store thinking tokens in a `thoughts` field.
    *   Implement robust parsing for `response_mime_type: "application/json"` to ensure stable structured output for Architect and QA agents.
3.  **Stability & Resilience**:
    *   Maintain a persistent `httpx.AsyncClient` connection pool.
    *   Implement intelligent exponential backoff for `RemoteProtocolError` and `ReadTimeout`.
4.  **Agent Migration**:
    *   Update all agents (Architect, Writer, EditorialQA, VisualQA, etc.) to produce native parts and consume the updated `GeminiResponse` structure.
5.  **High-Fidelity Audit**:
    *   Update `src/agents/asset_management/processors/audit.py` to send full-resolution images without truncation, utilizing the more stable native transport.

## Non-Functional Requirements
*   **Protocol Purity**: Zero dependency on OpenAI-style translation layers within the proxy.
*   **Performance**: Reduced latency by removing secondary format conversion on the proxy side.

## Acceptance Criteria
*   Successfully perform a full multimodal audit loop using the native protocol.
*   Thinking tokens are correctly extracted and logged in `AgentState`.
*   Zero `RemoteProtocolError` occurrences during high-payload SVG auditing tests.
*   All existing integration tests pass using the new Native Client.

## Out of Scope
*   Updating the proxy server implementation itself (assumes `/v1beta/` endpoints are already available).
