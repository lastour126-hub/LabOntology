"""One-action execution loop directed by the host Agent, not an embedded LLM."""
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .invoker import SkillInvoker
from .models import ExecutionPolicySpec, MissionState, SkillExecution, SkillSpec
from .state_store import StateStore


def _artifact_paths(artifacts: dict[str, str]) -> dict[str, str]:
    result = {}
    for name, value in artifacts.items():
        path = Path(value).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Artifact does not exist: {name}={path}")
        result[name] = str(path)
    return result


class AgentRuntime:
    def __init__(
        self, skills: dict[str, SkillSpec], invoker: SkillInvoker, store: StateStore,
        *, available_capabilities: set[str] | None = None,
        policies: list[ExecutionPolicySpec] | None = None,
        skill_knowledge: dict[str, dict[str, Any]] | None = None,
        workflow_references: list[dict[str, Any]] | None = None,
    ):
        self.skills, self.invoker, self.store = skills, invoker, store
        self.capabilities = set(available_capabilities or [])
        self.policies = policies or []
        self.knowledge = skill_knowledge or {}
        self.workflows = workflow_references or []

    def _load(self) -> MissionState:
        state = self.store.load()
        if state.mode != "agent":
            raise ValueError("Mission is not an Agent mission; create a new Agent mission")
        self.capabilities.update(state.available_capabilities)
        state.available_capabilities = sorted(self.capabilities)
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
                             artifacts=_artifact_paths(artifacts or {}), start_skill=start_skill)
        self.store.save(state)
        self.store.event("mission_created", {"goal": goal, "mode": "agent"})
        return state

    def context(self) -> dict[str, Any]:
        state = self._load()
        cards: list[tuple[int, dict[str, Any]]] = []
        goal_terms = set(re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", state.goal.lower()))
        for skill in self.skills.values():
            knowledge = self.knowledge.get(skill.id, {})
            description = str(knowledge.get("description") or "")
            searchable = f"{skill.id} {description} {' '.join(skill.goal_types)} {' '.join(skill.triggers)}".lower()
            score = sum(term in searchable for term in goal_terms)
            card = {
                "id": skill.id,
                "name": skill.id,
                "description": description,
                "suite_id": knowledge.get("suite_id"),
                "inputs": list(skill.input_artifacts),
                "required_capabilities": list(skill.required_capabilities),
                "side_effect_level": skill.side_effect_level,
                "missing_inputs": [artifact for artifact in skill.input_artifacts if artifact not in state.artifacts],
                "missing_capabilities": sorted(set(skill.required_capabilities) - self.capabilities),
            }
            cards.append((score, card))
        candidates = [card for _, card in sorted(cards, key=lambda item: (-item[0], item[1]["id"]))[:5]]
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
        return {"mission": state.to_dict(), "skills": candidates, "candidate_count": len(self.skills),
                "available_capabilities": sorted(self.capabilities),
                "start_skill": state.start_skill,
                "retry_candidates": retry_candidates,
                "workflow_references": self.workflows,
                "policies": [asdict(p) for p in self.policies],
                "next": "Host Agent: inspect evidence, choose one action, observe, then replan."}

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
        if kind not in {"skill", "request_human", "complete"}:
            raise ValueError("Decision kind must be skill, request_human or complete")
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
            instruction_error = self._instruction_error(action, self.skills[action["skill_id"]])
            if instruction_error:
                raise ValueError(instruction_error)
            action["skill_snapshot"] = self._skill_snapshot(self.skills[action["skill_id"]])
            retry_error = self._retry_error(state, action, self.skills[action["skill_id"]])
            if retry_error:
                raise ValueError(retry_error)
        if kind == "request_human" and not str(action.get("question", "")).strip():
            raise ValueError("Human decision requires a question")
        action["id"] = f"action:{len(state.decisions) + 1}"
        state.decisions.append(deepcopy(action))
        state.pending_action = action
        self.store.event("agent_decision", action)
        if kind == "complete":
            return self._observe(state, "completed", action["reason"], completed=True)
        if kind == "request_human":
            return self._wait_human(state, action["question"])
        skill = self.skills[action["skill_id"]]
        prerequisite_error = self._prerequisites(state, action, skill)
        if prerequisite_error:
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

    def _skill_snapshot(self, skill: SkillSpec) -> dict[str, Any]:
        knowledge = self.knowledge.get(skill.id, {})
        return {"contract": asdict(skill), "suite_id": knowledge.get("suite_id"),
                "registry_file": knowledge.get("registry_file")}

    def _prerequisites(self, state: MissionState, action: dict, skill: SkillSpec) -> str | None:
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
        if skill.execution_mode != "agent" and (not skill.runnable or not skill.command):
            return "Skill has no runnable process command"
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

    def _instruction_error(self, action: dict[str, Any], skill: SkillSpec) -> str | None:
        if skill.execution_mode == "agent":
            return None
        source = self.knowledge.get(skill.id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            return None
        path = Path(str(source["path"])).expanduser()
        if not path.is_file():
            return f"Skill document is unavailable: {path}"
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != source["sha256"]:
            return "Skill document changed; refresh the cache and reassess the action"
        reviewed = action.get("reviewed_instruction")
        if not isinstance(reviewed, dict):
            return "Script Skill decision requires reviewed_instruction with the current path and sha256"
        if str(reviewed.get("path")) != str(path.resolve()) or reviewed.get("sha256") != actual_hash:
            return "reviewed_instruction does not match the current Skill document"
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
            return self._observe(state, "blocked", error)
        state.artifacts.update(action.get("inputs", {}))
        if skill.execution_mode == "agent":
            state.status, state.block_reason = "waiting_agent", None
            state.skill_executions[action["id"]] = {
                "skill_id": skill.id, "status": "waiting_agent", "required_outputs": list(skill.outputs)}
            self.store.save(state)
            self.store.event("agent_skill_waiting", {"action": action["id"], "skill": skill.id})
            return state
        # Persist before invoking. After an interruption, a caller must reconcile;
        # context/run never automatically repeat a possibly impactful operation.
        state.status, state.block_reason = "running", None
        self.store.save(state)
        run_dir = self.store.run_dir / "skill-executions" / action["id"].replace(":", "_")
        if action.get("retry_of"):
            self.store.event("skill_retry_started", {"action": action["id"], "skill": skill.id,
                                                      "retry_of": action["retry_of"],
                                                      "retry_count": action["retry_count"]})
        self.store.event("skill_started", {"action": action["id"], "skill": skill.id})
        try:
            result = self.invoker.run(skill, run_dir, {a: state.artifacts[a] for a in skill.input_artifacts},
                                      action.get("arguments", {}))
        except OSError as exc:
            result = SkillExecution(action["id"], skill.id, "failed", error=str(exc),
                                    failure_kind="launch_error",
                                    retryable=skill.side_effect_level == "read_only")
        record = asdict(result)
        record["id"] = action["id"]
        record["run_dir"] = str(run_dir)
        record["retry_count"] = action.get("retry_count", 0)
        if action["assessment"]["impact"] == "significant":
            record["retryable"] = False
        if action.get("retry_of"):
            record["retry_of"] = action["retry_of"]
        state.skill_executions[action["id"]] = record
        if result.status == "succeeded":
            state.artifacts.update(result.outputs)
        logs = {}
        for name in ("stdout", "stderr"):
            path = run_dir / f"{name}.log"
            if path.exists():
                logs[name] = path.read_text(encoding="utf-8", errors="replace")[-12000:]
        return self._observe(state, result.status, result.error or "Skill completed", outputs=result.outputs, **logs)

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
        outputs = _artifact_paths(provided_artifacts or {})
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

    def resume(self, *, provided_artifacts: dict[str, str] | None = None,
               summary: str = "", evidence: list[str] | None = None, agent_completed: bool = False,
               agent_failed: bool = False,
               confirmed: bool = False, rejected: bool = False, answer: str = "") -> MissionState:
        state = self._load()
        if confirmed and rejected:
            raise ValueError("Cannot both approve and reject an action")
        if state.status == "waiting_human":
            if (confirmed or rejected) and not answer.strip():
                raise ValueError("Record the actual user reply when approving or rejecting an action")
            if rejected:
                return self._observe(state, "rejected", answer or "User rejected the action")
            action = state.pending_action
            if action["kind"] == "request_human":
                if not answer.strip():
                    return state
                return self._observe(state, "human_answer", answer)
            assessment = action["assessment"]
            # Approval alone does not fill in missing facts. Return to reasoning
            # when the human supplies evidence, so the Agent reassesses the action.
            if assessment["uncertainties"] or assessment["authenticity_gaps"]:
                if not answer.strip():
                    return state
                return self._observe(state, "human_answer", answer)
            if not confirmed:
                return state
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
        skill = self.skills.get(state.pending_action["skill_id"])
        if skill is None or state.pending_action.get("skill_snapshot") != self._skill_snapshot(skill):
            return self._observe(state, "blocked", "Selected Skill changed during Agent execution; reassess results")
        if agent_failed:
            if not summary.strip():
                raise ValueError("Failed Agent execution requires an explanation")
            state.skill_executions[state.pending_action["id"]] = {
                "id": state.pending_action["id"], "skill_id": skill.id, "status": "failed",
                "outputs": {}, "error": summary, "evidence": evidence or []}
            return self._observe(state, "failed", summary, evidence=evidence or [])
        outputs = _artifact_paths(provided_artifacts or {})
        missing = sorted(set(skill.outputs) - outputs.keys())
        if missing:
            raise ValueError(f"Required Agent outputs missing: {missing}")
        state.artifacts.update(outputs)
        state.skill_executions[state.pending_action["id"]] = {
            "id": state.pending_action["id"], "skill_id": skill.id, "status": "succeeded",
            "outputs": outputs, "summary": summary, "evidence": evidence or []}
        return self._observe(state, "succeeded", summary or "Agent Skill completed without a textual result",
                             outputs=outputs, evidence=evidence or [])

    def _observe(self, state: MissionState, status: str, summary: str,
                 *, completed: bool = False, **details: Any) -> MissionState:
        observation = {"action_id": state.pending_action["id"], "status": status, "summary": summary, **details}
        state.observations.append(observation)
        state.pending_action = None
        state.status = "completed" if completed else "awaiting_decision"
        state.block_reason = None
        self.store.save(state)
        self.store.event("observation", observation)
        return state
