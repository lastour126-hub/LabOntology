"""Export discovered Skill data into a portable ontology intake bundle."""
from __future__ import annotations

import json
from pathlib import Path

from .discovery import discover_tree


def _copy_directory(source: Path | None, destination: Path) -> None:
    if not source or not source.exists():
        return
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def export_bundle(
    root: Path,
    output_dir: Path,
    suite_id: str,
    device_knowledge: Path | None = None,
    workflows: Path | None = None,
    include_skill_ids: set[str] | None = None,
    exclude_skill_dirs: set[Path] | None = None,
) -> Path:
    """Write a portable, non-executable bundle for ontology intake."""
    skills = discover_tree(root, exclude_skill_dirs=exclude_skill_dirs)
    if include_skill_ids is not None:
        skills = [skill for skill in skills if str(skill.get("id")) in include_skill_ids]
    for skill in skills:
        skill["status"] = "draft"
    bundle = {
        "schema": "labontology.skill-bundle.v1",
        "suite_id": suite_id,
        "skills": skills,
        "device_knowledge": [],
        "workflows": [],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_dir = output_dir / "Knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    for skill in skills:
        source_dir = Path(skill["source_dir"])
        destination = knowledge_dir / skill["id"].split(":", 1)[-1]
        for relative in skill.get("knowledge_files", []):
            source = source_dir / relative["path"]
            if not source.exists():
                continue
            target = destination / relative["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    (output_dir / "DeviceKnowledge").mkdir(exist_ok=True)
    (output_dir / "Workflow").mkdir(exist_ok=True)
    _copy_directory(device_knowledge, output_dir / "DeviceKnowledge")
    _copy_directory(workflows, output_dir / "Workflow")
    (output_dir / "skills.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output_dir
