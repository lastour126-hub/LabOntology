import hashlib

import pytest

from core.runtime.agent_loop import AgentRuntime
from core.runtime.models import SkillSpec
from core.runtime.state_store import StateStore


def _runtime(tmp_path):
    document = tmp_path / "SKILL.md"
    document.write_text("# Worker\nRead this before acting.", encoding="utf-8")
    source = {
        "path": str(document),
        "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
    }
    skill = SkillSpec("lookup", [])
    runtime = AgentRuntime(
        {skill.id: skill},
        StateStore(tmp_path / "runs", "mission"),
        skill_knowledge={"lookup": {"instruction_source": source}},
    )
    runtime.start("Determine whether the sample needs review")
    return runtime, document, source


def _choose():
    return {
        "kind": "skill",
        "skill_id": "lookup",
        "reason": "Resolve the current task gap",
        "assessment": {
            "impact": "routine",
            "rationale": "Verified local operation",
            "uncertainties": [],
            "authenticity_gaps": [],
        },
    }


def test_prepare_skill_returns_content_and_persists_digest(tmp_path):
    runtime, document, source = _runtime(tmp_path)

    prepared = runtime.prepare_skill("lookup")

    assert prepared["skill_id"] == "lookup"
    assert prepared["path"] == str(document.resolve())
    assert prepared["sha256"] == source["sha256"]
    assert "Read this before acting." in prepared["content"]
    persisted = runtime.store.load().prepared_skill
    assert persisted == {
        "skill_id": "lookup",
        "path": str(document.resolve()),
        "sha256": source["sha256"],
        "prepared_at": prepared["prepared_at"],
    }
    assert "content" not in runtime.context()["mission"]["prepared_skill"]
    runtime.assert_skill_prepared("lookup")


def test_agent_worker_requires_prepare_before_decision(tmp_path):
    runtime, _, _ = _runtime(tmp_path)

    with pytest.raises(ValueError, match="prepare_skill"):
        runtime.decide(_choose())


def test_prepared_agent_worker_can_receive_execution_ticket(tmp_path):
    runtime, _, _ = _runtime(tmp_path)
    runtime.prepare_skill("lookup")

    state = runtime.decide(_choose())

    assert state.status == "waiting_agent"
    assert state.pending_action["prepared_skill"]["skill_id"] == "lookup"


def test_changed_worker_document_invalidates_preparation(tmp_path):
    runtime, document, _ = _runtime(tmp_path)
    runtime.prepare_skill("lookup")
    document.write_text("# Worker\nChanged after preparation.", encoding="utf-8")

    with pytest.raises(ValueError, match="changed|refresh"):
        runtime.decide(_choose())


def test_changed_worker_document_is_rejected_before_prepare(tmp_path):
    runtime, document, _ = _runtime(tmp_path)
    document.write_text("# Worker\nChanged before preparation.", encoding="utf-8")

    with pytest.raises(ValueError, match="changed|refresh"):
        runtime.prepare_skill("lookup")
