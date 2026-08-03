"""Durable, atomic state and event persistence for publication jobs."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any

from .models import JobState


class JobLockedError(RuntimeError):
    pass


class JobLock(AbstractContextManager["JobLock"]):
    """Cross-process lock stored outside the disposable job workspace."""

    def __init__(self, output_base: Path, job_id: str) -> None:
        self.lock_dir = output_base.resolve() / ".magnum-locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.lock_dir / f"{job_id}.lock"
        self._handle: Any | None = None

    def __enter__(self) -> "JobLock":
        self._handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            self._handle.close()
            self._handle = None
            raise JobLockedError(f"job is already running: {self.path.stem}") from exc
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                }
            ).encode("utf-8")
        )
        self._handle.flush()
        os.fsync(self._handle.fileno())
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


class StateStore:
    """Owns the control-plane files under ``workspace/.magnum``."""

    _event_lock = threading.Lock()

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.control_dir = self.workspace / ".magnum"
        self.results_dir = self.control_dir / "stage_results"
        self.reports_dir = self.control_dir / "quality_reports"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.control_dir / "job.json"
        self.events_path = self.control_dir / "events.jsonl"

    @staticmethod
    def atomic_write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp_path = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def atomic_write_json(path: Path, payload: Any) -> None:
        StateStore.atomic_write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def load(self) -> JobState | None:
        if not self.state_path.is_file():
            return None
        return JobState.model_validate_json(self.state_path.read_text(encoding="utf-8"))

    def save(self, state: JobState) -> None:
        state.updated_at = datetime.now(timezone.utc)
        self.atomic_write_json(self.state_path, state.model_dump(mode="json"))

    def append_event(self, event: str, **data: Any) -> None:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        }
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self._event_lock:
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    def stage_result_path(self, stage: str, attempt: int, task_id: str) -> Path:
        safe_task = "".join(
            character if character.isalnum() or character in "-_." else "-"
            for character in task_id
        )[:100]
        return self.results_dir / f"{stage}-attempt-{attempt:02d}-{safe_task}.json"

    def quality_report_path(self, stage: str, attempt: int) -> Path:
        return self.reports_dir / f"{stage}-attempt-{attempt:02d}.json"
