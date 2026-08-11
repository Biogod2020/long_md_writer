# Repository operating contract

## Architecture

- `src/orchestration/openai_workflow.py` is the deterministic control plane.
- `src/orchestration/codex_runtime.py` is the only module allowed to import the
  experimental Codex extension.
- Models do not decide acceptance. `quality.py`, `workspace_guard.py`, and
  `browser_probe.py` are authoritative.
- Canonical workspace state lives in `.magnum/job.json`; generated artifacts remain
  ordinary files.

## Change rules

1. Never reintroduce LangGraph or model-generated search/replace patch protocols.
2. Never let a Codex task write directly into the canonical job workspace.
3. Keep agent task scope explicit: allowed paths, required outputs, network policy,
   reasoning effort, and timeout.
4. Do not weaken browser hash binding, asset provenance checks, path containment,
   symlink rejection, input immutability, or baseline gates.
5. Add deterministic tests for every recovery, mutation, or quality-gate change.
6. Keep the real Codex test opt-in; unit tests must not require credentials.
