import json
import subprocess
import sys

from data_manager.importer import discover_skill, discover_tree, export_bundle


def test_discovery_extracts_markdown_frontmatter_python_cli_and_evidence(tmp_path):
    skill_dir = tmp_path / "constraint-parser"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: constraint-parser
description: Parse experiment constraints into JSON.
---

Reads a request and writes normalized constraints.
""",
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "parse.py").write_text(
        """import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', default='constraints.json')
def main():
    parser.parse_args()
""",
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    assert manifest["id"] == "constraint-parser"
    assert manifest["description"] == "Parse experiment constraints into JSON."
    assert {item["name"] for item in manifest["parameters"]} == {"input", "output"}
    assert manifest["status"] == "discovered"
    assert manifest["enabled"] is False
    assert any(item["source"] == "python_ast" for item in manifest["evidence"])
    assert "side_effect_level" in manifest["unresolved"]


def test_discovery_extracts_positional_python_cli_arguments(tmp_path):
    skill_dir = tmp_path / "resource-verify"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Verify resources\n", encoding="utf-8")
    (skill_dir / "scripts" / "verify.py").write_text(
        """import argparse

parser = argparse.ArgumentParser()
parser.add_argument('step_json_path')
parser.add_argument('--output-path', required=True)
""",
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    assert {item["name"] for item in manifest["parameters"]} == {
        "step_json_path",
        "output_path",
    }
    positional = next(item for item in manifest["parameters"] if item["name"] == "step_json_path")
    assert positional["positional"] is True


def test_discovery_handles_nonstandard_layout_and_emits_json(tmp_path):
    root = tmp_path / "vendor-package"
    (root / "cli").mkdir(parents=True)
    (root / "README.md").write_text("# Liquid transfer\nMoves liquid between vessels.\n", encoding="utf-8")
    (root / "manifest.yaml").write_text(
        "skill_id: liquid-transfer\ninputs: [source, destination]\n", encoding="utf-8"
    )
    (root / "cli" / "run.py").write_text("print('device')\n", encoding="utf-8")

    discovered = discover_tree(root)

    assert len(discovered) == 1
    assert discovered[0]["id"] == "liquid-transfer"
    assert discovered[0]["description"] == "Moves liquid between vessels."
    assert discovered[0]["parameters"] == [
        {"name": "source", "required": None, "default": None},
        {"name": "destination", "required": None, "default": None},
    ]
    json.dumps(discovered)


def test_discovery_preserves_common_execution_contract_without_classifying_skill_type(tmp_path):
    skill_dir = tmp_path / "fdu-add-liquid-json"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Add liquid\nGenerates a device-ready liquid transfer action.\n",
        encoding="utf-8",
    )
    (skill_dir / "manifest.yaml").write_text(
        """id: skill:fdu-add-liquid-json
outputs:
  - name: action_json
    type: artifact:device-action
    path: action.json
required_capabilities:
  - capability:liquid-transfer
dependencies:
  - python>=3.11
side_effect_level: local_file_write
""",
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "generate.py").write_text(
        "print('generate action')\n",
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    assert manifest["id"] == "skill:fdu-add-liquid-json"
    assert manifest["outputs"] == [
        {"name": "action_json", "type": "artifact:device-action", "path": "action.json"}
    ]
    assert manifest["required_capabilities"] == ["capability:liquid-transfer"]
    assert manifest["dependencies"] == ["python>=3.11"]
    assert manifest["side_effect_level"] == "local_file_write"
    assert "side_effect_level" not in manifest["unresolved"]
    assert "outputs" not in manifest["unresolved"]
    assert "skill_type" not in manifest


def test_discovery_extracts_markdown_sections_execution_hints_and_related_skills(tmp_path):
    skill_dir = tmp_path / "orchestrator"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """# Orchestrator
Runs a laboratory workflow.

## 强制执行顺序
1. 读取输入文件。
2. 调用 `step-builder` 生成步骤。

## 输入输出
- 输入：实验约束 JSON
- 输出：设备协议 JSON

## 约束
- 不得在确认前提交设备任务。
""",
        encoding="utf-8",
    )
    (skill_dir / "references" / "manifest.md").write_text(
        """# 流程说明

## 相关文件
- `../step-builder/SKILL.md`
""",
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    documentation = manifest["documentation"]
    assert "强制执行顺序" in {item["heading"] for item in documentation["sections"]}
    assert any("读取输入文件" in item for item in documentation["execution_order_hints"])
    assert any("实验约束 JSON" in item for item in documentation["input_hints"])
    assert any("设备协议 JSON" in item for item in documentation["output_hints"])
    assert any("确认前" in item for item in documentation["constraint_hints"])
    assert "step-builder" in documentation["related_skill_refs"]
    assert any(path.replace("\\", "/").endswith("references/manifest.md") for path in documentation["files"])


def test_discovery_indexes_kb_files_and_extracts_structured_facts(tmp_path):
    skill_dir = tmp_path / "action-skill"
    (skill_dir / "KB").mkdir(parents=True)
    (skill_dir / "references").mkdir()
    (skill_dir / "SKILL.md").write_text("# Action\nBuilds an action.\n", encoding="utf-8")
    (skill_dir / "KB" / "action_schema.json").write_text(
        json.dumps({"schema_version": "action/v1", "unit_type": "exp_pipetting", "defaults": {"unit": "mL"}}),
        encoding="utf-8",
    )
    (skill_dir / "KB" / "aliases.json").write_text(json.dumps({"MeCN": "乙腈"}), encoding="utf-8")
    (skill_dir / "KB" / "resources.csv").write_text("name,amount\nwater,1\n", encoding="utf-8")

    manifest = discover_skill(skill_dir)

    files = {item["path"]: item for item in manifest["knowledge_files"]}
    assert "KB/action_schema.json" in files
    assert files["KB/action_schema.json"]["format"] == "json"
    assert "exp_pipetting" in files["KB/action_schema.json"]["semantic_values"]
    assert files["KB/aliases.json"]["facts"]["alias_count"] == 1
    assert files["KB/resources.csv"]["columns"] == ["name", "amount"]
    assert manifest["knowledge_summary"]["file_count"] == 3


def test_discovery_derives_capability_from_skill_action_knowledge_with_evidence(tmp_path):
    skill_dir = tmp_path / "liquid-action"
    (skill_dir / "KB").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Liquid action\nGenerates a liquid-transfer action for the laboratory platform.\n",
        encoding="utf-8",
    )
    (skill_dir / "KB" / "action_schema.json").write_text(
        json.dumps({"schema_version": "action/v1", "unit_type": "exp_pipetting"}),
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    assert manifest["required_capabilities"] == ["capability:liquid-transfer"]
    assert any(
        item["capability"] == "capability:liquid-transfer"
        and item["source"] == "knowledge"
        and item["confidence"] == 0.9
        for item in manifest["capability_evidence"]
    )


def test_discovery_does_not_infer_capability_from_skill_name_alone(tmp_path):
    skill_dir = tmp_path / "liquid-transfer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Utility\nFormats a text report.\n", encoding="utf-8")

    manifest = discover_skill(skill_dir)

    assert manifest["required_capabilities"] == []


def test_discovery_builds_output_contract_from_script_and_documentation(tmp_path):
    skill_dir = tmp_path / "resource-verify"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """# Resource verification

## 输出
- 输出资源校验结果 JSON：`output/verification_result_<timestamp>.json`
""",
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "verify.py").write_text(
        """import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)

def main():
    args = parser.parse_args()
    with open(args.output, 'w', encoding='utf-8') as handle:
        json.dump({'status': 'ok'}, handle)
""",
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    assert manifest["outputs"] == [{
        "name": "artifact:verification-result",
        "format": "json",
        "path": "output/verification_result_<timestamp>.json",
        "required": True,
        "source": "script_and_documentation",
        "confidence": 0.9,
        "binding": {"parameter": "output", "flag": "--output"},
    }]
    assert any(item["field"] == "outputs" for item in manifest["contract_evidence"])


def test_discovery_assigns_a_runtime_output_path_when_script_only_declares_output(tmp_path):
    skill_dir = tmp_path / "writer"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Writer\nWrites a JSON result.\n", encoding="utf-8")
    (skill_dir / "scripts" / "write.py").write_text(
        "import argparse\nimport json\np=argparse.ArgumentParser()\np.add_argument('--output', required=True)\njson.dump({}, open('unused', 'w'))\n",
        encoding="utf-8",
    )

    manifest = discover_skill(skill_dir)

    assert manifest["outputs"][0]["path"] == "output/result_<timestamp>.json"


def test_cli_writes_discovery_report(tmp_path):
    skill_dir = tmp_path / "simple"
    skill_dir.mkdir()
    (skill_dir / "README.md").write_text("# Simple\nDoes one thing.\n", encoding="utf-8")
    output = tmp_path / "report.json"

    result = subprocess.run(
        [sys.executable, "-m", "data_manager.cli", str(skill_dir), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report[0]["id"] == "simple"


def test_export_bundle_writes_standardized_skill_manifest(tmp_path):
    source = tmp_path / "skill"
    source.mkdir()
    (source / "SKILL.md").write_text("# Example\nCreates a result.\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    export_bundle(source, bundle, "suite:test")

    manifest = json.loads((bundle / "skills.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "labontology.skill-bundle.v1"
    assert manifest["suite_id"] == "suite:test"
    assert manifest["skills"][0]["status"] == "draft"
    assert manifest["skills"][0]["enabled"] is False


def test_export_bundle_carries_device_and_workflow_files(tmp_path):
    source = tmp_path / "skill"
    source.mkdir()
    (source / "SKILL.md").write_text("# Example\nDoes one thing.\n", encoding="utf-8")
    device = tmp_path / "device"
    workflow = tmp_path / "workflow"
    device.mkdir()
    workflow.mkdir()
    (device / "platform.yaml").write_text("id: device:test\n", encoding="utf-8")
    (workflow / "task.yaml").write_text("id: workflow:test\n", encoding="utf-8")
    bundle = tmp_path / "bundle"

    export_bundle(source, bundle, "suite:test", device, workflow)

    assert (bundle / "DeviceKnowledge" / "platform.yaml").exists()
    assert (bundle / "Workflow" / "task.yaml").exists()


def test_export_bundle_carries_skill_knowledge_files_for_intake(tmp_path):
    source = tmp_path / "skill"
    (source / "KB").mkdir(parents=True)
    (source / "SKILL.md").write_text("# Example\nUses a schema.\n", encoding="utf-8")
    (source / "KB" / "schema.json").write_text("{\"version\": \"1\"}", encoding="utf-8")
    bundle = tmp_path / "bundle"

    export_bundle(source, bundle, "suite:test")

    assert (bundle / "Knowledge" / "skill" / "KB" / "schema.json").exists()
    manifest = json.loads((bundle / "skills.json").read_text(encoding="utf-8"))
    assert manifest["skills"][0]["knowledge_summary"]["file_count"] == 1
