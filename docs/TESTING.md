# Testing

## Deterministic suite

```bash
pytest -q -m "not integration"
```

This suite covers typed contracts, input safety, atomic state, locking, mutation
rollback, controlled subprocess environment, HTML safety, baseline comparison,
complete fake-executor publication, resume, and input invalidation.

## Browser evidence

```bash
python -m playwright install chromium
pytest -q tests/integration/test_browser_probe.py
```

## Credentialed Codex smoke

Set `OPENAI_API_KEY` or `CODEX_API_KEY`, then run:

```bash
pytest -q tests/integration/test_codex_smoke.py
```

GitHub Actions runs the browser contract on every change and exposes the Codex smoke
as an explicit manual workflow because it consumes a live credential and model quota.
