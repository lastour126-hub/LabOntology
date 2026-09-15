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
VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))
from core import ontology as ONTOLOGY
from core.creator.importer import discover_tree, export_bundle
from core.creator.intake import receive_bundle
from core.runtime import commands as runtime_commands
from core.runtime.registry import Registry


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_suite(skill_root: Path, suite_id: str, workspace: Path,
                 skill_ids: set[str] | None = None) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    with TemporaryDirectory(prefix="labontology-bundle-") as temporary:
        bundle_dir = Path(temporary)
        export_bundle(skill_root, bundle_dir, suite_id, include_skill_ids=skill_ids)
        imported = receive_bundle(bundle_dir, workspace, source_root=skill_root)

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
        and record.get("sha256") != _sha256(Path(record["path"]))
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


def _cached_suites_for_root(cache_dir: Path, skill_root: Path) -> list[str]:
    manifest_path = cache_dir / "cache-manifest.json"
    if manifest_path.is_file():
        try:
            suite_roots = json.loads(manifest_path.read_text(encoding="utf-8")).get("suite_roots", {})
            exact = sorted(str(suite_id) for suite_id, root in suite_roots.items()
                           if Path(str(root)).resolve() == skill_root)
            if exact:
                return exact
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    index_path = cache_dir / "source-index.json"
    if not index_path.is_file():
        return []
    try:
        sources = json.loads(index_path.read_text(encoding="utf-8")).get("sources", [])
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return sorted({str(record["suite_id"]) for record in sources
                   if isinstance(record, dict) and record.get("suite_id") and record.get("path")
                   and Path(str(record["path"])).resolve().is_relative_to(skill_root)})


def _explicit_suites_for_root(cache_dir: Path, skill_root: Path) -> list[str]:
    manifest_path = cache_dir / "cache-manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        suite_roots = json.loads(manifest_path.read_text(encoding="utf-8")).get("suite_roots", {})
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(suite_roots, dict):
        return []
    return sorted(str(suite_id) for suite_id, root in suite_roots.items()
                  if Path(str(root)).resolve() == skill_root)


def _library_files(skill_root: Path, skill_ids: set[str] | None = None) -> set[Path]:
    ignored_parts = {"__pycache__", ".git", ".hg", ".svn"}
    source_dirs = {Path(str(skill["source_dir"])).resolve() for skill in discover_tree(skill_root)
                   if skill_ids is None or str(skill.get("id")) in skill_ids
                   if skill.get("source_dir")}
    return {path.resolve() for source_dir in source_dirs for path in source_dir.rglob("*")
            if path.is_file() and not any(part in ignored_parts for part in path.parts)}


def _suite_skill_ids(cache_dir: Path, suite_id: str) -> set[str]:
    try:
        return set(Registry.load_cache(cache_dir).suite(suite_id).skills)
    except (FileNotFoundError, KeyError, ValueError, OSError, json.JSONDecodeError):
        return set()


def _new_skill_ids(skill_root: Path, cache_dir: Path) -> set[str]:
    discovered = {str(skill.get("id")) for skill in discover_tree(skill_root) if skill.get("id")}
    try:
        known = {skill_id for suite in Registry.load_cache(cache_dir).suites.values() for skill_id in suite.skills}
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        known = set()
    return discovered - known


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
    suite_roots = manifest.get("suite_roots", {})
    if suite_id:
        if not isinstance(suite_roots, dict) or suite_roots.get(suite_id) != str(skill_root):
            return None
    sources = index.get("sources", [])
    if not isinstance(sources, list):
        return None
    scoped_sources = []
    for record in sources:
        if not isinstance(record, dict) or not record.get("path"):
            continue
        source = Path(str(record["path"])).resolve()
        in_root = source.is_relative_to(skill_root)
        if suite_id:
            if record.get("suite_id") != suite_id or not in_root:
                continue
        elif not in_root:
            continue
        scoped_sources.append((record, source))
    if not scoped_sources:
        return None
    known_paths = {source for _, source in scoped_sources}
    mapped_suites = _explicit_suites_for_root(cache_dir, skill_root)
    expected_skill_ids = _suite_skill_ids(cache_dir, suite_id) if suite_id and len(mapped_suites) > 1 else None
    if not _library_files(skill_root, expected_skill_ids).issubset(known_paths):
        return None
    missing_sources = 0
    changed_sources = 0
    for record, source in scoped_sources:
        if not source.is_file():
            missing_sources += 1
        elif not record.get("sha256") or _sha256(source) != record["sha256"]:
            changed_sources += 1
    if missing_sources or changed_sources:
        return None
    validation_output = io.StringIO()
    with contextlib.redirect_stdout(validation_output):
        if ONTOLOGY.validate(system_dir=cache_dir) != 0:
            return None
    return {
        "cache_dir": str(cache_dir),
        "suite_ids": sorted(suite_ids),
        "matched_sources": len(scoped_sources),
        "source_integrity": {"records": len(scoped_sources), "missing": missing_sources, "changed": changed_sources},
        "source_freshness": "current",
    }


def sync_workspace(skill_root: Path, workspace: Path, suite_id: str | None = None,
                   skill_ids: set[str] | None = None, *, propagate_shared: bool = True) -> dict[str, Any]:
    """Refresh one explicit Suite, or safely place unclassified Skills in General."""
    skill_root = skill_root.resolve()
    cache = _workspace_cache_path(workspace)
    matched_suites = _cached_suites_for_root(cache, skill_root)
    new_skill_ids = _new_skill_ids(skill_root, cache)
    if suite_id:
        selected_suite = suite_id
    elif len(matched_suites) == 1:
        selected_suite = matched_suites[0]
    elif len(matched_suites) > 1:
        if new_skill_ids:
            # General is an additive bucket: retain its existing members while
            # importing only newly discovered, unclassified Skills.
            existing_general_ids = _suite_skill_ids(cache, "suite:general")
            return sync_workspace(
                skill_root, workspace, "suite:general",
                skill_ids=existing_general_ids | new_skill_ids,
            )
        raise ValueError("Multiple existing SkillSuites own this root; specify --suite-id")
    else:
        selected_suite = "suite:general"
    explicit_mappings = _explicit_suites_for_root(cache, skill_root)
    selected_ids = skill_ids
    if selected_ids is None and len(explicit_mappings) > 1:
        selected_ids = _suite_skill_ids(cache, selected_suite)
    # A requested Skill set that contains IDs absent from the cached Suite is
    # necessarily stale, even if the existing source records still match.
    # This prevents an existing suite:general from incorrectly reusing its old
    # cache when a new unclassified Skill was discovered.
    cached_selected_ids = _suite_skill_ids(cache, selected_suite)
    requested_ids = set(selected_ids or ())
    if requested_ids - cached_selected_ids:
        current = None
    else:
        current = _cache_match(cache, skill_root, selected_suite)
    if current is not None:
        return {
            "suite_id": selected_suite,
            "cache_dir": current["cache_dir"],
            "skill_count": len(Registry.load_cache(cache).suite(selected_suite).skills),
            "validation": {"graphs": 1, "valid": True},
            "suite_ids": current["suite_ids"],
            "synchronized": False,
            "reused": True,
        }
    # Skill entities are global in the unified graph. If a changed Skill is
    # shared by multiple Suites rooted at this same library, refresh those
    # memberships together so no Suite keeps an obsolete source hash.
    related_suites: list[str] = []
    if propagate_shared and current is None and selected_suite in explicit_mappings:
        try:
            registry = Registry.load_cache(cache)
            selected_members = set(selected_ids or registry.suite(selected_suite).skills)
            for owner_id in explicit_mappings:
                if owner_id == selected_suite or owner_id not in registry.suites:
                    continue
                if selected_members & set(registry.suite(owner_id).skills):
                    related_suites.append(owner_id)
        except (FileNotFoundError, KeyError, ValueError, OSError, json.JSONDecodeError):
            related_suites = []
    result = import_suite(skill_root, selected_suite, workspace, selected_ids)
    for owner_id in related_suites:
        owner_ids = _suite_skill_ids(cache, owner_id)
        import_suite(skill_root, owner_id, workspace, owner_ids)
    manifest = json.loads((Path(result["cache_dir"]) / "cache-manifest.json").read_text(encoding="utf-8"))
    return {**result, "suite_ids": manifest["suite_ids"], "synchronized": True, "reused": False,
            **({"related_suites": related_suites} if related_suites else {})}


def sync_workspace_all(skill_root: Path, workspace: Path) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    cache = _workspace_cache_path(workspace)
    suite_ids = _explicit_suites_for_root(cache, skill_root)
    if not suite_ids:
        raise ValueError("--all requires an existing explicit SkillSuite mapping for this root")
    new_skill_ids = _new_skill_ids(skill_root, cache)
    results = [sync_workspace(skill_root, workspace, suite_id,
                              skill_ids=_suite_skill_ids(cache, suite_id),
                              propagate_shared=False) for suite_id in suite_ids]
    if new_skill_ids:
        existing_general_ids = _suite_skill_ids(cache, "suite:general")
        results.append(sync_workspace(
            skill_root, workspace, "suite:general",
            skill_ids=existing_general_ids | new_skill_ids,
            propagate_shared=False,
        ))
    return {"cache_dir": str(_workspace_cache_path(workspace)), "suites": results,
            "synchronized": any(result["synchronized"] for result in results)}


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


def resume_mission(cache_dir: Path, mission_id: str, *, suite_id: str | None = None,
                   confirm: bool = False, reject: bool = False,
                   answer: str = "", summary: str = "", evidence: list[str] | None = None,
                   provided_artifacts: list[str] | None = None, agent_completed: bool = False,
                   agent_failed: bool = False) -> dict[str, Any]:
    arguments = ["resume", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    for flag, enabled in (("--confirm", confirm), ("--reject", reject),
                          ("--agent-completed", agent_completed), ("--agent-failed", agent_failed)):
        if enabled:
            arguments.append(flag)
    if answer:
        arguments.extend(["--answer", answer])
    if summary:
        arguments.extend(["--summary", summary])
    for item in evidence or []:
        arguments.extend(["--evidence", item])
    for item in provided_artifacts or []:
        arguments.extend(["--provide-artifact", item])
    return _runtime_result(arguments)


def _select_skill(registry: Registry, skill_id: str, suite_id: str | None = None):
    if suite_id:
        try:
            suite = registry.suite(suite_id)
        except KeyError as exc:
            raise ValueError(f"Unknown SkillSuite: {suite_id}") from exc
        skill = suite.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown Skill in {suite_id}: {skill_id}")
        return suite, skill
    matches = [(suite, suite.skills[skill_id]) for suite in registry.suites.values() if skill_id in suite.skills]
    if not matches:
        raise ValueError(f"Unknown Skill: {skill_id}")
    if len(matches) != 1:
        raise ValueError(f"Skill {skill_id} belongs to multiple SkillSuites; specify --suite-id")
    return matches[0]


def describe_skill(cache_dir: Path, skill_id: str, suite_id: str | None = None) -> dict[str, Any]:
    suite, skill = _select_skill(Registry.load_cache(cache_dir.resolve()), skill_id, suite_id)
    knowledge = suite.skill_knowledge.get(skill.id, {})
    return {
        "id": skill.id,
        "suite_id": suite.id,
        "name": knowledge.get("name", skill.id),
        "description": knowledge.get("description"),
        "inputs": list(skill.input_artifacts),
        "outputs": dict(skill.outputs),
        "required_capabilities": list(skill.required_capabilities),
        "side_effect_level": skill.side_effect_level,
        "execution_mode": skill.execution_mode,
        "runnable": skill.runnable,
        "instruction_source": knowledge.get("instruction_source"),
        "instruction_digest": knowledge.get("instruction_digest", []),
        "documentation": knowledge.get("documentation", {}),
        "unresolved": knowledge.get("unresolved", []),
        "evidence": knowledge.get("evidence", []),
        "capability_evidence": knowledge.get("capability_evidence", []),
        "contract_evidence": knowledge.get("contract_evidence", []),
        "preconditions": knowledge.get("preconditions", []),
        "decision_policy": knowledge.get("decision_policy", {}),
    }


def list_missions(cache_dir: Path, query: str | None = None) -> dict[str, Any]:
    runs_dir = cache_dir.resolve() / "runs"
    needle = (query or "").casefold()
    missions = []
    for state_path in sorted(runs_dir.glob("*/state.json")) if runs_dir.is_dir() else []:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        goal = str(state.get("goal", ""))
        if needle and needle not in goal.casefold() and needle not in str(state.get("mission_id", "")).casefold():
            continue
        missions.append({"mission_id": state.get("mission_id", state_path.parent.name), "goal": goal,
                         "status": state.get("status", "unknown"), "suite_id": state.get("suite_id")})
    return {"missions": missions}


def _user_facing_error(exc: Exception) -> str:
    """Translate common release errors into experiment-language guidance."""
    message = str(exc)
    translations = (
        ("Workspace cache is unavailable or stale; synchronize the workspace Skill library",
         "实验流程库需要更新，请先同步后再继续。"),
        ("Multiple existing SkillSuites own this root; specify --suite-id",
         "这个 Skill 目录对应多个实验流程集合，请明确要使用的实验项目。"),
        ("--all requires an existing explicit SkillSuite mapping for this root",
         "只有已经登记过实验项目的 Skill 目录才能执行全量维护。"),
        ("Mission belongs to a different SkillSuite",
         "这个任务属于另一个实验项目，请继续使用任务原本所属的项目。"),
        ("Unknown Skill:", "没有找到匹配的实验步骤："),
        ("Unknown Skill in", "当前实验项目中没有找到这个实验步骤："),
        ("Required inputs missing:", "执行前还缺少必要输入："),
        ("Required capability unavailable:", "执行前还缺少必要能力："),
    )
    for source, target in translations:
        if message.startswith(source):
            suffix = message[len(source):].lstrip()
            return f"{target}{suffix}" if suffix else target
    return message


def _routine_decision(cache_dir: Path, mission_id: str, skill_id: str, reason: str,
                      suite_id: str | None = None) -> dict[str, Any]:
    cache_dir = cache_dir.resolve()
    registry = Registry.load_cache(cache_dir)
    suite, skill = _select_skill(registry, skill_id, suite_id)
    if skill.side_effect_level != "read_only":
        raise ValueError("Significant or device-facing actions require the Runtime approval workflow")
    if skill.execution_mode != "process" or not skill.runnable:
        raise ValueError("Only runnable read-only process Skills can use the release decision command")
    if skill.input_artifacts or skill.required_capabilities:
        raise ValueError("Skills with required inputs or capabilities require the Runtime approval workflow")
    source = suite.skill_knowledge.get(skill_id, {}).get("instruction_source")
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


def decide_routine_action(cache_dir: Path, mission_id: str, skill_id: str, reason: str,
                          suite_id: str | None = None) -> dict[str, Any]:
    decision = _routine_decision(cache_dir, mission_id, skill_id, reason, suite_id)
    suite, _ = _select_skill(Registry.load_cache(cache_dir.resolve()), skill_id, suite_id)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(decision, handle, ensure_ascii=False)
            temporary_path = Path(handle.name)
        return _runtime_result([
            "act", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id,
            "--suite", suite.id, "--decision-file", str(temporary_path),
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
    sync_parser.add_argument("--all", action="store_true")
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
    resume_parser.add_argument("--suite-id")
    resume_parser.add_argument("--confirm", action="store_true")
    resume_parser.add_argument("--reject", action="store_true")
    resume_parser.add_argument("--answer", default="")
    resume_parser.add_argument("--summary", default="")
    resume_parser.add_argument("--evidence", action="append", default=[])
    resume_parser.add_argument("--provide-artifact", action="append", default=[], metavar="ARTIFACT_ID=PATH")
    resume_parser.add_argument("--agent-completed", action="store_true")
    resume_parser.add_argument("--agent-failed", action="store_true")
    status_parser = subparsers.add_parser("status", help="Show a persisted mission")
    status_parser.add_argument("--cache-dir", type=Path, required=True)
    status_parser.add_argument("--mission-id", required=True)
    decide_parser = subparsers.add_parser("decide", help="Confirm one routine read-only action")
    decide_parser.add_argument("--cache-dir", type=Path, required=True)
    decide_parser.add_argument("--mission-id", required=True)
    decide_parser.add_argument("--skill-id", required=True)
    decide_parser.add_argument("--suite-id")
    decide_parser.add_argument("--reason", required=True)
    describe_parser = subparsers.add_parser("describe-skill", help="Read full details for one selected Skill")
    describe_parser.add_argument("--cache-dir", type=Path, required=True)
    describe_parser.add_argument("--skill-id", required=True)
    describe_parser.add_argument("--suite-id")
    missions_parser = subparsers.add_parser("missions", help="List persisted Agent missions")
    missions_parser.add_argument("--cache-dir", type=Path, required=True)
    missions_parser.add_argument("--query")
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            result = import_suite(args.skill_root, args.suite_id, args.workspace)
        elif args.command == "sync":
            if args.all and args.suite_id:
                raise ValueError("--all cannot be combined with --suite-id")
            result = sync_workspace_all(args.skill_root, args.workspace) if args.all else sync_workspace(args.skill_root, args.workspace, args.suite_id)
        elif args.command == "resolve-cache":
            result = resolve_cache(args.skill_root, args.workspace, args.suite_id)
        elif args.command == "inspect":
            result = inspect_cache(args.cache_dir)
        elif args.command == "run":
            result = run_mission(args.cache_dir, args.goal, args.mission_id, args.suite_id, args.input_artifact)
        elif args.command == "resume":
            result = resume_mission(args.cache_dir, args.mission_id, suite_id=args.suite_id,
                                    confirm=args.confirm, reject=args.reject,
                                    answer=args.answer, summary=args.summary, evidence=args.evidence,
                                    provided_artifacts=args.provide_artifact,
                                    agent_completed=args.agent_completed, agent_failed=args.agent_failed)
        elif args.command == "status":
            result = mission_status(args.cache_dir, args.mission_id)
        elif args.command == "decide":
            result = decide_routine_action(args.cache_dir, args.mission_id, args.skill_id, args.reason, args.suite_id)
        elif args.command == "describe-skill":
            result = describe_skill(args.cache_dir, args.skill_id, args.suite_id)
        else:
            result = list_missions(args.cache_dir, args.query)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(_user_facing_error(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
