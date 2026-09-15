from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .invoker import SkillInvoker
from .agent_loop import AgentRuntime
from .models import SkillSpec
from .registry import Registry, _skill_from_data
from .state_store import StateStore


def load_skill_file(path: Path) -> SkillSpec:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _skill_from_data(data, path.parent)


def _load_registry(args: argparse.Namespace) -> Registry:
    if getattr(args, "system_dir", None):
        return Registry.load_cache(Path(args.system_dir))
    return Registry.load(Path(args.registry))


def _select_suite(registry: Registry, suite_id: str | None):
    if suite_id:
        return registry.suite(suite_id)
    if len(registry.suites) != 1:
        raise ValueError("--suite is required when the registry contains multiple suites")
    return next(iter(registry.suites.values()))


def _parse_initial_artifacts(values: list[str]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for value in values:
        artifact_id, separator, path = value.partition("=")
        if not separator or not artifact_id or not path:
            raise ValueError("--input-artifact must use ARTIFACT_ID=PATH")
        artifacts[artifact_id] = str(Path(path).expanduser().resolve())
    return artifacts


def _mission_store(args: argparse.Namespace) -> StateStore:
    root = Path(args.runs_dir) if args.runs_dir else (
        Path(args.system_dir) / "runs" if args.system_dir else Path("runs")
    )
    return StateStore(root, args.mission_id)


def build_agent_runtime(args: argparse.Namespace) -> AgentRuntime:
    registry = _load_registry(args)
    suites = [registry.suite(args.suite)] if args.suite else list(registry.suites.values())
    skills, knowledge, workflows, policies = {}, {}, [], []
    for suite in suites:
        duplicates = set(skills).intersection(suite.skills)
        if duplicates:
            raise ValueError(f"Ambiguous Skill IDs {sorted(duplicates)}; select --suite explicitly")
        skills.update(suite.skills)
        knowledge.update({skill_id: {**data, "suite_id": suite.id}
                          for skill_id, data in suite.skill_knowledge.items()})
        policies.extend(suite.policies)
        workflows.extend({
            "id": flow_id, "suite_id": suite.id, "file": str(path),
            "skills": [node.skill_id for node in suite.skill_flow(flow_id).nodes if node.skill_id],
            "role": "reference_only",
        } for flow_id, path in suite.flow_entries.items())
    return AgentRuntime(
        skills, SkillInvoker(), _mission_store(args),
        available_capabilities=set(args.capability).union(*(suite.available_capabilities for suite in suites)), policies=policies,
        skill_knowledge=knowledge, workflow_references=workflows, suite_id=args.suite,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent-directed LabOntology missions")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "context", "act", "reconcile"):
        command = subparsers.add_parser(name)
        registry_source = command.add_mutually_exclusive_group(required=True)
        registry_source.add_argument("--registry")
        registry_source.add_argument("--system-dir")
        command.add_argument("--suite")
        command.add_argument("--runs-dir")
        command.add_argument(
            "--input-artifact",
            action="append",
            default=[],
            metavar="ARTIFACT_ID=PATH",
            help="Seed an external mission input artifact; may be repeated.",
        )
        command.add_argument(
            "--provide-artifact",
            action="append",
            default=[],
            metavar="ARTIFACT_ID=PATH",
            help="Provide outputs from an Agent Skill when resuming; may be repeated.",
        )
        command.add_argument("--mission-id", required=True)
        command.add_argument("--capability", action="append", default=[])
        if name == "run":
            command.add_argument("--goal", default="", help="Mission goal for default Agent mode")
            command.add_argument("--constraint", action="append", default=[])
            command.add_argument("--start-skill", help="Preferred first Skill; Agent may replan")
        if name == "act":
            command.add_argument("--decision-file", required=True, help="One host-Agent decision as JSON")
        if name == "resume":
            command.add_argument("--confirm", action="store_true")
            command.add_argument("--reject", action="store_true")
            command.add_argument("--answer", default="", help="Actual user reply to a pending human decision")
            command.add_argument("--summary", default="", help="Agent Skill result; no artifact required")
            command.add_argument("--evidence", action="append", default=[])
            command.add_argument("--agent-completed", action="store_true")
            command.add_argument("--agent-failed", action="store_true")
        if name == "reconcile":
            command.add_argument("--outcome", required=True,
                                 choices=("not_started", "succeeded", "failed", "unknown"))
            command.add_argument("--summary", required=True)
            command.add_argument("--evidence", action="append", default=[])
    status = subparsers.add_parser("status")
    status.add_argument("--runs-dir", default="runs")
    status.add_argument("--mission-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "status":
        state = StateStore(Path(args.runs_dir), args.mission_id).load()
    else:
        store = _mission_store(args)
        existing = store.load() if store.state_path.exists() else None
        if existing and existing.suite_id:
            if args.suite and args.suite != existing.suite_id:
                raise ValueError("Mission belongs to a different SkillSuite")
            args.suite = existing.suite_id
        runtime = build_agent_runtime(args)
        if args.command == "run":
            runtime.start(args.goal, constraints=args.constraint,
                          artifacts=_parse_initial_artifacts(args.input_artifact),
                          start_skill=args.start_skill)
        elif args.command == "act":
            decision = json.loads(Path(args.decision_file).read_text(encoding="utf-8-sig"))
            runtime.decide(decision)
        elif args.command == "resume":
            runtime.resume(provided_artifacts=_parse_initial_artifacts(args.provide_artifact),
                           summary=args.summary, evidence=args.evidence,
                           agent_completed=args.agent_completed, confirmed=args.confirm,
                           agent_failed=args.agent_failed,
                           rejected=args.reject, answer=args.answer)
        elif args.command == "reconcile":
            runtime.reconcile(args.outcome, args.summary, evidence=args.evidence,
                              provided_artifacts=_parse_initial_artifacts(args.provide_artifact))
        print(json.dumps(runtime.context(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
