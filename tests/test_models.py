from pathlib import Path

import pytest
from pydantic import ValidationError

from src.orchestration.input_safety import safe_upload_name, sanitize_job_id
from src.orchestration.models import PublicationPlan, WorkflowRequest


def test_publication_plan_rejects_duplicate_sections() -> None:
    payload = {
        "project_title": "Test",
        "audience": "Researchers",
        "objectives": ["Explain"],
        "sections": [
            {"id": "same", "title": "A", "objective": "A", "estimated_words": 200},
            {"id": "same", "title": "B", "objective": "B", "estimated_words": 200},
        ],
    }
    with pytest.raises(ValidationError):
        PublicationPlan.model_validate(payload)


def test_safe_upload_name_preserves_extension_and_resolves_collisions() -> None:
    used: set[str] = set()
    first = safe_upload_name("../A very long reference 文档.md", used, 1)
    second = safe_upload_name("A very long reference 文档.md", used, 2)
    assert first.endswith(".md")
    assert second.endswith(".md")
    assert first.casefold() != second.casefold()
    assert "/" not in first and "\\" not in first


def test_job_id_is_filesystem_safe() -> None:
    assert sanitize_job_id("../../My Job") == "My-Job"
    assert len(sanitize_job_id("x" * 500)) <= 80


def test_request_rejects_missing_reference(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        WorkflowRequest(user_intent="write", reference_files=[tmp_path / "missing.md"])
