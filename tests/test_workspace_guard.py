from pathlib import Path

import pytest

from src.orchestration.models import CodexTaskResult
from src.orchestration.workspace_guard import WorkspaceMutationGuard


def _result() -> CodexTaskResult:
    return CodexTaskResult(status="completed", summary="done")


def test_guard_restores_unauthorized_mutation(tmp_path: Path) -> None:
    protected = tmp_path / "inputs" / "request.md"
    protected.parent.mkdir()
    protected.write_text("original")
    with WorkspaceMutationGuard(tmp_path, ["output.md"]) as guard:
        protected.write_text("tampered")
        (tmp_path / "output.md").write_text("ok")
        result, audit = guard.finish(_result(), ["output.md"])
    assert result.status == "failed"
    assert protected.read_text() == "original"
    assert "inputs/request.md" in audit.unauthorized_files


def test_guard_rejects_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("target")
    with WorkspaceMutationGuard(tmp_path, ["out/**"]) as guard:
        out = tmp_path / "out"
        out.mkdir()
        try:
            (out / "link").symlink_to(target)
        except OSError:
            pytest.skip("symlinks unavailable")
        result, audit = guard.finish(_result())
    assert result.status == "failed"
    assert audit.symlinks
