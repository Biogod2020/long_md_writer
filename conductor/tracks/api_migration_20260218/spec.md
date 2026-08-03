# Track Specification: API Provider Migration (geminicli2api -> AIClient-2-API)

## Overview
This track involves migrating the core LLM communication layer from the legacy `geminicli2api` proxy to the more robust and community-maintained `AIClient-2-API` project. The goal is to leverage advanced features like multi-account load balancing and improved error handling while maintaining the performance of the current Gemini Native protocol implementation.

## Motivation
- **Reliability**: Utilize AIClient-2-API's superior polling and automatic failover mechanisms.
- **Scalability**: Enable multi-account polling to effectively bypass per-account rate limits during high-concurrency E2E tests.
- **Sustainability**: Move to a project with broader community support and more frequent updates.
- **Standardization**: Align the local development environment with OpenAI-compatible infrastructure standards.

## Functional Requirements
- **Endpoint Adaptation**: Update the default `GeminiClient` base URL from `http://localhost:8888` to `http://localhost:3000`.
- **Model Name Standardization**: Refactor `GeminiClient` to strip non-standard suffixes (e.g., `-maxthinking`, `-thinking`) before sending requests to the API, ensuring compatibility with standard proxies like AIClient-2-API.
- **Explicit Thinking Configuration**: Automatically inject `thinkingConfig` (including `thinkingLevel` or `thinkingBudget`) and `responseModalities: ["TEXT"]` based on the requested model variant.
- **Protocol Preservation**: Maintain the existing Gemini Native protocol implementation (`/v1beta/models/...`) to preserve "thinking" token capture and SSE stream parsing logic.
- **Auth Compatibility**: Ensure Bearer token handling remains compatible with AIClient-2-API's security requirements.

## Non-Functional Requirements
- **Zero Regression**: Existing E2E tests (specifically `verification_v13.py`) must pass with the new provider without code changes to the agent logic.
- **Transparency**: Update the Dashboard and CLI logs to clearly indicate when the system is communicating via AIClient-2-API.

## Acceptance Criteria
- [ ] `src/core/gemini_client.py` defaults to `http://localhost:3000`.
- [ ] A dedicated smoke test (`scripts/test_aiclient_migration.py`) confirms successful round-trip communication.
- [ ] `tests/verification_v13.py` completes a full SOTA 2.0 pipeline run successfully using the new provider.
- [ ] Documentation updated to include AIClient-2-API setup steps.

## Out of Scope
- Refactoring the client to use the OpenAI protocol (decided to stick with Native for stability).
- Migrating non-Gemini providers (e.g., Anthropic) unless they are already configured via the proxy.
