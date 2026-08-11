"""Input materialization and upload-name hardening."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import unicodedata
from typing import Iterable

from .models import WorkflowRequest

MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILENAME_BYTES = 180
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _truncate_utf8(value: str, byte_limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= byte_limit:
        return value
    truncated = encoded[:byte_limit]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return "file"


def safe_upload_name(raw_name: str, used: set[str], index: int) -> str:
    """Return a deterministic, collision-safe, filesystem-safe upload name."""

    name = unicodedata.normalize("NFKC", Path(raw_name).name).strip()
    name = name.replace("\x00", "")
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = f"file-{index}"

    suffixes = "".join(Path(name).suffixes)
    stem = name[: -len(suffixes)] if suffixes else name
    suffixes = _truncate_utf8(suffixes, 40)
    stem_budget = max(20, MAX_FILENAME_BYTES - len(suffixes.encode("utf-8")))
    stem = _truncate_utf8(stem, stem_budget).rstrip(" .") or f"file-{index}"
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"

    candidate = f"{stem}{suffixes}"
    key = candidate.casefold()
    counter = 2
    while key in used:
        tag = f"-{counter}"
        stem_budget = max(
            12,
            MAX_FILENAME_BYTES
            - len(suffixes.encode("utf-8"))
            - len(tag.encode("utf-8")),
        )
        candidate = f"{_truncate_utf8(stem, stem_budget)}{tag}{suffixes}"
        key = candidate.casefold()
        counter += 1
    used.add(key)
    return candidate


def sanitize_job_id(raw: str | None) -> str:
    if raw:
        value = unicodedata.normalize("NFKC", raw).strip()
        value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
        if value:
            return value[:80]
    from datetime import datetime, timezone

    return "job-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def _assert_regular_source(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"symbolic links are not accepted as inputs: {path}")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"input is not a regular file: {path}")
    size = resolved.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(f"input exceeds 100 MiB: {path}")
    return resolved


def _copy_regular_file(source: Path, destination: Path) -> dict[str, object]:
    resolved = _assert_regular_source(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("rb") as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
    destination.chmod(0o444)
    return {
        "name": destination.name,
        "path": destination.as_posix(),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def _iter_asset_files(root: Path) -> Iterable[Path]:
    if root.is_symlink():
        raise ValueError(f"assets directory may not be a symlink: {root}")
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError(f"assets path is not a directory: {root}")
    for path in sorted(resolved_root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"asset symlink rejected: {path}")
        if path.is_file():
            yield path


def materialize_inputs(request: WorkflowRequest, workspace: Path) -> tuple[dict[str, object], str]:
    """Copy the exact current request into an immutable workspace input tree."""

    inputs = workspace / "inputs"
    if inputs.exists():
        shutil.rmtree(inputs)
    references_dir = inputs / "references"
    assets_dir = inputs / "assets"
    references_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    manifest: dict[str, object] = {
        "schema_version": 2,
        "user_intent": request.user_intent,
        "mode": request.mode.value,
        "references": [],
        "assets": [],
    }

    request_path = inputs / "request.md"
    request_body = request.user_intent.strip() + "\n"
    if request.inline_reference_materials:
        request_body += "\n## Inline reference material\n\n"
        request_body += request.inline_reference_materials
        if not request_body.endswith("\n"):
            request_body += "\n"
    encoded = request_body.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("request and inline reference material exceed 100 MiB")
    request_path.write_bytes(encoded)
    request_path.chmod(0o444)
    total_bytes += len(encoded)
    manifest["request"] = {
        "path": "inputs/request.md",
        "bytes": len(encoded),
        "sha256": sha256_file(request_path),
    }

    used_reference_names: set[str] = set()
    reference_entries: list[dict[str, object]] = []
    for index, source in enumerate(request.reference_files, start=1):
        name = safe_upload_name(source.name, used_reference_names, index)
        entry = _copy_regular_file(source, references_dir / name)
        entry["path"] = f"inputs/references/{name}"
        total_bytes += int(entry["bytes"])
        reference_entries.append(entry)
    manifest["references"] = reference_entries

    asset_entries: list[dict[str, object]] = []
    if request.assets_dir is not None:
        used_asset_names: set[str] = set()
        assets_dir.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(_iter_asset_files(request.assets_dir), start=1):
            name = safe_upload_name(source.name, used_asset_names, index)
            entry = _copy_regular_file(source, assets_dir / name)
            entry["path"] = f"inputs/assets/{name}"
            total_bytes += int(entry["bytes"])
            asset_entries.append(entry)
    manifest["assets"] = asset_entries

    if total_bytes > MAX_TOTAL_BYTES:
        raise ValueError("combined inputs exceed 512 MiB")
    manifest["total_bytes"] = total_bytes

    manifest_path = inputs / "manifest.json"
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(payload, encoding="utf-8")
    manifest_path.chmod(0o444)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return manifest, digest


def restore_input_permissions(workspace: Path) -> None:
    inputs = workspace / "inputs"
    if not inputs.exists():
        return
    for path in inputs.rglob("*"):
        if path.is_file() and not path.is_symlink():
            try:
                os.chmod(path, 0o444)
            except OSError:
                pass
