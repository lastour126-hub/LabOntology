import json
import sys
from pathlib import Path

from core.runtime.registry import Registry


PROJECT_ROOT = Path(__file__).resolve().parents[4]
FDU_ROOT = PROJECT_ROOT / "FduSkills"
REGISTRY_PATH = PROJECT_ROOT / ".agent" / "skills" / "labontology-skill" / "tests" / "fixtures" / "fdu" / "registry.yaml"
VERIFY_SCRIPT_DIR = FDU_ROOT / "fdu-resource-verify" / "scripts"
sys.path.insert(0, str(VERIFY_SCRIPT_DIR))

from verify_resources import print_verification_result, save_verification_result  # noqa: E402


def test_fdu_registry_points_to_real_root_and_registers_all_discovered_skills():
    registry = Registry.load(REGISTRY_PATH)
    suite = registry.suite("suite:fdu")

    assert suite.root == FDU_ROOT.resolve()
    assert len(suite.skills) == 17
    assert "skill:fdu-device-run" in suite.skills
    assert "skill:fdu-risk-review" in suite.skills
    assert suite.skills["skill:fdu-risk-review"].execution_mode == "agent"
    assert suite.skills["skill:fdu-risk-review"].runnable is False
    assert all((suite.root / spec.working_dir).is_dir() for spec in suite.skills.values() if spec.working_dir)


def test_fdu_resource_verification_writes_result_file(tmp_path):
    output_path = tmp_path / "verification.json"

    save_verification_result([], output_path)

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["details"] == []
    assert result["summary"] == {"total_steps": 0, "valid": 0, "invalid": 0}


def test_fdu_resource_verification_status_output_is_windows_console_safe(capsys):
    print_verification_result([
        {
            "step_index": 1,
            "unit_type": "exp_add_solid",
            "instruction": "add solid",
            "substance": "4A MS",
            "matches_count": 1,
            "available_count": 1,
            "available_resources": [],
            "quantity_validation": None,
            "is_valid": True,
        }
    ])

    output = capsys.readouterr().out
    assert "[OK]" in output
    assert "✓" not in output
    assert "✗" not in output
