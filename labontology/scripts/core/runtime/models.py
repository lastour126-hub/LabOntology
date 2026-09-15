from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowNode:
    id: str
    node_type: str
    skill_id: str | None = None
    order: int = 0
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    next_node_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowNode":
        return cls(
            id=data["id"],
            node_type=data.get("node_type", data.get("type", "skill_call")),
            skill_id=data.get("skill"),
            order=int(data.get("order", 0)),
            input_artifacts=list(data.get("inputs", [])),
            output_artifacts=list(data.get("outputs", [])),
            next_node_id=data.get("next"),
        )


@dataclass
class SkillFlow:
    id: str
    nodes: list[FlowNode]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillFlow":
        nodes = [FlowNode.from_dict(item) for item in data.get("nodes", data.get("steps", []))]
        return cls(data["id"], sorted(nodes, key=lambda node: node.order))


@dataclass
class SkillSpec:
    id: str
    command: list[str]
    outputs: dict[str, str] = field(default_factory=dict)
    input_artifacts: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    working_dir: str | None = None
    timeout_seconds: int = 300
    side_effect_level: str = "read_only"
    execution_mode: str = "process"
    runnable: bool = True
    argument_bindings: dict[str, Any] = field(default_factory=dict)
    fixed_arguments: list[str] = field(default_factory=list)
    knowledge_dir: str | None = None
    decision_policy: dict[str, Any] = field(default_factory=dict)
    goal_types: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    recommended_next_skills: list[str] = field(default_factory=list)
    retry_limit: int = 1


@dataclass
class ExecutionPolicySpec:
    id: str
    applies_to: list[str] = field(default_factory=list)
    blocked: bool = False
    requires_confirmation: bool = False


@dataclass
class SkillExecution:
    id: str
    skill_id: str
    status: str
    outputs: dict[str, str] = field(default_factory=dict)
    return_code: int | None = None
    error: str | None = None
    failure_kind: str | None = None
    retryable: bool = False
    retry_count: int = 0


@dataclass
class MissionState:
    mission_id: str
    status: str = "created"
    artifacts: dict[str, str] = field(default_factory=dict)
    skill_executions: dict[str, dict[str, Any]] = field(default_factory=dict)
    block_reason: str | None = None
    mode: str = "agent"
    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    available_capabilities: list[str] = field(default_factory=list)
    start_skill: str | None = None
    suite_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "status": self.status,
            "artifacts": self.artifacts,
            "skill_executions": self.skill_executions,
            "block_reason": self.block_reason,
            "mode": self.mode,
            "goal": self.goal,
            "constraints": self.constraints,
            "decisions": self.decisions,
            "observations": self.observations,
            "pending_action": self.pending_action,
            "available_capabilities": self.available_capabilities,
            "start_skill": self.start_skill,
            "suite_id": self.suite_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MissionState":
        return cls(
            mission_id=data["mission_id"],
            status=data.get("status", "created"),
            artifacts=dict(data.get("artifacts", {})),
            skill_executions=dict(data.get("skill_executions", {})),
            block_reason=data.get("block_reason"),
            mode=data.get("mode", "agent"),
            goal=data.get("goal", ""),
            constraints=list(data.get("constraints", [])),
            decisions=list(data.get("decisions", [])),
            observations=list(data.get("observations", [])),
            pending_action=data.get("pending_action"),
            available_capabilities=list(data.get("available_capabilities", [])),
            start_skill=data.get("start_skill"),
            suite_id=data.get("suite_id"),
        )
