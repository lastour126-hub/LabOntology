from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Sequence
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
for component in (PROJECT_ROOT / "labontology-creator", PROJECT_ROOT / "labontology-run"):
    if str(component) not in sys.path:
        sys.path.insert(0, str(component))

from data_manager.importer import export_bundle
from data_manager.intake import receive_bundle
from runtime import commands as runtime_commands
from runtime.registry import Registry


def _ontology_module():
    path = PROJECT_ROOT / "labontology-run" / "scripts" / "ontology.py"
    spec = importlib.util.spec_from_file_location("labontology_runtime_ontology", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load ontology helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ONTOLOGY = _ontology_module()


def import_suite(skill_root: Path, suite_id: str, workspace: Path) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    with TemporaryDirectory(prefix="labontology-bundle-") as temporary:
        bundle_dir = Path(temporary)
        export_bundle(skill_root, bundle_dir, suite_id)
        imported = receive_bundle(bundle_dir, workspace)

    cache_dir = Path(imported["output_dir"])
    validation_output = io.StringIO()
    with contextlib.redirect_stdout(validation_output):
        valid = ONTOLOGY.validate(system_dir=cache_dir) == 0
    if not valid:
        raise ValueError(validation_output.getvalue().strip() or "Imported graph is invalid")
    entities, _ = ONTOLOGY.load_graph(cache_dir / "ontology.jsonl")
    if not any(entity.get("type") == "SkillSuite" for entity in entities.values()):
        raise ValueError("Imported graph contains no SkillSuite")
    return {
        "suite_id": imported["suite_id"],
        "cache_dir": str(cache_dir),
        "skill_count": sum(entity.get("type") == "Skill" for entity in entities.values()),
        "validation": {"graphs": 1, "valid": True},
    }


def inspect_cache(cache_dir: Path) -> dict[str, Any]:
    cache_dir = cache_dir.resolve()
    registry = Registry.load_cache(cache_dir)
    if len(registry.suites) != 1:
        raise ValueError("Release inspection requires exactly one suite per cache")
    suite = next(iter(registry.suites.values()))
    entities, relations = ONTOLOGY.load_graph(cache_dir / "ontology.jsonl")
    index = json.loads((cache_dir / "source-index.json").read_text(encoding="utf-8"))
    sources = index.get("sources", [])
    missing = sum(not Path(record["path"]).is_file() for record in sources if record.get("path"))
    return {
        "suite_id": suite.id,
        "skill_count": len(suite.skills),
        "capabilities": sorted(suite.available_capabilities),
        "graph": {"entities": len(entities), "relations": len(relations)},
        "source_integrity": {"records": len(sources), "missing": missing},
    }


def _runtime_result(arguments: list[str]) -> dict[str, Any]:
    rendered = io.StringIO()
    with contextlib.redirect_stdout(rendered):
        runtime_commands.main(arguments)
    return json.loads(rendered.getvalue())


def run_mission(cache_dir: Path, goal: str, mission_id: str | None) -> dict[str, Any]:
    mission_id = mission_id or uuid4().hex
    result = _runtime_result([
        "run", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id, "--goal", goal,
    ])
    return {"mission_id": mission_id, **result}


def mission_status(cache_dir: Path, mission_id: str) -> dict[str, Any]:
    return _runtime_result([
        "status", "--runs-dir", str(cache_dir.resolve() / "runs"), "--mission-id", mission_id,
    ])


def _routine_decision(cache_dir: Path, mission_id: str, skill_id: str, reason: str) -> dict[str, Any]:
    cache_dir = cache_dir.resolve()
    registry = Registry.load_cache(cache_dir)
    if len(registry.suites) != 1:
        raise ValueError("Release decisions require exactly one suite per cache")
    skill = next(iter(registry.suites.values())).skills.get(skill_id)
    if skill is None:
        raise ValueError(f"Unknown Skill: {skill_id}")
    if skill.side_effect_level != "read_only":
        raise ValueError("Significant or device-facing actions require the Runtime approval workflow")
    if skill.execution_mode != "process" or not skill.runnable:
        raise ValueError("Only runnable read-only process Skills can use the release decision command")
    if skill.input_artifacts or skill.required_capabilities:
        raise ValueError("Skills with required inputs or capabilities require the Runtime approval workflow")
    source = next(iter(registry.suites.values())).skill_knowledge.get(skill_id, {}).get("instruction_source")
    if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
        raise ValueError("The Skill lacks a recorded instruction source; use the advanced Runtime workflow")
    document = Path(str(source["path"])).resolve()
    if not document.is_file():
        raise ValueError(f"Skill instruction is unavailable: {document}")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()
    if digest != source["sha256"]:
        raise ValueError("Skill instruction changed; refresh the cache before deciding")
    print(f"Selected Skill: {skill.id}\nImpact: routine/read-only\nReason: {reason}", file=sys.stderr)
    print("Continue with this routine read-only action? [y/N]", file=sys.stderr, end=" ", flush=True)
    if input().strip().lower() not in {"y", "yes"}:
        raise ValueError("Routine action cancelled")
    return {
        "kind": "skill",
        "skill_id": skill.id,
        "reason": reason,
        "assessment": {
            "impact": "routine",
            "rationale": "User explicitly selected this read-only action.",
            "uncertainties": [],
            "authenticity_gaps": [],
        },
        "reviewed_instruction": {"path": str(document), "sha256": digest},
    }


def decide_routine_action(cache_dir: Path, mission_id: str, skill_id: str, reason: str) -> dict[str, Any]:
    decision = _routine_decision(cache_dir, mission_id, skill_id, reason)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(decision, handle, ensure_ascii=False)
            temporary_path = Path(handle.name)
        return _runtime_result([
            "act", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id,
            "--decision-file", str(temporary_path),
        ])
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release-facing LabOntology workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import", help="Create and validate a compact cache")
    import_parser.add_argument("skill_root", type=Path)
    import_parser.add_argument("--suite-id", required=True)
    import_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    inspect_parser = subparsers.add_parser("inspect", help="Summarize a compact cache")
    inspect_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser = subparsers.add_parser("run", help="Create an Agent-mode mission")
    run_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser.add_argument("--goal", required=True)
    run_parser.add_argument("--mission-id")
    status_parser = subparsers.add_parser("status", help="Show a persisted mission")
    status_parser.add_argument("--cache-dir", type=Path, required=True)
    status_parser.add_argument("--mission-id", required=True)
    decide_parser = subparsers.add_parser("decide", help="Confirm one routine read-only action")
    decide_parser.add_argument("--cache-dir", type=Path, required=True)
    decide_parser.add_argument("--mission-id", required=True)
    decide_parser.add_argument("--skill-id", required=True)
    decide_parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            result = import_suite(args.skill_root, args.suite_id, args.workspace)
        elif args.command == "inspect":
            result = inspect_cache(args.cache_dir)
        elif args.command == "run":
            result = run_mission(args.cache_dir, args.goal, args.mission_id)
        elif args.command == "status":
            result = mission_status(args.cache_dir, args.mission_id)
        else:
            result = decide_routine_action(args.cache_dir, args.mission_id, args.skill_id, args.reason)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
