"""Simple latest-backup support for the active compact graph."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..graph import validate


GRAPH_FILES = ("ontology.jsonl", "source-index.json", "cache-manifest.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_files(root: Path, label: str) -> None:
    missing = [name for name in GRAPH_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError(f"{label} is incomplete: missing {missing}")


def _validate_graph_root(root: Path) -> None:
    try:
        json.loads((root / "source-index.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "cache-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"graph metadata is invalid: {exc}") from exc
    if manifest.get("schema") != "labontology.workspace-cache.v1":
        raise ValueError("graph metadata has an unsupported cache schema")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = validate(system_dir=root)
    if result != 0:
        raise ValueError("graph validation failed")


def backup_active_graph(cache_dir: Path, reason: str) -> dict[str, Any]:
    cache = Path(cache_dir).resolve()
    _require_files(cache, "active graph")
    backup = cache / ".backup"
    staging = cache.parent / f".{cache.name}-backup-build"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        files = {}
        for name in GRAPH_FILES:
            source = cache / name
            destination = staging / name
            shutil.copy2(source, destination)
            files[name] = {"path": name, "sha256": _sha256(destination),
                           "size_bytes": destination.stat().st_size}
        if backup.exists():
            if backup.is_dir():
                shutil.rmtree(backup)
            else:
                backup.unlink()
        staging.replace(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "backup_dir": str(backup),
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


def restore_active_graph(cache_dir: Path) -> dict[str, Any]:
    cache = Path(cache_dir).resolve()
    backup = cache / ".backup"
    _require_files(backup, "incomplete backup")
    staging = cache.parent / f".{cache.name}-restore-build"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for name in GRAPH_FILES:
            shutil.copy2(backup / name, staging / name)
        _validate_graph_root(staging)
        for name in GRAPH_FILES:
            replacement = cache.parent / f".{cache.name}-{name}.restore"
            if replacement.exists():
                replacement.unlink()
            shutil.copy2(staging / name, replacement)
            replacement.replace(cache / name)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    return {"cache_dir": str(cache), "restored": sorted(GRAPH_FILES)}
