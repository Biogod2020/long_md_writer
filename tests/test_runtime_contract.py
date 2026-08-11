from pathlib import Path

import os

from src.orchestration.codex_runtime import OpenAICodexExecutor


def test_controlled_codex_environment_excludes_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("MY_PRIVATE_TOKEN", "secret")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    env = OpenAICodexExecutor._controlled_environment(tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "MY_PRIVATE_TOKEN" not in env
    assert env["HOME"] == str(tmp_path)
    assert env["CODEX_HOME"].startswith(str(tmp_path))
