from pathlib import Path

import json
import pytest

from src.orchestration.models import JobState, WorkflowMode
from src.orchestration.state_store import JobLock, JobLockedError, StateStore


def test_state_store_atomic_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "job")
    state = JobState(job_id="job", workspace=str(tmp_path / "job"), mode=WorkflowMode.HTML, user_intent="x")
    store.save(state)
    loaded = store.load()
    assert loaded is not None and loaded.job_id == "job"
    store.append_event("test", value=1)
    event = json.loads(store.events_path.read_text().splitlines()[0])
    assert event["event"] == "test"


def test_job_lock_is_exclusive(tmp_path: Path) -> None:
    with JobLock(tmp_path, "same"):
        with pytest.raises(JobLockedError):
            with JobLock(tmp_path, "same"):
                pass
