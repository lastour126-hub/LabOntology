import json
import sys
from pathlib import Path

from core.runtime import agent_loop
from core.runtime.models import SkillSpec
from core.runtime.state_store import StateStore


def controller(tmp_path, skills):
    return agent_loop.AgentRuntime(
        {skill.id: skill for skill in skills},
        StateStore(tmp_path, "mission"),
    )


def choose(skill_id):
    return {
        "kind": "skill",
        "skill_id": skill_id,
        "reason": "Use the selected procedure for this task",
        "assessment": {
            "impact": "routine",
            "rationale": "The action is a read-only preparation step",
            "uncertainties": [],
            "authenticity_gaps": [],
        },
    }


def test_agent_action_exposes_a_return_ticket(tmp_path):
    skill = SkillSpec(
        "lookup", [],
        outputs={"artifact:report": "report.txt"},
    )
    runtime = controller(tmp_path, [skill])
    runtime.start("Get a report")

    state = runtime.decide(choose("lookup"))

    assert state.pending_action["return_to"] == "labontology-skill"
    assert state.pending_action["ticket_status"] == "waiting_external"
    context = runtime.context()
    assert context["supervisor_status"] == "waiting_external"
    assert context["pending_ticket"]["action_id"] == "action:1"


def test_process_action_returns_to_context_without_external_resume(tmp_path):
    skill = SkillSpec(
        "lookup", [sys.executable, "-c", "print('verified')"],
    )
    runtime = controller(tmp_path, [skill])
    runtime.start("Verify a local record")

    state = runtime.decide(choose("lookup"))
    context = runtime.context()

    assert state.status == "waiting_agent"
    assert state.pending_action is not None
    assert context["worker_cycle"] == {
        "entrypoint": "act",
        "after_act": "resume",
        "requires_resume": True,
        "requires_reconcile": False,
        "resume_mode": "external_worker",
        "status": "waiting_agent",
    }


def test_agent_action_context_requires_resume_before_context(tmp_path):
    skill = SkillSpec("lookup", [])
    runtime = controller(tmp_path, [skill])
    runtime.start("Get an external report")
    runtime.decide(choose("lookup"))

    context = runtime.context()

    assert context["worker_cycle"] == {
        "entrypoint": "act",
        "after_act": "resume",
        "requires_resume": True,
        "requires_reconcile": False,
        "resume_mode": "external_worker",
        "status": "waiting_agent",
    }


def test_human_wait_exposes_human_resume_mode(tmp_path):
    skill = SkillSpec("operation", [sys.executable, "-c", "print('no')"])
    runtime = controller(tmp_path, [skill])
    runtime.start("Approve an operation")
    decision = choose("operation")
    decision["assessment"]["impact"] = "significant"
    runtime.decide(decision)

    context = runtime.context()

    assert context["worker_cycle"] == {
        "entrypoint": "act",
        "after_act": "resume",
        "requires_resume": True,
        "requires_reconcile": False,
        "resume_mode": "human_decision",
        "status": "waiting_human",
    }


def test_running_action_requires_reconcile_before_replanning(tmp_path):
    skill = SkillSpec("operation", [sys.executable, "-c", "print('no')"])
    runtime = controller(tmp_path, [skill])
    state = runtime.start("Operate")
    state.status = "running"
    state.pending_action = {**choose("operation"), "id": "action:1"}
    runtime.store.save(state)

    context = runtime.context()

    assert context["worker_cycle"] == {
        "entrypoint": "act",
        "after_act": "reconcile",
        "requires_resume": False,
        "requires_reconcile": True,
        "resume_mode": None,
        "status": "running",
    }


def test_resume_closes_external_action_and_returns_to_supervisor(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("verified", encoding="utf-8")
    skill = SkillSpec(
        "lookup", [],
        outputs={"artifact:report": "report.txt"},
    )
    runtime = controller(tmp_path, [skill])
    runtime.start("Get a report")
    runtime.decide(choose("lookup"))

    state = runtime.resume(
        action_id="action:1", agent_completed=True,
        summary="The report is ready", provided_artifacts={"artifact:report": str(source)},
    )

    assert state.status == "awaiting_decision"
    assert state.pending_action is None
    assert state.pending_ticket is None
    assert state.supervisor_status == "needs_action"
    assert state.action_history[-1]["action_id"] == "action:1"
    assert state.action_history[-1]["return_to"] == "labontology-skill"
    assert Path(state.artifacts["artifact:report"]).read_text(encoding="utf-8") == "verified"
    assert state.artifact_records["artifact:report"]["valid"] is True
    assert state.artifact_records["artifact:report"]["action_id"] == "action:1"


def test_resume_rejects_a_stale_action_ticket(tmp_path):
    skill = SkillSpec("lookup", [])
    runtime = controller(tmp_path, [skill])
    runtime.start("Get a report")
    runtime.decide(choose("lookup"))

    try:
        runtime.resume(action_id="action:99", agent_completed=True, summary="wrong action")
    except ValueError as exc:
        assert "action" in str(exc)
    else:
        raise AssertionError("stale action ticket was accepted")

    persisted = json.loads(runtime.store.state_path.read_text(encoding="utf-8"))
    assert persisted["pending_action"]["id"] == "action:1"


def test_untracked_artifact_prevents_task_completion(tmp_path):
    runtime = controller(tmp_path, [])
    runtime.start("Prepare a task")
    artifact_dir = runtime.store.run_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "bypassed.txt").write_text("written outside the supervisor", encoding="utf-8")

    state = runtime.decide({"kind": "complete", "reason": "The task is complete"})

    assert state.status == "awaiting_decision"
    assert state.supervisor_status == "needs_action"
    assert state.untracked_external_calls
    assert state.observations[-1]["status"] == "blocked"
