import hashlib
import json
import sys
from pathlib import Path

import pytest

from core.runtime import agent_loop
from core.runtime.models import ExecutionPolicySpec, SkillSpec
from core.runtime.state_store import StateStore


def controller(tmp_path, skills, **kwargs):
    return agent_loop.AgentRuntime(
        {s.id: s for s in skills}, StateStore(tmp_path, "mission"), **kwargs
    )


def choose(skill, **assessment):
    return {"kind": "skill", "skill_id": skill, "reason": "Resolve the current task gap",
            "assessment": {"impact": "routine", "rationale": "Verified local operation",
                           "uncertainties": [], "authenticity_gaps": [], **assessment}}


def test_knowledge_agent_without_artifacts_returns_to_decision_and_can_be_reused(tmp_path):
    skill = SkillSpec("lookup", [])
    runtime = controller(tmp_path, [skill])
    assert runtime.start("Determine whether a device experiment is needed").status == "awaiting_decision"
    assert runtime.decide(choose("lookup")).status == "waiting_agent"
    state = runtime.resume(summary="Literature is inconclusive", evidence=["doi:example"])
    assert state.status == "awaiting_decision"
    assert state.observations[-1]["summary"] == "Literature is inconclusive"
    assert state.observations[-1]["evidence"] == ["doi:example"]
    assert runtime.decide(choose("lookup")).status == "waiting_agent"
    state = runtime.resume(agent_completed=True)
    assert len(state.skill_executions) == 2
    assert state.artifacts == {}
    reloaded = controller(tmp_path, [skill]).context()
    assert reloaded["mission"]["goal"] == "Determine whether a device experiment is needed"
    assert len(reloaded["mission"]["decisions"]) == 2


def test_script_backed_document_worker_waits_for_host_instead_of_running_script(tmp_path):
    marker = tmp_path / "ran.txt"
    skill = SkillSpec(
        "lookup",
        optional_command=[sys.executable, "-c", f"from pathlib import Path; Path(r'{marker}').write_text('ran')"],
    )
    runtime = controller(tmp_path, [skill], skill_knowledge={"lookup": {"description": "Inspect records"}})
    runtime.start("Inspect records")

    state = runtime.decide(choose("lookup"))

    assert state.status == "waiting_agent"
    assert state.skill_executions["action:1"]["status"] == "waiting_agent"
    assert not marker.exists()


def test_agent_context_exposes_a_task_artifact_directory(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("lookup", [])])
    runtime.start("Create a report")

    context = runtime.context()

    artifact_dir = Path(context["artifact_dir"])
    assert artifact_dir == runtime.store.run_dir / "artifacts"
    assert artifact_dir.is_dir()


def test_agent_outputs_are_copied_into_the_task_artifact_directory(tmp_path):
    source = tmp_path / "desktop" / "plan.md"
    source.parent.mkdir()
    source.write_text("plan", encoding="utf-8")
    skill = SkillSpec("planner", [], outputs={"artifact:plan": "plan.md"})
    runtime = controller(tmp_path, [skill])
    runtime.start("Create a plan")
    runtime.decide(choose("planner"))

    state = runtime.resume(agent_completed=True, provided_artifacts={"artifact:plan": str(source)})

    stored = Path(state.artifacts["artifact:plan"])
    assert stored.parent == runtime.store.run_dir / "artifacts"
    assert stored.read_text(encoding="utf-8") == "plan"
    assert source.is_file()


def test_process_runs_one_chosen_action_without_a_flow(tmp_path):
    skills = [SkillSpec(name, [sys.executable, "-c", "print('observed')"])
              for name in ["knowledge", "device"]]
    runtime = controller(tmp_path, skills, skill_knowledge={
        "knowledge": {"description": "Inspect records"},
        "device": {"description": "Inspect devices"},
    })
    runtime.start("Inspect first")
    state = runtime.decide(choose("knowledge"))
    assert state.status == "waiting_agent"
    assert [r["skill_id"] for r in state.skill_executions.values()] == ["knowledge"]
    assert not runtime.context()["mission"]["observations"]
    assert set(s["id"] for s in runtime.context()["skills"]) == {"knowledge", "device"}


def test_process_passes_declared_decision_arguments_to_the_skill(tmp_path):
    skill = SkillSpec(
        "script",
        [sys.executable, "-c", "import argparse; p=argparse.ArgumentParser(); p.add_argument('--text'); a=p.parse_args(); print(a.text)"],
        argument_bindings={"parameters": {"text": {"flag": "--text"}}},
    )
    runtime = controller(tmp_path, [skill])
    runtime.start("Run local script")

    state = runtime.decide({**choose("script"), "arguments": {"text": "from-decision"}})

    assert state.status == "waiting_agent"
    assert state.pending_action["arguments"] == {"text": "from-decision"}
    runtime.resume(agent_completed=True, summary="Script result was returned by the host")
    with pytest.raises(ValueError, match="Unknown declared argument"):
        runtime.decide({**choose("script"), "arguments": {"unknown": "value"}})


def test_process_skill_requires_current_skill_document_review(tmp_path):
    document = tmp_path / "SKILL.md"
    document.write_text("Do not guess output paths.", encoding="utf-8")
    source = {"path": str(document), "sha256": hashlib.sha256(document.read_bytes()).hexdigest()}
    skill = SkillSpec("script", optional_command=[sys.executable, "-c", "print('done')"])
    runtime = controller(tmp_path, [skill], skill_knowledge={"script": {
        "instruction_source": source}})
    runtime.start("Run script")
    with pytest.raises(ValueError, match="prepare_skill"):
        runtime.decide(choose("script"))
    runtime.prepare_skill("script")
    state = runtime.decide(choose("script"))
    assert state.status == "waiting_agent"


def test_process_skill_rejects_stale_document_review(tmp_path):
    document = tmp_path / "SKILL.md"
    document.write_text("v1", encoding="utf-8")
    source = {"path": str(document), "sha256": hashlib.sha256(document.read_bytes()).hexdigest()}
    skill = SkillSpec("script", optional_command=[sys.executable, "-c", "print('done')"])
    runtime = controller(tmp_path, [skill], skill_knowledge={"script": {"instruction_source": source}})
    runtime.start("Run script")
    runtime.prepare_skill("script")
    document.write_text("v2", encoding="utf-8")
    with pytest.raises(ValueError, match="changed|refresh"):
        runtime.decide(choose("script"))


def test_start_skill_is_persisted_as_agent_hint(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("plan", []), SkillSpec("lookup", [])])
    state = runtime.start("Continue an existing experiment", start_skill="plan")
    assert state.start_skill == "plan"
    assert runtime.context()["start_skill"] == "plan"


def test_unknown_start_skill_is_rejected(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("plan", [])])
    with pytest.raises(ValueError, match="Unknown start Skill"):
        runtime.start("Continue", start_skill="missing")


@pytest.mark.parametrize("assessment, executions", [
    ({"impact": "significant"}, 1), ({"uncertainties": ["Actual concentration unknown"]}, 0),
    ({"authenticity_gaps": ["Unverified device calibration"]}, 0),
])
def test_agent_assessment_requests_human_for_specific_action_only(tmp_path, assessment, executions):
    skill = SkillSpec("operation", [sys.executable, "-c", "print('done')"])
    runtime = controller(tmp_path, [skill])
    runtime.start("Evaluate operation")
    state = runtime.decide(choose("operation", **assessment))
    assert state.status == "waiting_human"
    assert state.skill_executions == {}
    assert runtime.resume().status == "waiting_human"
    state = runtime.resume(confirmed=True, answer="Checked source and approved this exact operation")
    assert state.status == ("waiting_agent" if executions else "awaiting_decision")
    assert len(state.skill_executions) == executions
    if executions:
        assert state.status == "waiting_agent"
    else:
        assert runtime.decide(choose("operation", **assessment)).status == "waiting_human"


def test_human_rejection_returns_to_replanning_without_execution(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("operation", [sys.executable, "-c", "print('no')"])])
    runtime.start("Review")
    runtime.decide(choose("operation", impact="significant"))
    state = runtime.resume(rejected=True, answer="Get independent evidence first")
    assert state.status == "awaiting_decision"
    assert not state.skill_executions
    assert state.observations[-1]["summary"] == "Get independent evidence first"


def test_agent_can_ask_question_without_a_skill_or_static_gate(tmp_path):
    runtime = controller(tmp_path, [])
    runtime.start("Identify sample")
    state = runtime.decide({"kind": "request_human", "reason": "No verifiable source",
                            "question": "Which sample is in the tray?"})
    assert state.status == "waiting_human"
    state = runtime.resume(answer="Sample B")
    assert state.status == "awaiting_decision"
    assert state.observations[-1]["summary"] == "Sample B"


def test_human_answer_requires_replanning_before_completion(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("operation", [sys.executable, "-c", "print('done')"])])
    runtime.start("Analyze the sample")
    runtime.decide({"kind": "request_human", "reason": "A sample property is missing",
                    "question": "Which sample should be analyzed?"})

    state = runtime.resume(answer="Sample B")

    assert state.status == "awaiting_decision"
    context = runtime.context()
    assert context["replan_required"] is True
    assert context["next"] == (
        "Host Agent: reassess the goal with the human answer, read context, and select a Worker; "
        "for an explicitly approved low-risk read-only fallback, use agent_fallback; "
        "do not complete or compute outside a Worker or approved fallback."
    )
    with pytest.raises(ValueError, match="replan"):
        runtime.decide({"kind": "complete", "reason": "The task is complete"})


def test_fresh_mission_cannot_complete_without_successful_worker_evidence(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("operation", [sys.executable, "-c", "print('done')"])])
    runtime.start("Analyze the sample")

    with pytest.raises(ValueError, match="successful Worker result"):
        runtime.decide({"kind": "complete", "reason": "The task is complete"})


def test_existing_input_artifact_surfaces_matching_worker_without_keyword_overlap(tmp_path):
    source = tmp_path / "molecules.smi"
    source.write_text("CCO\n", encoding="utf-8")
    skill = SkillSpec("molecule-worker", [sys.executable, "-c", "print('done')"],
                      input_artifacts=["artifact:molecules"])
    runtime = controller(tmp_path, [skill])
    runtime.start("对分子进行标准化、生成指纹并聚类", artifacts={"artifact:molecules": str(source)})

    context = runtime.context()

    assert context["match_found"] is True
    assert context["skills"][0]["id"] == "molecule-worker"
    assert context["skills"][0]["match_score"] == 0


def test_device_action_uses_scoped_authorization_without_a_static_gate(tmp_path):
    skill = SkillSpec("device", [sys.executable, "-c", "print('simulated')"],
                     side_effect_level="device_control")
    runtime = controller(tmp_path, [skill])
    runtime.start("Run authorized simulation")
    state = runtime.decide(choose("device", impact="significant",
                                  authorization="User explicitly authorized this simulated action"))
    assert state.status == "waiting_agent"
    assert len(state.skill_executions) == 1


def test_required_agent_artifact_cannot_be_omitted_or_fabricated(tmp_path):
    skill = SkillSpec("lookup", [], outputs={"artifact:report": "report.txt"})
    runtime = controller(tmp_path, [skill])
    runtime.start("Get report")
    runtime.decide(choose("lookup"))
    with pytest.raises(ValueError, match="outputs"):
        runtime.resume(agent_completed=True)
    with pytest.raises(ValueError, match="exist"):
        runtime.resume(provided_artifacts={"artifact:report": str(tmp_path / "missing")})
    assert runtime.context()["mission"]["status"] == "waiting_agent"
    report = tmp_path / "report.txt"
    report.write_text("verified", encoding="utf-8")
    state = runtime.resume(provided_artifacts={"artifact:report": str(report)})
    assert state.status == "awaiting_decision"


def test_agent_mode_checks_prerequisites_and_explicit_policy_before_handoff(tmp_path):
    skill = SkillSpec("device", [],
                     required_capabilities=["cap:measure"])
    runtime = controller(tmp_path, [skill])
    runtime.start("Measure")
    state = runtime.decide(choose("device"))
    assert state.status == "awaiting_decision"
    assert "capability" in state.observations[-1]["summary"]
    runtime = controller(tmp_path, [skill], available_capabilities={"cap:measure"},
                         policies=[ExecutionPolicySpec("blocked", ["device"], blocked=True)])
    state = runtime.decide(choose("device"))
    assert state.status == "awaiting_decision"
    assert "policy" in state.observations[-1]["summary"]
    assert not state.skill_executions


def test_failed_process_is_observation_and_does_not_auto_retry(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("fail", [sys.executable, "-c", "raise SystemExit(2)"])])
    runtime.start("Try")
    state = runtime.decide(choose("fail"))
    assert state.status == "waiting_agent"
    state = runtime.resume(agent_failed=True, summary="Optional script failed")
    assert state.observations[-1]["status"] == "failed"
    assert len(state.skill_executions) == 1


def test_explicit_retry_creates_a_new_action_for_retryable_failure(tmp_path):
    skill = SkillSpec("flaky", [sys.executable, "-c", "import time; time.sleep(1)"],
                      timeout_seconds=0, side_effect_level="read_only")
    runtime = controller(tmp_path, [skill])
    runtime.start("Read local evidence")
    first = runtime.decide(choose("flaky"))
    assert first.status == "waiting_agent"
    runtime.resume(agent_failed=True, summary="Temporary external failure")

    retry = runtime.decide({**choose("flaky"), "retry_of": "action:1"})

    assert retry.decisions[-1]["retry_of"] == "action:1"
    assert retry.status == "waiting_agent"
    assert retry.pending_action["retry_count"] == 1
    events = [json.loads(line) for line in runtime.store.events_path.read_text(encoding="utf-8").splitlines()]
    assert not any(event["event"] == "skill_started" for event in events)


def test_retry_rejects_non_retryable_or_device_action(tmp_path):
    device = SkillSpec("device", [sys.executable, "-c", "raise SystemExit(2)"],
                       side_effect_level="device_task_create")
    runtime = controller(tmp_path, [device])
    runtime.start("Operate")
    runtime.decide(choose("device", impact="significant", authorization="Authorized test operation"))
    runtime.resume(agent_failed=True, summary="External operation failed")

    with pytest.raises(ValueError, match="not retryable"):
        runtime.decide({**choose("device"), "retry_of": "action:1"})


def test_significant_read_only_failure_is_not_a_retry_candidate(tmp_path):
    skill = SkillSpec("sensitive-read", [sys.executable, "-c", "import time; time.sleep(1)"],
                      timeout_seconds=0, side_effect_level="read_only")
    runtime = controller(tmp_path, [skill])
    runtime.start("Inspect sensitive record")
    state = runtime.decide(choose("sensitive-read", impact="significant",
                                  authorization="Authorized one-time inspection"))

    assert state.skill_executions["action:1"]["status"] == "waiting_agent"
    assert runtime.context()["retry_candidates"] == []


def test_context_lists_only_safe_retry_candidates(tmp_path):
    skill = SkillSpec("flaky", [sys.executable, "-c", "import time; time.sleep(1)"],
                      timeout_seconds=0, side_effect_level="read_only")
    runtime = controller(tmp_path, [skill])
    runtime.start("Read")
    runtime.decide(choose("flaky"))
    runtime.resume(agent_failed=True, summary="Temporary external failure")

    assert runtime.context()["retry_candidates"] == [{
        "action_id": "action:1", "skill_id": "flaky", "failure_kind": "external_worker", "retry_count": 0,
    }]


def test_pending_action_cannot_be_replaced_and_completion_needs_reason(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("lookup", [])])
    runtime.start("Lookup")
    runtime.decide(choose("lookup"))
    with pytest.raises(ValueError, match="waiting_agent"):
        runtime.decide({"kind": "complete", "reason": "Done"})
    assert runtime.resume().status == "waiting_agent"
    runtime.resume(agent_completed=True)
    with pytest.raises(ValueError, match="reason"):
        runtime.decide({"kind": "complete"})
    assert runtime.decide({"kind": "complete", "reason": "Answer verified"}).status == "completed"


def test_verified_capabilities_survive_command_restart(tmp_path):
    skill = SkillSpec("measure", [sys.executable, "-c", "print('local simulation')"],
                     required_capabilities=["cap:measure"])
    runtime = controller(tmp_path, [skill], available_capabilities={"cap:measure"})
    runtime.start("Measure")
    resumed = controller(tmp_path, [skill])
    state = resumed.decide(choose("measure"))
    assert len(state.skill_executions) == 1
    assert resumed.context()["available_capabilities"] == ["cap:measure"]


def test_agent_failure_returns_observation_without_requiring_declared_outputs(tmp_path):
    skill = SkillSpec("lookup", [], outputs={"artifact:report": "report.txt"})
    runtime = controller(tmp_path, [skill])
    runtime.start("Get evidence")
    runtime.decide(choose("lookup"))
    state = runtime.resume(agent_failed=True, summary="Source is unavailable", evidence=["source:attempted"])
    assert state.status == "awaiting_decision"
    assert state.observations[-1]["status"] == "failed"
    assert not state.artifacts


def test_nonobject_decision_is_rejected_without_corrupting_state(tmp_path):
    runtime = controller(tmp_path, [])
    runtime.start("Read")
    with pytest.raises(ValueError, match="object"):
        runtime.decide([])
    assert runtime.context()["mission"]["decisions"] == []


def test_interrupted_process_is_not_silently_rerun(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("device", [sys.executable, "-c", "print('no')"])])
    state = runtime.start("Operate")
    state.status = "running"
    state.pending_action = {**choose("device"), "id": "action:1"}
    runtime.store.save(state)
    assert runtime.start("Operate").status == "running"
    assert runtime.resume().status == "running"
    with pytest.raises(ValueError, match="running"):
        runtime.decide(choose("device"))
    assert not runtime.context()["mission"]["skill_executions"]


def test_reconcile_running_action_as_succeeded_requires_declared_outputs(tmp_path):
    skill = SkillSpec("submit", [sys.executable, "-c", "print('no')"],
                      outputs={"artifact:submit": "submit.json"},
                      side_effect_level="device_task_create")
    runtime = controller(tmp_path, [skill])
    state = runtime.start("Submit")
    state.status = "running"
    state.pending_action = {**choose("submit"), "id": "action:1", "skill_snapshot": runtime._skill_snapshot(skill)}
    runtime.store.save(state)

    with pytest.raises(ValueError, match="Required reconciled outputs missing"):
        runtime.reconcile("succeeded", "Device reports completion")


def test_reconcile_unknown_records_external_state_without_replay(tmp_path):
    skill = SkillSpec("device", [sys.executable, "-c", "raise RuntimeError('must not run')"])
    runtime = controller(tmp_path, [skill])
    state = runtime.start("Operate")
    state.status = "running"
    state.pending_action = {**choose("device"), "id": "action:1", "skill_snapshot": runtime._skill_snapshot(skill)}
    runtime.store.save(state)

    result = runtime.reconcile("unknown", "Task ID could not be found", evidence=["monitor:404"])

    assert result.observations[-1]["status"] == "reconciled_unknown"
    assert result.observations[-1]["evidence"] == ["monitor:404"]
    assert result.skill_executions == {}


def test_human_confirmation_requires_record_of_actual_reply(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("operation", [sys.executable, "-c", "print('no')"])])
    runtime.start("Review")
    runtime.decide(choose("operation", impact="significant"))
    with pytest.raises(ValueError, match="reply"):
        runtime.resume(confirmed=True)
    assert runtime.context()["mission"]["status"] == "waiting_human"


def test_candidate_context_links_large_manuals_without_repeating_their_text(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("lookup", [])], skill_knowledge={
            "lookup": {"description": "Read evidence", "documentation": {
            "files": ["manual.md"], "sections": [{"text": "large manual " * 10000}]},
            "evidence": [{"file": "manual.md"}], "unresolved": ["source date"]}})
    runtime.start("Read")
    context = runtime.context()
    assert len(json.dumps(context)) < 5000
    assert context["skills"][0]["description"] == "Read evidence"
    assert "documentation_files" not in context["skills"][0]


def test_context_returns_compact_goal_matched_skill_cards(tmp_path):
    skills = [SkillSpec(f"other-{index}", []) for index in range(6)]
    skills.append(SkillSpec("reaction-planner", []))
    knowledge = {skill.id: {"description": "general helper"} for skill in skills}
    knowledge["reaction-planner"] = {"description": "Plan an ATA reaction experiment"}
    runtime = controller(tmp_path, skills, skill_knowledge=knowledge)
    runtime.start("Plan an ATA reaction")

    context = runtime.context()

    assert context["registered_skill_count"] == 7
    assert context["candidate_count"] == 1
    assert context["match_found"] is True
    assert len(context["skills"]) == 1
    assert context["skills"][0] == {
        "id": "reaction-planner", "name": "reaction-planner",
        "description": "Plan an ATA reaction experiment", "suite_id": None,
        "inputs": [], "required_capabilities": [], "side_effect_level": "read_only",
        "missing_inputs": [], "missing_capabilities": [], "match_score": 4,
        "eligible": True,
    }


def test_context_excludes_unrunnable_process_workers(tmp_path):
    unusable = SkillSpec("broken-check", [])
    usable = SkillSpec("molecule-check", [sys.executable, "-c", "print('ok')"])
    runtime = controller(tmp_path, [unusable, usable], skill_knowledge={
        "broken-check": {"description": "Check molecule validity"},
        "molecule-check": {"description": "Check molecule validity"},
    })
    runtime.start("Check molecule validity")

    context = runtime.context()

    assert [skill["id"] for skill in context["skills"]] == ["broken-check", "molecule-check"]
    assert context["excluded_skills"] == []


def test_context_reports_no_match_instead_of_returning_arbitrary_workers(tmp_path):
    skill = SkillSpec("inventory", [])
    runtime = controller(tmp_path, [skill], skill_knowledge={
        "inventory": {"description": "Manage reagent inventory"},
    })
    runtime.start("Validate a protein sequence")

    context = runtime.context()

    assert context["match_found"] is False
    assert context["candidate_count"] == 0
    assert context["registered_skill_count"] == 1
    assert context["skills"] == []
    assert context["coverage_diagnostic"] == {
        "status": "no_matching_worker",
        "execution_started": False,
        "registered_skill_count": 1,
        "candidate_count": 0,
        "fallback_available": True,
        "fallback_scope": "low_risk_read_only",
        "fallback_message": (
            "如果这是低风险、只读分析，可以由 Agent 直接尝试，"
            "结果会标记为 Agent 直接执行。是否继续？"
        ),
        "user_message": (
            "当前没有找到能完成这项任务的完整能力，所以还没有开始执行。"
            "可能是相关 Skill 没有安装完整，或安装后没有被正确登记。"
            "请检查相关 Skill 后重试。"
        ),
    }


def test_approved_agent_fallback_records_native_execution(tmp_path):
    runtime = controller(tmp_path, [])
    runtime.start("Inspect a public PDB structure")
    runtime.decide({
        "kind": "request_human",
        "reason": "No matching Worker is registered",
        "question": "是否允许 Agent 直接完成这项低风险只读分析？",
    })

    state = runtime.resume(answer="允许，请直接完成并标记为 Agent 直接执行")
    assert state.replan_required is True

    state = runtime.decide({
        "kind": "agent_fallback",
        "reason": "用户已明确允许 Agent 直接完成只读分析",
        "side_effect_level": "read_only",
        "assessment": {
            "impact": "routine",
            "rationale": "仅读取公开结构并计算指标",
            "uncertainties": [],
            "authenticity_gaps": [],
            "authorization": "用户已明确允许 Agent 直接完成只读分析",
        },
    })

    assert state.status == "waiting_agent"
    assert state.skill_executions["action:2"]["execution_source"] == "agent_native"
    assert runtime.context()["worker_cycle"]["resume_mode"] == "agent_native"

    state = runtime.resume(
        action_id="action:2",
        agent_completed=True,
        summary="已读取结构并完成只读指标计算",
        evidence=["public-pdb:1AKE"],
    )
    assert state.observations[-1]["status"] == "succeeded"
    assert state.observations[-1]["execution_source"] == "agent_native"
    assert state.skill_executions["action:2"]["execution_source"] == "agent_native"


def test_context_ranks_chinese_goal_against_skill_metadata_without_expanding_cards(tmp_path):
    unrelated = SkillSpec("aaa-unrelated", [])
    relevant = SkillSpec("reaction-plan", [], triggers=["氢化", "反应"])
    runtime = controller(tmp_path, [unrelated, relevant], skill_knowledge={
        "reaction-plan": {"description": "设计氢化反应方案"},
        "aaa-unrelated": {"description": "整理库存"},
    })
    runtime.start("请设计氢化反应方案")

    context = runtime.context()

    assert context["skills"][0]["id"] == "reaction-plan"
    assert len(context["skills"]) == 1


def test_context_ranks_and_displays_a_chinese_skill_name(tmp_path):
    relevant = SkillSpec("reaction-plan", [])
    unrelated = SkillSpec("aaa-unrelated", [])
    runtime = controller(tmp_path, [unrelated, relevant], skill_knowledge={
        "reaction-plan": {"name": "氢化反应规划", "description": "实验规划"},
        "aaa-unrelated": {"name": "库存整理", "description": "实验规划"},
    })
    runtime.start("执行氢化反应规划")

    context = runtime.context()

    assert context["skills"][0]["id"] == "reaction-plan"
    assert context["skills"][0]["name"] == "氢化反应规划"


def test_factual_answer_replans_without_requiring_an_approval_flag(tmp_path):
    runtime = controller(tmp_path, [SkillSpec("device", [sys.executable, "-c", "print('no')"])])
    runtime.start("Measure")
    runtime.decide(choose("device", authenticity_gaps=["Sample identity unknown"]))
    state = runtime.resume(answer="The sample is B, according to the signed record")
    assert state.status == "awaiting_decision"
    assert state.observations[-1]["summary"] == "The sample is B, according to the signed record"
    assert not state.skill_executions


def test_approval_cannot_execute_a_changed_skill_implementation(tmp_path):
    original = SkillSpec("device", [sys.executable, "-c", "print('original')"])
    runtime = controller(tmp_path, [original])
    runtime.start("Operate")
    runtime.decide(choose("device", impact="significant"))
    changed = SkillSpec("device", [sys.executable, "-c", "print('different operation')"])
    resumed = controller(tmp_path, [changed])
    state = resumed.resume(confirmed=True, answer="Approved the original operation")
    assert state.status == "awaiting_decision"
    assert not state.skill_executions
    assert "changed" in state.observations[-1]["summary"]
