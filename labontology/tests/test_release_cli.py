import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI = PROJECT_ROOT / "labontology" / "scripts" / "labontology.py"


def run_cli(*args: str, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        input=input,
        check=check,
    )


def make_skill_root(tmp_path: Path) -> Path:
    skill_root = tmp_path / "demo-skill"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Inspect a local record.\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    return skill_root


def import_demo_cache(tmp_path: Path) -> Path:
    result = json.loads(run_cli(
        "import", str(make_skill_root(tmp_path)),
        "--suite-id", "suite:demo", "--workspace", str(tmp_path),
    ).stdout)
    return Path(result["cache_dir"])


def test_import_creates_and_validates_a_cache(tmp_path: Path):
    result = json.loads(run_cli(
        "import", str(make_skill_root(tmp_path)),
        "--suite-id", "suite:demo", "--workspace", str(tmp_path),
    ).stdout)

    assert result["suite_id"] == "suite:demo"
    assert Path(result["cache_dir"]).is_dir()
    assert result["validation"] == {"graphs": 1, "valid": True}


def test_inspect_reports_cache_summary(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    result = json.loads(run_cli("inspect", "--cache-dir", str(cache)).stdout)

    assert result["suite_id"] == "suite:demo"
    assert result["skill_count"] == 1
    assert result["source_integrity"]["missing"] == 0
