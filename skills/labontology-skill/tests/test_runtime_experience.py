import json
from pathlib import Path

from core.runtime.agent_loop import AgentRuntime
from core.runtime.experience import ExperienceStore
from core.runtime.models import SkillSpec
from core.runtime.state_store import StateStore


def test_experience_store_keeps_compact_records_and_returns_matching_history(tmp_path):
    store = ExperienceStore(tmp_path)
    store.record_success(
        goal="比较分子结构指纹并聚类",
        skill_ids=["datamol-analysis"],
        summary="完成标准化、ECFP 指纹和 Butina 聚类",
        constraints=["datamol 未安装，使用 RDKit 回退"],
        artifact_types=["json", "csv"],
    )

    matches = store.search("请比较分子并生成结构指纹")

    assert len(matches) == 1
    assert matches[0]["skills"] == ["datamol-analysis"]
    assert matches[0]["constraints"] == ["datamol 未安装，使用 RDKit 回退"]
    assert "rationale" not in matches[0]
    assert (tmp_path / "experiences.jsonl").is_file()


def test_context_exposes_only_a_small_historical_hint_list(tmp_path):
    ExperienceStore(tmp_path).record_success(
        goal="计算分子性质",
        skill_ids=["property"],
        summary="完成分子性质计算",
        artifact_types=["json"],
    )
    runtime = AgentRuntime(
        {"property": SkillSpec("property", [])},
        StateStore(tmp_path, "mission"),
        skill_knowledge={"property": {"description": "计算分子性质"}},
    )
    runtime.start("请计算分子性质")

    context = runtime.context()

    assert len(context["historical_experiences"]) == 1
    assert context["historical_experiences"][0]["summary"] == "完成分子性质计算"


def test_experience_history_is_bounded_and_compacted(tmp_path):
    store = ExperienceStore(tmp_path)
    for index in range(205):
        store.record_success(
            goal=f"任务 {index}",
            skill_ids=["worker"],
            summary=f"结果 {index}",
        )

    records = [json.loads(line) for line in (tmp_path / "experiences.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 200
    assert len(store.search("任务", limit=20)) == 3
    assert (tmp_path / ".backup" / "experiences.jsonl").is_file()


def test_completed_mission_is_recorded_as_experience(tmp_path):
    runtime = AgentRuntime(
        {"lookup": SkillSpec("lookup", [])},
        StateStore(tmp_path, "mission"),
        skill_knowledge={"lookup": {"description": "查找实验记录"}},
    )
    runtime.start("查找实验记录")
    runtime.decide({
        "kind": "skill",
        "skill_id": "lookup",
        "reason": "查找当前任务所需记录",
        "assessment": {
            "impact": "routine",
            "rationale": "该 Worker 覆盖当前查询",
            "uncertainties": [],
            "authenticity_gaps": [],
        },
    })
    runtime.resume(agent_completed=True, summary="找到实验记录")
    runtime.decide({"kind": "complete", "reason": "结果已记录"})

    records = [json.loads(line) for line in (tmp_path / "experiences.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[0]["status"] == "succeeded"
    assert records[0]["skills"] == ["lookup"]
