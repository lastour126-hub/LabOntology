import json
import sys
import subprocess
from pathlib import Path

import yaml

from core.runtime.commands import main
from core.runtime.models import MissionState
from core.runtime.state_store import StateStore


def cache_fixture(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "cache-manifest.json").write_text('{"updated_at": "2026-09-07"}', encoding="utf-8")
    entities = [
        {"id": "suite:test", "type": "SkillSuite", "properties": {"name": "Test suite"}},
        {"id": "skill:lookup", "type": "Skill", "properties": {
            "description": "Research measurement evidence", "unresolved": ["source authenticity"],
            "evidence": [{"source": "SKILL.md"}],
            "runtime": {"optional_command": [], "optional_entrypoints": []},
        }},
        {"id": "skill:calculate", "type": "Skill", "properties": {
            "description": "Calculate molecular properties",
            "runtime": {"optional_command": [sys.executable, "-c", "print('calculated')"]},
        }},
        {"id": "suite:devices", "type": "SkillSuite", "properties": {"name": "Device suite"}},
        {"id": "skill:device", "type": "Skill", "properties": {
            "description": "Operate a device",
            "runtime": {"optional_command": [], "optional_entrypoints": []},
        }},
    ]
    relations = [
        {"relation": "containsSkill", "source": "suite:test", "target": "skill:lookup"},
        {"relation": "containsSkill", "source": "suite:test", "target": "skill:calculate"},
        {"relation": "containsSkill", "source": "suite:devices", "target": "skill:device"},
    ]
    (cache / "ontology.jsonl").write_text(
        "".join(json.dumps({"entity": entity}) + "\n" for entity in entities)
        + "".join(json.dumps({"relation": relation}) + "\n" for relation in relations),
        encoding="utf-8",
    )
    return cache


def test_cli_default_agent_loop_works_without_workflow_and_leaves_cache_readonly(tmp_path, capsys):
    cache = cache_fixture(tmp_path)
    before = {str(p.relative_to(cache)): p.read_bytes() for p in cache.rglob('*') if p.is_file()}
    args = ["--system-dir", str(cache), "--mission-id", "test"]
    assert main(["run", *args, "--goal", "Research measurement evidence"]) == 0
    context = json.loads(capsys.readouterr().out)
    assert context["mission"]["status"] == "awaiting_decision"
    assert context["workflow_references"] == []
    lookup = next(skill for skill in context["skills"] if skill["id"] == "lookup")
    assert lookup["description"] == "Research measurement evidence"
    assert "knowledge" not in lookup
    decision = tmp_path / "decision.json"
    decision.write_text(json.dumps({"kind": "skill", "skill_id": "lookup", "reason": "Get evidence first",
                                  "assessment": {"impact": "routine", "rationale": "Read literature",
                                                 "uncertainties": [], "authenticity_gaps": []}}), encoding="utf-8")
    assert main(["act", *args, "--decision-file", str(decision)]) == 0
    assert json.loads(capsys.readouterr().out)["mission"]["status"] == "waiting_agent"
    assert main(["resume", *args, "--summary", "Evidence supports calculation", "--evidence", "paper:123"]) == 0
    assert json.loads(capsys.readouterr().out)["mission"]["observations"][-1]["evidence"] == ["paper:123"]
    assert main(["context", *args]) == 0
    assert json.loads(capsys.readouterr().out)["mission"]["status"] == "awaiting_decision"
    for name, content in before.items():
        assert (cache / name).read_bytes() == content
    assert (cache / "runs" / "test" / "state.json").exists()


def test_agent_context_can_combine_knowledge_and_device_suites(tmp_path, capsys):
    cache = cache_fixture(tmp_path)
    assert main(["run", "--system-dir", str(cache), "--mission-id", "combined", "--goal", "Research calculate operate"]) == 0
    context = json.loads(capsys.readouterr().out)
    assert {s["id"] for s in context["skills"]} == {"lookup", "calculate", "device"}


def test_cli_emits_utf8_json_for_chinese_agent_goals(tmp_path):
    cache = cache_fixture(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "runtime.py"
    result = subprocess.run([sys.executable, str(script), "run", "--system-dir", str(cache),
                             "--mission-id", "unicode", "--goal", "核实实验条件"], capture_output=True)
    assert result.returncode == 0
    assert json.loads(result.stdout.decode("utf-8"))["mission"]["goal"] == "核实实验条件"


def test_status_accepts_cache_dir_alias(tmp_path, capsys):
    cache = cache_fixture(tmp_path)
    StateStore(cache / "runs", "status-check").save(
        MissionState("status-check", status="awaiting_decision", mode="agent", goal="Inspect")
    )

    assert main(["status", "--cache-dir", str(cache), "--mission-id", "status-check"]) == 0

    state = json.loads(capsys.readouterr().out)
    assert state["mission_id"] == "status-check"


def test_cli_reconciles_interrupted_mission_without_reinvoking_skill(tmp_path, capsys):
    cache = cache_fixture(tmp_path)
    store = StateStore(cache / "runs", "interrupted")
    store.save(MissionState(
        "interrupted", status="running", mode="agent", goal="Inspect",
        pending_action={"id": "action:1", "kind": "skill", "skill_id": "calculate"},
    ))

    assert main([
        "reconcile", "--system-dir", str(cache), "--mission-id", "interrupted",
        "--outcome", "unknown", "--summary", "No external receipt", "--evidence", "monitor:404",
    ]) == 0

    context = json.loads(capsys.readouterr().out)
    assert context["mission"]["observations"][-1]["status"] == "reconciled_unknown"


def test_script_entrypoint_forwards_reconcile_subcommand(tmp_path):
    cache = cache_fixture(tmp_path)
    StateStore(cache / "runs", "entrypoint").save(MissionState(
        "entrypoint", status="running", mode="agent", goal="Inspect",
        pending_action={"id": "action:1", "kind": "skill", "skill_id": "calculate"},
    ))
    script = Path(__file__).resolve().parents[1] / "scripts" / "runtime.py"

    result = subprocess.run([
        sys.executable, str(script), "reconcile", "--system-dir", str(cache),
        "--mission-id", "entrypoint", "--outcome", "unknown", "--summary", "No receipt",
    ], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mission"]["observations"][-1]["status"] == "reconciled_unknown"
