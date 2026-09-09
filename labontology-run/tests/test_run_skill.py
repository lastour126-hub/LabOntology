import subprocess
import sys


def test_run_skill_exposes_runtime_cli_help():
    result = subprocess.run(
        [sys.executable, "scripts/run_skill.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: run_skill.py run" in result.stdout
    assert "--registry" in result.stdout
    assert "--system-dir" in result.stdout
