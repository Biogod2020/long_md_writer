import os
from pathlib import Path

import pytest

from src.orchestration.codex_runtime import OpenAICodexExecutor
from src.orchestration.models import CodexTaskSpec, StageName


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_codex_can_write_bounded_file(tmp_path: Path) -> None:
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("CODEX_API_KEY")):
        pytest.skip("credentialed Codex smoke test")
    executor = OpenAICodexExecutor(
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL", "gpt-5.6-luna"),
        codex_model=os.getenv("CODEX_MODEL", "gpt-5.3-codex"),
    )
    result = await executor.execute(CodexTaskSpec(
        task_id="smoke",
        stage=StageName.PLAN,
        workspace=tmp_path,
        prompt="Write exactly the text ok followed by a newline to result.txt, then return the structured result.",
        allowed_paths=["result.txt"],
        required_outputs=["result.txt"],
    ))
    assert result.status == "completed"
    assert (tmp_path / "result.txt").read_text() == "ok\n"
