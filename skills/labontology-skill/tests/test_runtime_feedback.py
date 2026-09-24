import hashlib
import json
import sys

from core.runtime.agent_loop import AgentRuntime
from core.runtime.feedback import FeedbackStore, repeated_problems
from core.runtime.models import SkillSpec
from core.runtime.state_store import StateStore


def test_feedback_store_appends_jsonl_and_omits_reasoning_fields(tmp_path):
    store = FeedbackStore(tmp_path)

    record = store.append(
        "skill_failed",
        "mission:1",
        "lookup",
        {
            "summary": "The source was unavailable",
            "reason": "private chain",
            "rationale": "private rationale",
            "nested": {"analysis": "private analysis", "path": "source.txt"},
        },
    )

    assert record["event"] == "skill_failed"
    assert record["skill_id"] == "lookup"
    assert record["details"] == {
        "summary": "The source was unavailable",
        "nested": {"path": "source.txt"},
    }
    lines = (tmp_path / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == record
    assert store.aggregate(event="skill_failed", skill_id="lookup") == [record]


def test_runtime_records_observable_feedback_for_preparation_and_resume(tmp_path):
    document = tmp_path / "SKILL.md"
    document.write_text("# Worker", encoding="utf-8")
    source = {"path": str(document), "sha256": hashlib.sha256(document.read_bytes()).hexdigest()}
    skill = SkillSpec("lookup", [])
    runtime = AgentRuntime(
        {skill.id: skill}, StateStore(tmp_path / "runs", "mission"),
        skill_knowledge={"lookup": {"instruction_source": source}},
    )
    runtime.start("Get a report")
    runtime.prepare_skill("lookup")
    runtime.decide({
        "kind": "skill", "skill_id": "lookup", "reason": "Get report",
        "assessment": {
            "impact": "routine", "rationale": "Routine lookup",
            "uncertainties": [], "authenticity_gaps": [],
        },
    })
    runtime.resume(summary="Report received")

    events = runtime.store.feedback.aggregate()
    assert [item["event"] for item in events] == ["skill_prepared", "mission_resumed"]
    assert events[-1]["details"] == {"action_id": "action:1", "from_status": "waiting_agent"}


def test_runtime_records_missing_capability_and_skill_failure(tmp_path):
    blocked = SkillSpec("device", [],
                        required_capabilities=["cap:measure"])
    failed = SkillSpec("check", optional_command=[sys.executable, "-c", "raise SystemExit(2)"])
    runtime = AgentRuntime(
        {blocked.id: blocked, failed.id: failed}, StateStore(tmp_path, "mission"),
    )
    runtime.start("Check readiness")
    choose = {
        "kind": "skill", "skill_id": "device", "reason": "Measure",
        "assessment": {
            "impact": "routine", "rationale": "Need measurement",
            "uncertainties": [], "authenticity_gaps": [],
        },
    }
    runtime.decide(choose)
    runtime.decide({**choose, "skill_id": "check", "reason": "Run check"})
    runtime.resume(agent_failed=True, summary="Optional check failed")

    events = runtime.store.feedback.aggregate()
    assert any(item["event"] == "missing_capability" for item in events)
    assert any(item["event"] == "skill_failed" for item in events)


def test_repeated_problems_are_grouped_deterministically_and_only_suggest_safe_targets():
    feedback = [
        {"event": "skill_failed", "skill_id": "lookup"},
        {"event": "missing_precondition", "skill_id": "lookup"},
        {"event": "missing_precondition", "skill_id": "lookup"},
        {"event": "missing_precondition", "skill_id": "lookup"},
        {"event": "skill_failed", "skill_id": "lookup"},
        {"event": "skill_failed", "skill_id": "other"},
    ]

    suggestions = repeated_problems(feedback)

    assert suggestions == [{
        "event": "missing_precondition", "skill_id": "lookup", "count": 3,
        "proposed_patch_target": {
            "entity_id": "skill:lookup", "fields": ["preconditions", "documentation"],
        },
    }]
