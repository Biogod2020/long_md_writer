"""Transactional filesystem boundaries for Codex workspace tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Iterable

from .models import CodexTaskResult


@dataclass(frozen=True)
class FileSnapshot:
    kind: str
    digest: str | None
    mode: int
    size: int


@dataclass
class MutationAudit:
    changed_files: list[str] = field(default_factory=list)
    unauthorized_files: list[str] = field(default_factory=list)
    restored_files: list[str] = field(default_factory=list)
    missing_outputs: list[str] = field(default_factory=list)
    symlinks: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.unauthorized_files and not self.missing_outputs and not self.symlinks


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(path: Path) -> FileSnapshot:
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if path.is_symlink():
        return FileSnapshot("symlink", os.readlink(path), mode, 0)
    if path.is_dir():
        return FileSnapshot("directory", None, mode, 0)
    if path.is_file():
        return FileSnapshot("file", _sha256(path), mode, info.st_size)
    return FileSnapshot("other", None, mode, info.st_size)


def _walk(workspace: Path) -> dict[str, FileSnapshot]:
    entries: dict[str, FileSnapshot] = {}
    if not workspace.exists():
        return entries
    for root, directories, files in os.walk(workspace, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in list(directories):
            path = root_path / name
            relative = path.relative_to(workspace).as_posix()
            entries[relative] = _snapshot(path)
            if path.is_symlink():
                directories.remove(name)
        for name in files:
            path = root_path / name
            relative = path.relative_to(workspace).as_posix()
            entries[relative] = _snapshot(path)
    return entries


def _matches(relative: str, rules: Iterable[str]) -> bool:
    value = relative.strip("/")
    for raw_rule in rules:
        rule = raw_rule.strip().strip("/")
        if not rule:
            continue
        if rule.endswith("/**"):
            prefix = rule[:-3].rstrip("/")
            if value == prefix or value.startswith(prefix + "/"):
                return True
        elif rule.endswith("/"):
            prefix = rule.rstrip("/")
            if value == prefix or value.startswith(prefix + "/"):
                return True
        elif fnmatch.fnmatchcase(value, rule):
            return True
        elif value == rule:
            return True
        elif rule.startswith(value + "/"):
            # Creating a parent directory is necessary for an allowed child path.
            return True
    return False


class WorkspaceMutationGuard:
    """Back up protected paths, audit changes, and roll back scope violations."""

    def __init__(self, workspace: Path, allowed_paths: Iterable[str]) -> None:
        self.workspace = workspace.resolve()
        self.allowed_paths = tuple(allowed_paths)
        self.before: dict[str, FileSnapshot] = {}
        self._backup_root: Path | None = None

    def __enter__(self) -> "WorkspaceMutationGuard":
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.before = _walk(self.workspace)
        self._backup_root = Path(tempfile.mkdtemp(prefix="magnum-guard-"))
        for relative, snapshot in self.before.items():
            if _matches(relative, self.allowed_paths):
                continue
            source = self.workspace / relative
            destination = self._backup_root / relative
            if snapshot.kind == "directory":
                destination.mkdir(parents=True, exist_ok=True)
            elif snapshot.kind == "file":
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination, follow_symlinks=False)
            elif snapshot.kind == "symlink":
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(os.readlink(source))
        return self

    def _remove(self, path: Path) -> None:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    def _restore(self, relative: str, snapshot: FileSnapshot) -> None:
        if self._backup_root is None:
            raise RuntimeError("guard was not entered")
        target = self.workspace / relative
        backup = self._backup_root / relative
        self._remove(target)
        if snapshot.kind == "directory":
            target.mkdir(parents=True, exist_ok=True)
            os.chmod(target, snapshot.mode)
        elif snapshot.kind == "file":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target, follow_symlinks=False)
            os.chmod(target, snapshot.mode)
        elif snapshot.kind == "symlink":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.readlink(backup))

    def finish(
        self,
        result: CodexTaskResult,
        required_outputs: Iterable[str] = (),
    ) -> tuple[CodexTaskResult, MutationAudit]:
        after = _walk(self.workspace)
        audit = MutationAudit()
        all_paths = sorted(set(self.before) | set(after))
        for relative in all_paths:
            old = self.before.get(relative)
            new = after.get(relative)
            if old == new:
                continue
            audit.changed_files.append(relative)
            if new is not None and new.kind == "symlink":
                audit.symlinks.append(relative)
            if _matches(relative, self.allowed_paths):
                continue
            audit.unauthorized_files.append(relative)
            if old is None:
                self._remove(self.workspace / relative)
                audit.restored_files.append(relative)
            else:
                self._restore(relative, old)
                audit.restored_files.append(relative)

        for relative in required_outputs:
            target = self.workspace / relative
            try:
                resolved = target.resolve(strict=True)
            except FileNotFoundError:
                audit.missing_outputs.append(relative)
                continue
            try:
                resolved.relative_to(self.workspace)
            except ValueError:
                audit.missing_outputs.append(relative)
                continue
            if target.is_symlink() or not target.is_file() or target.stat().st_size == 0:
                audit.missing_outputs.append(relative)

        if not audit.passed:
            result = result.model_copy(
                update={
                    "status": "failed",
                    "summary": result.summary + " Filesystem contract failed.",
                    "unresolved_issues": [
                        *result.unresolved_issues,
                        *(
                            ["unauthorized mutations: " + ", ".join(audit.unauthorized_files)]
                            if audit.unauthorized_files
                            else []
                        ),
                        *(
                            ["symlinks are forbidden: " + ", ".join(audit.symlinks)]
                            if audit.symlinks
                            else []
                        ),
                        *(
                            ["missing outputs: " + ", ".join(audit.missing_outputs)]
                            if audit.missing_outputs
                            else []
                        ),
                    ],
                }
            )
        result = result.model_copy(update={"changed_files": sorted(set(audit.changed_files))})
        self.cleanup()
        return result, audit

    def cleanup(self) -> None:
        if self._backup_root is not None:
            shutil.rmtree(self._backup_root, ignore_errors=True)
            self._backup_root = None

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            # Roll back every protected path even when the executor raises.
            after = _walk(self.workspace)
            for relative in sorted(set(self.before) | set(after)):
                if _matches(relative, self.allowed_paths):
                    continue
                old = self.before.get(relative)
                new = after.get(relative)
                if old == new:
                    continue
                if old is None:
                    self._remove(self.workspace / relative)
                else:
                    self._restore(relative, old)
        # ``finish`` normally owns cleanup; this covers exception paths.
        if exc_type is not None:
            self.cleanup()
