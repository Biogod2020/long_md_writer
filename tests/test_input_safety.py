from pathlib import Path

import json
import os
import pytest

from src.orchestration.input_safety import materialize_inputs
from src.orchestration.models import WorkflowRequest


def test_materialize_inputs_is_immutable_and_deterministic(tmp_path: Path) -> None:
    reference = tmp_path / "reference.md"
    reference.write_text("source material", encoding="utf-8")
    workspace = tmp_path / "workspace"
    request = WorkflowRequest(
        user_intent="Create a rigorous guide",
        reference_files=[reference],
        inline_reference_materials="inline",
    )
    manifest, digest = materialize_inputs(request, workspace)
    assert len(digest) == 64
    assert manifest["references"][0]["path"].startswith("inputs/references/")
    loaded = json.loads((workspace / "inputs" / "manifest.json").read_text())
    assert loaded["user_intent"] == request.user_intent
    if os.name != "nt":
        assert not ((workspace / "inputs" / "request.md").stat().st_mode & 0o222)


def test_materialize_rejects_symlink_reference(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("source", encoding="utf-8")
    link = tmp_path / "link.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    request = WorkflowRequest(user_intent="write", reference_files=[link])
    with pytest.raises(ValueError, match="symbolic link"):
        materialize_inputs(request, tmp_path / "workspace")
