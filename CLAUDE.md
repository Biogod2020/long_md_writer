# Claude Code guidance

Read `AGENTS.md` and `docs/ARCHITECTURE.md` before modifying the repository.
The active runtime is OpenAI Agents SDK + Codex, not LangGraph. Preserve the
staging-workspace boundary and deterministic acceptance model. Run:

```bash
python -m compileall -q src scripts tests
pytest -q -m "not integration"
```
