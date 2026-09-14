import json
import subprocess
import sys
from pathlib import Path


MANAGER_ROOT = Path(__file__).parents[1]
RUNTIME_ROOT = MANAGER_ROOT.parent / "labontology-run"


def test_bundle_intake_is_owned_by_data_manager(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "skills.json").write_text(
        json.dumps(
            {
                "schema": "labontology.skill-bundle.v1",
                "suite_id": "suite:boundary",
                "skills": [{"id": "boundary:skill", "status": "draft", "enabled": False}],
                "device_knowledge": [],
                "workflows": [],
            }
        ),
        encoding="utf-8",
    )
    workdir = tmp_path / "workdir"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/import_bundle.py",
            str(bundle),
            "--workdir",
            str(workdir),
        ],
        cwd=MANAGER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (workdir / "labontology_boundary_skill_cache" / "ontology.jsonl").exists()
    assert (MANAGER_ROOT / "scripts" / "import_bundle.py").exists()
    assert not (RUNTIME_ROOT / "scripts" / "import_bundle.py").exists()


def test_data_manager_code_is_not_named_as_runtime_code():
    assert (MANAGER_ROOT / "data_manager" / "intake.py").exists()
    assert not (MANAGER_ROOT / "runtime" / "intake.py").exists()
