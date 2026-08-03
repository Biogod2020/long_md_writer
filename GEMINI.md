# Gemini CLI guidance

Read `AGENTS.md`. The production workflow no longer uses the legacy Gemini client.
Do not add provider-specific logic to the control plane. Any future provider adapter
must implement `TaskExecutor` and remain isolated from state, quality gates, and
artifact promotion.
