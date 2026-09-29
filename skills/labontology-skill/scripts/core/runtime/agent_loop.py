"""One-action execution loop directed by the host Agent, not an embedded LLM."""
from __future__ import annotations

import hashlib
import re
import shutil
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ExecutionPolicySpec, MissionState, SkillSpec
from .state_store import StateStore


def _artifact_paths(artifacts: dict[str, str]) -> dict[str, str]:
    result = {}
    for name, value in artifacts.items():
        path = Path(value).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Artifact does not exist: {name}={path}")
        result[name] = str(path)
    return result


def _materialize_artifacts(artifacts: dict[str, str], artifact_dir: Path) -> dict[str, str]:
    """Copy Agent-provided outputs into the mission-owned artifact directory."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    for artifact_id, source_value in artifacts.items():
        source = Path(source_value).resolve()
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact_id.split(":", 1)[-1]).strip("._") or "artifact"
        destination = artifact_dir / f"{safe_id}__{source.name}"
        if source != destination.resolve():
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        result[artifact_id] = str(destination)
    return result


def _artifact_records(artifacts: dict[str, str], action_id: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for artifact_id, value in artifacts.items():
        path = Path(value).resolve()
        record: dict[str, Any] = {
            "artifact_id": artifact_id,
            "path": str(path),
            "action_id": action_id,
            "valid": path.exists(),
        }
        if path.is_file():
            record["size_bytes"] = path.stat().st_size
            record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            record["size_bytes"] = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        records[artifact_id] = record
    return records


def _untracked_artifacts(state: MissionState, artifact_dir: Path) -> list[str]:
    if not artifact_dir.is_dir():
        return []
    known = {str(Path(value).resolve()) for value in state.artifacts.values()}
    known.update(str(Path(record["path"]).resolve()) for record in state.artifact_records.values()
                 if isinstance(record, dict) and record.get("path"))
    return sorted(str(path.resolve()) for path in artifact_dir.rglob("*")
                  if path.is_file() and str(path.resolve()) not in known)


def _search_terms(value: str) -> set[str]:
    """Return compact English terms and overlapping Chinese terms for ranking."""
    terms = set(re.findall(r"[a-z0-9]+", value.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", value):
        terms.add(run)
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return terms


def _documentation_search_text(documentation: Any) -> str:
    """Build a bounded search view without placing full documents in context."""
    if not isinstance(documentation, dict):
        return ""
    parts: list[str] = []
    for key in (
        "input_hints", "output_hints", "execution_order_hints",
        "precondition_hints", "constraint_hints", "related_skill_refs",
    ):
        values = documentation.get(key, [])
        if isinstance(values, list):
            parts.extend(str(value) for value in values[:40])
    sections = documentation.get("sections", [])
    if isinstance(sections, list):
        for section in sections[:20]:
            if not isinstance(section, dict):
                continue
            parts.append(str(section.get("heading") or ""))
            parts.append(str(section.get("text") or "")[:800])
    return " ".join(parts)


class AgentRuntime:
    def __init__(
        self, skills: dict[str, SkillSpec], store: StateStore,
        *, available_capabilities: set[str] | None = None,
        policies: list[ExecutionPolicySpec] | None = None,
        skill_knowledge: dict[str, dict[str, Any]] | None = None,
        workflow_references: list[dict[str, Any]] | None = None,
        suite_id: str | None = None,
    ):
        self.skills, self.store = skills, store
        self.capabilities = set(available_capabilities or [])
        self.policies = policies or []
        self.knowledge = skill_knowledge or {}
        self.workflows = workflow_references or []
        self.suite_id = suite_id

    def _feedback(self, event: str, skill_id: str | None, details: dict[str, Any]) -> None:
        self.store.feedback.append(event, self.store.mission_id, skill_id, details)

    def _load(self) -> MissionState:
        state = self.store.load()
        if state.mode != "agent":
            raise ValueError("Mission is not an Agent mission; create a new Agent mission")
        self.capabilities.update(state.available_capabilities)
        state.available_capabilities = sorted(self.capabilities)
        if self.suite_id:
            if state.suite_id and state.suite_id != self.suite_id:
                raise ValueError("Mission belongs to a different SkillSuite")
            if not state.suite_id:
                state.suite_id = self.suite_id
                self.store.save(state)
        return state

    def start(self, goal: str, *, constraints: list[str] | None = None,
              artifacts: dict[str, str] | None = None,
              start_skill: str | None = None) -> MissionState:
        if self.store.state_path.exists():
            state = self._load()
            if goal and goal != state.goal:
                raise ValueError("Use a new mission ID for a different goal")
            return state
        if not goal.strip():
            raise ValueError("A mission goal is required")
        if start_skill and start_skill not in self.skills:
            raise ValueError(f"Unknown start Skill: {start_skill}")
        state = MissionState(self.store.mission_id, status="awaiting_decision", mode="agent",
                             goal=goal, constraints=list(constraints or []),
                             available_capabilities=sorted(self.capabilities),
                             artifacts=_artifact_paths(artifacts or {}), start_skill=start_skill,
                             suite_id=self.suite_id)
        self.store.save(state)
        self.store.event("mission_created", {"goal": goal, "mode": "agent"})
        return state

    def context(self) -> dict[str, Any]:
        state = self._load()
        artifact_dir = self.store.run_dir / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        cards: list[tuple[int, dict[str, Any]]] = []
        excluded_skills: list[dict[str, str]] = []
        goal_terms = _search_terms(state.goal)
        for skill in self.skills.values():
            knowledge = self.knowledge.get(skill.id, {})
            name = str(knowledge.get("name") or skill.id)
            description = str(knowledge.get("description") or "")
            searchable = (
                f"{skill.id} {name} {description} {' '.join(skill.goal_types)} "
                f"{' '.join(skill.triggers)} {' '.join(skill.required_capabilities)} "
                f"{' '.join(skill.input_artifacts)} "
                f"{_documentation_search_text(knowledge.get('documentation'))}"
            ).lower()
            searchable_terms = _search_terms(searchable)
            score = sum(term in searchable_terms for term in goal_terms)
            card = {
                "id": skill.id,
                "name": name,
                "description": description,
                "suite_id": knowledge.get("suite_id"),
                "inputs": list(skill.input_artifacts),
                "required_capabilities": list(skill.required_capabilities),
                "side_effect_level": skill.side_effect_level,
                "missing_inputs": [artifact for artifact in skill.input_artifacts if artifact not in state.artifacts],
                "missing_capabilities": sorted(set(skill.required_capabilities) - self.capabilities),
                "match_score": score,
                "eligible": True,
            }
            if skill.optional_entrypoints or skill.optional_command:
                card["optional_script"] = {
                    "entrypoints": list(skill.optional_entrypoints),
                    "script_command": list(skill.optional_command),
                }
            cards.append((score, card))
        matched_cards = [
            item for item in cards
            if item[0] > 0
            or item[1]["id"] == state.start_skill
            or (item[1]["inputs"] and not item[1]["missing_inputs"])
        ]
        ranked_cards = sorted(cards, key=lambda item: (-item[0], item[1]["id"]))
        candidates = [card for _, card in sorted(matched_cards, key=lambda item: (-item[0], item[1]["id"]))[:5]]
        candidate_review_required = not matched_cards and bool(cards)
        if candidate_review_required:
            candidates = [card for _, card in ranked_cards[:5]]
            for card in candidates:
                card["selection_note"] = "关键词未直接命中，必须读取完整 Skill 文档确认是否适用。"
        historical_experiences = self.store.experiences.search(
            state.goal, skill_ids=[card["id"] for card in candidates]
        )
        if not self.skills:
            coverage_diagnostic = {
                "status": "no_registered_skill",
                "execution_started": False,
                "registered_skill_count": 0,
                "candidate_count": 0,
                "fallback_available": True,
                "fallback_scope": "low_risk_read_only",
                "fallback_message": (
                    "如果这是低风险、只读分析，可以由 Agent 直接尝试，"
                    "结果会标记为 Agent 直接执行。是否继续？"
                ),
                "user_message": (
                    "当前没有找到可用的实验能力，任务还没有开始。"
                    "请先安装或初始化相关能力。"
                ),
            }
        elif candidate_review_required:
            coverage_diagnostic = {
                "status": "candidate_review",
                "execution_started": False,
                "registered_skill_count": len(self.skills),
                "candidate_count": len(candidates),
                "fallback_available": False,
                "user_message": (
                    "当前已登记实验能力，但任务关键词没有直接匹配。"
                    "请先读取候选 Skill 的完整说明确认是否适用，确认后再开始执行。"
                ),
            }
        else:
            coverage_diagnostic = {
                "status": "candidate_found",
                "execution_started": False,
                "registered_skill_count": len(self.skills),
                "candidate_count": len(candidates),
                "user_message": "已经找到可用的实验能力，但任务还没有开始。",
            }
        retry_candidates = []
        for action_id, execution in state.skill_executions.items():
            skill = self.skills.get(execution.get("skill_id"))
            if (execution.get("status") in {"failed", "timed_out"}
                    and execution.get("retryable") is True
                    and skill is not None
                    and skill.side_effect_level == "read_only"
                    and execution.get("retry_count", 0) < skill.retry_limit):
                retry_candidates.append({
                    "action_id": action_id,
                    "skill_id": skill.id,
                    "failure_kind": execution.get("failure_kind"),
                    "retry_count": execution.get("retry_count", 0),
                })
        waiting_for_resume = state.status in {"waiting_agent", "waiting_human"}
        waiting_for_reconcile = state.status == "running"
        native_fallback_waiting = (
            state.status == "waiting_agent"
            and isinstance(state.pending_action, dict)
            and state.pending_action.get("execution_source") == "agent_native"
        )
        execution_cycle = {
            "entrypoint": "act",
            "after_act": "reconcile" if waiting_for_reconcile else ("resume" if waiting_for_resume else "context"),
            "requires_resume": waiting_for_resume,
            "requires_reconcile": waiting_for_reconcile,
            "resume_mode": (
                "agent_native" if native_fallback_waiting
                else "external_skill" if state.status == "waiting_agent"
                else "human_decision" if state.status == "waiting_human"
                else None
            ),
            "status": state.status,
        }
        if state.status == "running":
            next_step = "Host Agent: reconcile the interrupted action before choosing another Skill."
        elif state.status == "waiting_agent":
            next_step = (
                "Host Agent: follow the prepared Skill document; optionally use its script accelerator, "
                "then call resume with the actual result and read context."
            )
        elif state.status == "waiting_human":
            next_step = "Host Agent: obtain the required user decision, call resume, then read context."
        elif state.replan_required:
            next_step = (
                "Host Agent: reassess the goal with the human answer, read context, and select a Skill; "
                "for an explicitly approved low-risk read-only fallback, use agent_fallback; "
                "do not complete or compute outside a Skill or approved fallback."
            )
        else:
            next_step = "Host Agent: inspect context and choose the next action; call resume only when the execution_cycle requires it."
        return {"mission": state.to_dict(), "skills": candidates, "candidate_count": len(candidates),
                "registered_skill_count": len(self.skills), "match_found": bool(candidates),
                "coverage_diagnostic": coverage_diagnostic,
                "excluded_skills": excluded_skills,
                "artifact_dir": str(artifact_dir),
                "supervisor_status": state.supervisor_status,
                "pending_ticket": state.pending_ticket,
                "prepared_skill": state.prepared_skill,
                "action_history_count": len(state.action_history),
                 "available_capabilities": sorted(self.capabilities),
                 "start_skill": state.start_skill,
                 "replan_required": state.replan_required,
                 "retry_candidates": retry_candidates,
                "workflow_references": self.workflows,
                "policies": [asdict(p) for p in self.policies],
                "execution_cycle": execution_cycle,
                "historical_experiences": historical_experiences,
                "next": next_step}

    def prepare_skill(self, skill_id: str) -> dict[str, Any]:
        """Read the selected Skill and persist the exact document digest."""
        state = self._load()
        skill = self.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown registered Skill: {skill_id}")
        source = self.knowledge.get(skill_id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path"):
            raise ValueError(f"Skill has no instruction source: {skill_id}")
        path = Path(str(source["path"])).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Skill document is unavailable: {path}")
        raw_content = path.read_bytes()
        actual_hash = hashlib.sha256(raw_content).hexdigest()
        recorded_hash = source.get("sha256")
        if recorded_hash and actual_hash != recorded_hash:
            raise ValueError("Skill document changed; refresh the cache and reassess the action")
        content = raw_content.decode("utf-8", errors="replace")
        prepared = {
            "skill_id": skill_id,
            "path": str(path),
            "sha256": actual_hash,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "content": content,
        }
        state.prepared_skill = {key: value for key, value in prepared.items() if key != "content"}
        self.store.save(state)
        self.store.event("skill_prepared", {
            "skill": skill_id, "path": str(path), "sha256": prepared["sha256"]
        })
        self._feedback("skill_prepared", skill_id,
                       {"path": str(path), "sha256": prepared["sha256"]})
        return prepared

    def assert_skill_prepared(self, skill_id: str) -> None:
        state = self._load()
        skill = self.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown registered Skill: {skill_id}")
        error = self._prepared_skill_error(state, skill)
        if error:
            raise ValueError(error)

    def decide(self, decision: dict[str, Any]) -> MissionState:
        if not isinstance(decision, dict):
            raise ValueError("Decision must be a JSON object")
        state = self._load()
        if state.status != "awaiting_decision":
            raise ValueError(f"Cannot replace an action while mission is {state.status}")
        action = deepcopy(decision)
        if not isinstance(action.get("reason"), str) or not action["reason"].strip():
            raise ValueError("Decision requires a reason")
        kind = action.get("kind")
        if kind not in {"skill", "request_human", "agent_fallback", "complete"}:
            raise ValueError("Decision kind must be skill, request_human, agent_fallback or complete")
        if kind == "complete" and state.replan_required:
            raise ValueError("Human answer received; replan in context and select a Skill before completing")
        if kind == "skill":
            if action.get("skill_id") not in self.skills:
                raise ValueError(f"Unknown registered Skill: {action.get('skill_id')}")
            assessment = action.get("assessment", {})
            if not isinstance(assessment, dict) or assessment.get("impact") not in {"routine", "significant"}:
                raise ValueError("Agent assessment requires impact: routine or significant")
            if not isinstance(assessment.get("rationale"), str) or not assessment["rationale"].strip():
                raise ValueError("Agent assessment requires a rationale")
            for key in ("uncertainties", "authenticity_gaps"):
                if not isinstance(assessment.get(key), list) or not all(isinstance(x, str) for x in assessment[key]):
                    raise ValueError(f"Agent assessment requires {key} as a list of strings")
            if "authorization" in assessment and not isinstance(assessment["authorization"], str):
                raise ValueError("Existing authorization must cite the user's instruction")
            action["inputs"] = _artifact_paths(action.get("inputs", {}))
            action["arguments"] = self._decision_arguments(action, self.skills[action["skill_id"]])
            prepared_error = self._prepared_skill_error(state, self.skills[action["skill_id"]])
            if prepared_error:
                raise ValueError(prepared_error)
            if state.prepared_skill and state.prepared_skill.get("skill_id") == action["skill_id"]:
                action["prepared_skill"] = deepcopy(state.prepared_skill)
            instruction_error = self._instruction_error(action, self.skills[action["skill_id"]])
            if instruction_error:
                raise ValueError(instruction_error)
            action["skill_snapshot"] = self._skill_snapshot(self.skills[action["skill_id"]])
            retry_error = self._retry_error(state, action, self.skills[action["skill_id"]])
            if retry_error:
                raise ValueError(retry_error)
        if kind == "agent_fallback":
            fallback_error = self._agent_fallback_error(state, action)
            if fallback_error:
                raise ValueError(fallback_error)
        if kind == "request_human" and not str(action.get("question", "")).strip():
            raise ValueError("Human decision requires a question")
        action["id"] = f"action:{len(state.decisions) + 1}"
        action["action_id"] = action["id"]
        action["return_to"] = "labontology-skill"
        action["ticket_status"] = "issued"
        state.decisions.append(deepcopy(action))
        state.pending_action = action
        state.pending_ticket = action
        state.supervisor_status = "decision_pending"
        self.store.event("agent_decision", action)
        if kind == "complete":
            untracked = _untracked_artifacts(state, self.store.run_dir / "artifacts")
            if untracked:
                state.untracked_external_calls.extend({"path": path, "action_id": action["id"]}
                                                       for path in untracked)
                return self._observe(state, "blocked",
                                     "Untracked external output must be returned through LabOntology",
                                     untracked_external_calls=untracked)
            if not any(
                execution.get("status") in {"succeeded", "reconciled_succeeded"}
                for execution in state.skill_executions.values()
                if isinstance(execution, dict)
            ):
                raise ValueError("Cannot complete without a successful Skill result")
            return self._observe(state, "completed", action["reason"], completed=True)
        if kind == "request_human":
            return self._wait_human(state, action["question"])
        if kind == "agent_fallback":
            state.replan_required = False
            return self._execute_agent_fallback(state)
        state.replan_required = False
        skill = self.skills[action["skill_id"]]
        prerequisite_error = self._prerequisites(state, action, skill)
        if prerequisite_error:
            self._record_prerequisite_feedback(skill, action, prerequisite_error)
            return self._observe(state, "blocked", prerequisite_error)
        assessment = action["assessment"]
        concerns = assessment["uncertainties"] + assessment["authenticity_gaps"]
        if assessment["impact"] == "significant" and not assessment.get("authorization", "").strip():
            concerns.append("Significant impact: " + assessment["rationale"])
        if any(p.requires_confirmation and skill.id in p.applies_to for p in self.policies):
            concerns.append("Explicit execution policy requires human confirmation")
        if concerns:
            return self._wait_human(state, "; ".join(concerns))
        return self._execute(state)

    def _agent_fallback_error(self, state: MissionState, action: dict[str, Any]) -> str | None:
        if not state.replan_required:
            return "Agent fallback requires an explicit human approval first"
        if action.get("side_effect_level") != "read_only":
            return "Agent fallback is limited to read-only work"
        assessment = action.get("assessment")
        if not isinstance(assessment, dict):
            return "Agent fallback requires an assessment"
        if assessment.get("impact") != "routine":
            return "Agent fallback is limited to routine, low-risk work"
        if not isinstance(assessment.get("rationale"), str) or not assessment["rationale"].strip():
            return "Agent fallback assessment requires a rationale"
        for key in ("uncertainties", "authenticity_gaps"):
            if not isinstance(assessment.get(key), list) or not all(isinstance(x, str) for x in assessment[key]):
                return f"Agent fallback assessment requires {key} as a list of strings"
        if not isinstance(assessment.get("authorization"), str) or not assessment["authorization"].strip():
            return "Agent fallback requires the user's explicit approval"
        return None

    def _skill_snapshot(self, skill: SkillSpec) -> dict[str, Any]:
        knowledge = self.knowledge.get(skill.id, {})
        return {"contract": asdict(skill), "suite_id": knowledge.get("suite_id"),
                "registry_file": knowledge.get("registry_file")}

    def _prerequisites(self, state: MissionState, action: dict, skill: SkillSpec) -> str | None:
        prepared_error = self._prepared_skill_error(state, skill)
        if prepared_error:
            return prepared_error
        instruction_error = self._instruction_error(action, skill)
        if instruction_error:
            return instruction_error
        if action.get("skill_snapshot") != self._skill_snapshot(skill):
            return "Selected Skill implementation or suite changed; reassess before execution"
        if any(p.blocked and skill.id in p.applies_to for p in self.policies):
            return "Explicit policy blocks this Skill"
        missing_caps = sorted(set(skill.required_capabilities) - self.capabilities)
        if missing_caps:
            return f"Required capability unavailable: {missing_caps}"
        artifacts = {**state.artifacts, **action.get("inputs", {})}
        missing = [a for a in skill.input_artifacts if a not in artifacts or not Path(artifacts[a]).exists()]
        if missing:
            return f"Required inputs missing: {missing}"
        return None

    def _decision_arguments(self, action: dict[str, Any], skill: SkillSpec) -> dict[str, Any]:
        arguments = action.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("Decision arguments must be an object")
        bindings = skill.argument_bindings if isinstance(skill.argument_bindings, dict) else {}
        declared = bindings.get("parameters", {}) if isinstance(bindings.get("parameters", {}), dict) else {}
        unknown = sorted(set(arguments) - set(declared))
        if unknown:
            raise ValueError(f"Unknown declared argument(s) for {skill.id}: {unknown}")
        if not all(isinstance(value, (str, int, float, bool)) for value in arguments.values()):
            raise ValueError("Decision argument values must be strings, numbers, or booleans")
        return arguments

    def _prepared_skill_error(self, state: MissionState, skill: SkillSpec) -> str | None:
        """Require a fresh read for imported Skills.

        Hand-built legacy skills without an instruction source keep their old
        behavior; imported Skills are always checked at the action
        boundary and again immediately before execution.
        """
        source = self.knowledge.get(skill.id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path"):
            return None
        prepared = state.prepared_skill
        if not isinstance(prepared, dict) or prepared.get("skill_id") != skill.id:
            return "Skill requires prepare_skill before execution"
        path = Path(str(source["path"])).expanduser().resolve()
        if not path.is_file():
            return f"Skill document is unavailable: {path}"
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        recorded_hash = source.get("sha256")
        if recorded_hash and actual_hash != recorded_hash:
            return "Skill document changed; refresh the cache and reassess the action"
        if prepared.get("path") != str(path) or prepared.get("sha256") != actual_hash:
            return "Prepared Skill document changed; refresh with prepare_skill"
        return None

    def _record_prerequisite_feedback(self, skill: SkillSpec, action: dict[str, Any],
                                      error: str) -> None:
        if error.startswith("Required capability unavailable:"):
            event = "missing_capability"
        elif error.startswith("Required inputs missing:"):
            event = "missing_precondition"
        else:
            return
        self._feedback(event, skill.id, {"action_id": action.get("id"), "error": error})

    def _instruction_error(self, action: dict[str, Any], skill: SkillSpec) -> str | None:
        source = self.knowledge.get(skill.id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            return None
        path = Path(str(source["path"])).expanduser()
        if not path.is_file():
            return f"Skill document is unavailable: {path}"
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != source["sha256"]:
            return "Skill document changed; refresh the cache and reassess the action"
        reviewed = action.get("reviewed_instruction") or action.get("prepared_skill")
        if not isinstance(reviewed, dict):
            return "Skill decision requires a prepared Skill document"
        if str(reviewed.get("path")) != str(path.resolve()) or reviewed.get("sha256") != actual_hash:
            return "prepared Skill document does not match the current Skill document"
        return None

    def _retry_error(self, state: MissionState, action: dict[str, Any], skill: SkillSpec) -> str | None:
        retry_of = action.get("retry_of")
        if retry_of is None:
            return None
        if not isinstance(retry_of, str) or not retry_of:
            return "retry_of must name a prior action"
        prior = state.skill_executions.get(retry_of)
        if prior is None:
            return f"Retry target does not exist: {retry_of}"
        if prior.get("skill_id") != skill.id:
            return "Retry target belongs to a different Skill"
        if prior.get("status") not in {"failed", "timed_out"}:
            return "Retry target did not fail"
        if prior.get("retryable") is not True:
            return "Prior action is not retryable"
        if skill.side_effect_level != "read_only":
            return "Skill is not retryable because it is not read-only"
        retry_count = int(prior.get("retry_count", 0))
        if retry_count >= skill.retry_limit:
            return f"Retry limit reached for {skill.id}"
        action["retry_count"] = retry_count + 1
        return None

    def _wait_human(self, state: MissionState, question: str) -> MissionState:
        state.status, state.block_reason = "waiting_human", question
        state.supervisor_status = "waiting_human"
        self.store.save(state)
        self.store.event("human_decision_requested", {"action": state.pending_action["id"], "question": question})
        return state

    def _execute(self, state: MissionState) -> MissionState:
        action = state.pending_action
        skill = self.skills.get(action["skill_id"])
        if skill is None:
            return self._observe(state, "blocked", "Selected Skill is no longer registered; replan")
        error = self._prerequisites(state, action, skill)
        if error:
            self._record_prerequisite_feedback(skill, action, error)
            return self._observe(state, "blocked", error)
        state.artifacts.update(action.get("inputs", {}))
        # Every Skill is executed through the prepared document contract. A
        # script, when present, is merely an optional host-side accelerator.
        action["ticket_status"] = "waiting_external"
        state.status, state.block_reason = "waiting_agent", None
        state.supervisor_status = "waiting_external"
        state.skill_executions[action["id"]] = {
            "skill_id": skill.id,
            "status": "waiting_agent",
            "required_outputs": list(skill.outputs),
            "optional_script_available": bool(skill.optional_command or skill.optional_entrypoints),
        }
        self.store.save(state)
        self.store.event("agent_skill_waiting", {"action": action["id"], "skill": skill.id})
        return state

    def _execute_agent_fallback(self, state: MissionState) -> MissionState:
        action = state.pending_action
        action["execution_source"] = "agent_native"
        action["ticket_status"] = "waiting_external"
        state.status, state.block_reason = "waiting_agent", None
        state.supervisor_status = "waiting_external"
        state.skill_executions[action["id"]] = {
            "id": action["id"],
            "skill_id": None,
            "status": "waiting_agent",
            "execution_source": "agent_native",
            "required_outputs": [],
        }
        self.store.save(state)
        self.store.event("agent_fallback_waiting", {"action": action["id"]})
        return state

    def reconcile(self, outcome: str, summary: str, *, evidence: list[str] | None = None,
                  provided_artifacts: dict[str, str] | None = None) -> MissionState:
        """Resolve an interrupted process from external evidence without replaying it."""
        if outcome not in {"not_started", "succeeded", "failed", "unknown"}:
            raise ValueError("Reconciliation outcome must be not_started, succeeded, failed or unknown")
        if not summary.strip():
            raise ValueError("Reconciliation requires a summary")
        state = self._load()
        if state.status != "running" or not state.pending_action:
            raise ValueError("Only a running action can be reconciled")
        action = state.pending_action
        skill = self.skills.get(action.get("skill_id"))
        if skill is None:
            raise ValueError("Selected Skill is no longer registered; cannot reconcile its contract")
        snapshot = action.get("skill_snapshot")
        if snapshot is not None and snapshot != self._skill_snapshot(skill):
            raise ValueError("Selected Skill changed during interruption; cannot reconcile its contract")
        outputs = _materialize_artifacts(_artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts")
        if outcome == "succeeded":
            missing = sorted(set(skill.outputs) - outputs.keys())
            if missing:
                raise ValueError(f"Required reconciled outputs missing: {missing}")
            state.artifacts.update(outputs)
            state.skill_executions[action["id"]] = {
                "id": action["id"], "skill_id": skill.id, "status": "reconciled_succeeded",
                "outputs": outputs, "summary": summary, "evidence": evidence or [],
            }
        elif outputs:
            raise ValueError("Only a succeeded reconciliation may provide output artifacts")
        details = {"outcome": outcome, "summary": summary, "evidence": evidence or [], "outputs": outputs}
        self.store.event("reconciliation", {"action": action["id"], **details})
        return self._observe(state, f"reconciled_{outcome}", summary, evidence=evidence or [], outputs=outputs)

    def resume(self, *, action_id: str = "", provided_artifacts: dict[str, str] | None = None,
               summary: str = "", evidence: list[str] | None = None, agent_completed: bool = False,
               agent_failed: bool = False,
               confirmed: bool = False, rejected: bool = False, answer: str = "") -> MissionState:
        state = self._load()
        if confirmed and rejected:
            raise ValueError("Cannot both approve and reject an action")
        if action_id:
            if state.status != "waiting_agent" or not state.pending_action:
                raise ValueError("No external Skill is waiting for a result")
            if state.pending_action.get("id") != action_id:
                raise ValueError(f"External action does not match pending action: {action_id}")
        if state.status == "waiting_human":
            if (confirmed or rejected) and not answer.strip():
                raise ValueError("Record the actual user reply when approving or rejecting an action")
            if rejected:
                self._feedback("mission_resumed", state.pending_action.get("skill_id"),
                               {"action_id": state.pending_action["id"], "from_status": state.status})
                return self._observe(state, "rejected", answer or "User rejected the action")
            action = state.pending_action
            if action["kind"] == "request_human":
                if not answer.strip():
                    return state
                self._feedback("mission_resumed", action.get("skill_id"),
                               {"action_id": action["id"], "from_status": state.status})
                return self._observe(state, "human_answer", answer)
            assessment = action["assessment"]
            # Approval alone does not fill in missing facts. Return to reasoning
            # when the human supplies evidence, so the Agent reassesses the action.
            if assessment["uncertainties"] or assessment["authenticity_gaps"]:
                if not answer.strip():
                    return state
                self._feedback("mission_resumed", action.get("skill_id"),
                               {"action_id": action["id"], "from_status": state.status})
                return self._observe(state, "human_answer", answer)
            if not confirmed:
                return state
            self._feedback("mission_resumed", action.get("skill_id"),
                           {"action_id": action["id"], "from_status": state.status})
            state.observations.append({"action_id": action["id"], "status": "human_approved",
                                       "summary": answer or "User approved this action"})
            self.store.event("human_approved", {"action": action["id"], "answer": answer})
            return self._execute(state)
        if state.status != "waiting_agent":
            return state
        if agent_failed and (agent_completed or provided_artifacts):
            raise ValueError("Failed Agent execution cannot also report successful completion or outputs")
        if not (agent_completed or agent_failed or summary.strip() or provided_artifacts):
            return state
        self._feedback("mission_resumed", state.pending_action.get("skill_id"),
                       {"action_id": state.pending_action["id"], "from_status": state.status})
        if state.pending_action.get("execution_source") == "agent_native":
            action = state.pending_action
            action_id = action["id"]
            if agent_failed:
                if not summary.strip():
                    raise ValueError("Failed Agent fallback requires an explanation")
                state.skill_executions[action_id] = {
                    "id": action_id,
                    "skill_id": None,
                    "status": "failed",
                    "execution_source": "agent_native",
                    "outputs": {},
                    "error": summary,
                    "evidence": evidence or [],
                    "failure_kind": "agent_native",
                    "retryable": False,
                }
                return self._observe(
                    state, "failed", summary, evidence=evidence or [],
                    execution_source="agent_native",
                )
            outputs = _materialize_artifacts(
                _artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts"
            )
            state.artifacts.update(outputs)
            state.artifact_records.update(_artifact_records(outputs, action_id))
            state.skill_executions[action_id] = {
                "id": action_id,
                "skill_id": None,
                "status": "succeeded",
                "execution_source": "agent_native",
                "outputs": outputs,
                "summary": summary,
                "evidence": evidence or [],
            }
            return self._observe(
                state, "succeeded", summary or "Agent fallback completed without a textual result",
                outputs=outputs, evidence=evidence or [], execution_source="agent_native",
            )
        skill = self.skills.get(state.pending_action["skill_id"])
        if skill is None or state.pending_action.get("skill_snapshot") != self._skill_snapshot(skill):
            return self._observe(state, "blocked", "Selected Skill changed during Agent execution; reassess results")
        if agent_failed:
            if not summary.strip():
                raise ValueError("Failed Agent execution requires an explanation")
            state.skill_executions[state.pending_action["id"]] = {
                "id": state.pending_action["id"], "skill_id": skill.id, "status": "failed",
                "outputs": {}, "error": summary, "evidence": evidence or [],
                "failure_kind": "external_skill",
                "retryable": skill.side_effect_level == "read_only",
                "retry_count": 0,
            }
            return self._observe(state, "failed", summary, evidence=evidence or [])
        outputs = _materialize_artifacts(_artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts")
        missing = sorted(set(skill.outputs) - outputs.keys())
        if missing:
            raise ValueError(f"Required Agent outputs missing: {missing}")
        state.artifacts.update(outputs)
        state.artifact_records.update(_artifact_records(outputs, state.pending_action["id"]))
        state.skill_executions[state.pending_action["id"]] = {
            "id": state.pending_action["id"], "skill_id": skill.id, "status": "succeeded",
            "outputs": outputs, "summary": summary, "evidence": evidence or []}
        return self._observe(state, "succeeded", summary or "Agent Skill completed without a textual result",
                             outputs=outputs, evidence=evidence or [])

    def _observe(self, state: MissionState, status: str, summary: str,
                 *, completed: bool = False, **details: Any) -> MissionState:
        observation = {"action_id": state.pending_action["id"], "status": status, "summary": summary, **details}
        state.observations.append(observation)
        ticket = state.pending_action
        if ticket:
            state.action_history.append({
                "action_id": ticket.get("id"),
                "skill_id": ticket.get("skill_id"),
                "return_to": ticket.get("return_to", "labontology-skill"),
                "status": status,
            })
            if status in {"failed", "reconciled_failed"}:
                self._feedback("skill_failed", ticket.get("skill_id"), {
                    "action_id": ticket.get("id"),
                    "status": status,
                    "summary": summary,
                    "failure_kind": details.get("failure_kind"),
                })
        state.pending_action = None
        state.pending_ticket = None
        if status in {"human_answer", "rejected"}:
            state.replan_required = True
        elif completed or status in {"succeeded", "failed", "blocked", "reconciled_failed"}:
            state.replan_required = False
        state.status = "completed" if completed else "awaiting_decision"
        state.block_reason = None
        state.supervisor_status = "completed" if completed else "needs_action"
        self.store.save(state)
        self.store.event("observation", observation)
        if completed:
            self.store.experiences.record_mission(state)
        return state
