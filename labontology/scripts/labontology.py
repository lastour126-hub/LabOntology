from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Sequence
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
from core import ontology as ONTOLOGY
from core.creator.importer import export_bundle
from core.creator.intake import receive_bundle
from core.runtime import commands as runtime_commands
from core.runtime.registry import Registry


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
    entities, relations = ONTOLOGY.load_graph(cache_dir / "ontology.jsonl")
    if not any(entity.get("type") == "SkillSuite" for entity in entities.values()):
        raise ValueError("Imported graph contains no SkillSuite")
    return {
        "suite_id": imported["suite_id"],
        "cache_dir": str(cache_dir),
        "skill_count": sum(
            relation.get("relation") == "containsSkill" and relation.get("source") == suite_id
            for relation in relations
        ),
        "validation": {"graphs": 1, "valid": True},
    }


def inspect_cache(cache_dir: Path) -> dict[str, Any]:
    cache_dir = cache_dir.resolve()
    registry = Registry.load_cache(cache_dir)
    entities, relations = ONTOLOGY.load_graph(cache_dir / "ontology.jsonl")
    index = json.loads((cache_dir / "source-index.json").read_text(encoding="utf-8"))
    sources = index.get("sources", [])
    missing = sum(not Path(record["path"]).is_file() for record in sources if record.get("path"))
    changed = sum(
        Path(record["path"]).is_file()
        and record.get("sha256") != hashlib.sha256(Path(record["path"]).read_bytes()).hexdigest()
        for record in sources if record.get("path") and record.get("sha256")
    )
    suites = [{"suite_id": suite.id, "skill_count": len(suite.skills)}
              for suite in sorted(registry.suites.values(), key=lambda suite: suite.id)]
    result = {
        "suites": suites,
        "capabilities": sorted({capability for suite in registry.suites.values()
                                 for capability in suite.available_capabilities}),
        "graph": {"entities": len(entities), "relations": len(relations)},
        "source_integrity": {"records": len(sources), "missing": missing, "changed": changed},
    }
    if len(suites) == 1:
        result.update({"suite_id": suites[0]["suite_id"], "skill_count": suites[0]["skill_count"]})
    return result


def _workspace_cache_path(workspace: Path) -> Path:
    return workspace.resolve() / "labontology_workspace_cache"


def _cache_match(cache_dir: Path, skill_root: Path, suite_id: str | None) -> dict[str, Any] | None:
    manifest_path = cache_dir / "cache-manifest.json"
    graph_path = cache_dir / "ontology.jsonl"
    index_path = cache_dir / "source-index.json"
    if not (manifest_path.is_file() and graph_path.is_file() and index_path.is_file()):
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if manifest.get("schema") != "labontology.workspace-cache.v1":
        return None
    suite_ids = manifest.get("suite_ids", [])
    if not isinstance(suite_ids, list) or not all(isinstance(item, str) for item in suite_ids):
        return None
    if suite_id and suite_id not in suite_ids:
        return None
    sources = index.get("sources", [])
    if not isinstance(sources, list):
        return None
    matched_sources = 0
    missing_sources = 0
    for record in sources:
        if not isinstance(record, dict) or not record.get("path"):
            continue
        source = Path(str(record["path"])).resolve()
        if not source.is_file():
            missing_sources += 1
        elif not record.get("sha256") or hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
            missing_sources += 1
        if source.is_relative_to(skill_root):
            matched_sources += 1
    if not matched_sources or missing_sources:
        return None
    validation_output = io.StringIO()
    with contextlib.redirect_stdout(validation_output):
        if ONTOLOGY.validate(system_dir=cache_dir) != 0:
            return None
    return {
        "cache_dir": str(cache_dir),
        "suite_ids": sorted(suite_ids),
        "matched_sources": matched_sources,
        "source_integrity": {"records": len(sources), "missing": missing_sources},
        "source_freshness": "current",
    }


def sync_workspace(skill_root: Path, workspace: Path, suite_id: str | None = None) -> dict[str, Any]:
    """Refresh one explicit Suite, or safely place unclassified Skills in General."""
    result = import_suite(skill_root, suite_id or "suite:general", workspace)
    manifest = json.loads((Path(result["cache_dir"]) / "cache-manifest.json").read_text(encoding="utf-8"))
    return {**result, "suite_ids": manifest["suite_ids"], "synchronized": True}


def resolve_cache(skill_root: Path, workspace: Path, suite_id: str | None = None) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    if not skill_root.is_dir():
        raise ValueError(f"Skill root is unavailable: {skill_root}")
    cache = _workspace_cache_path(workspace)
    selected = _cache_match(cache, skill_root, suite_id)
    if selected is None:
        raise ValueError("Workspace cache is unavailable or stale; synchronize the workspace Skill library")
    return {
        "cache_dir": selected["cache_dir"],
        "suite_ids": selected["suite_ids"],
        "suite_id": suite_id if suite_id else selected["suite_ids"][0] if len(selected["suite_ids"]) == 1 else None,
        "candidate_count": 1,
        "matched_sources": selected["matched_sources"],
        "source_integrity": selected["source_integrity"],
    }


def _runtime_result(arguments: list[str]) -> dict[str, Any]:
    rendered = io.StringIO()
    with contextlib.redirect_stdout(rendered):
        runtime_commands.main(arguments)
    return json.loads(rendered.getvalue())


def run_mission(cache_dir: Path, goal: str, mission_id: str | None, suite_id: str | None,
                input_artifacts: list[str]) -> dict[str, Any]:
    mission_id = mission_id or uuid4().hex
    arguments = [
        "run", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id, "--goal", goal,
    ]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    for artifact in input_artifacts:
        arguments.extend(["--input-artifact", artifact])
    result = _runtime_result(arguments)
    return {"mission_id": mission_id, **result}


def mission_status(cache_dir: Path, mission_id: str) -> dict[str, Any]:
    return _runtime_result([
        "status", "--runs-dir", str(cache_dir.resolve() / "runs"), "--mission-id", mission_id,
    ])


def resume_mission(cache_dir: Path, mission_id: str) -> dict[str, Any]:
    return _runtime_result([
        "resume", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id,
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
    sync_parser = subparsers.add_parser("sync", help="Synchronize a Skill root into the workspace cache")
    sync_parser.add_argument("--skill-root", type=Path, required=True)
    sync_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    sync_parser.add_argument("--suite-id")
    resolve_parser = subparsers.add_parser("resolve-cache", help="Find a valid existing cache for a Skill directory")
    resolve_parser.add_argument("--skill-root", type=Path, required=True)
    resolve_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    resolve_parser.add_argument("--suite-id")
    inspect_parser = subparsers.add_parser("inspect", help="Summarize a compact cache")
    inspect_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser = subparsers.add_parser("run", help="Create an Agent-mode mission")
    run_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser.add_argument("--goal", required=True)
    run_parser.add_argument("--mission-id")
    run_parser.add_argument("--suite-id")
    run_parser.add_argument("--input-artifact", action="append", default=[], metavar="ARTIFACT_ID=PATH")
    resume_parser = subparsers.add_parser("resume", help="Resume an Agent-mode mission")
    resume_parser.add_argument("--cache-dir", type=Path, required=True)
    resume_parser.add_argument("--mission-id", required=True)
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
        elif args.command == "sync":
            result = sync_workspace(args.skill_root, args.workspace, args.suite_id)
        elif args.command == "resolve-cache":
            result = resolve_cache(args.skill_root, args.workspace, args.suite_id)
        elif args.command == "inspect":
            result = inspect_cache(args.cache_dir)
        elif args.command == "run":
            result = run_mission(args.cache_dir, args.goal, args.mission_id, args.suite_id, args.input_artifact)
        elif args.command == "resume":
            result = resume_mission(args.cache_dir, args.mission_id)
        elif args.command == "status":
            result = mission_status(args.cache_dir, args.mission_id)
        else:
            result = decide_routine_action(args.cache_dir, args.mission_id, args.skill_id, args.reason)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
