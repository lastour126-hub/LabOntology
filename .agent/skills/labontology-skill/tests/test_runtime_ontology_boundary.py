import subprocess
import sys
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).parents[1] / "scripts"


def test_ontology_tool_requires_an_active_cache_directory():
    result = subprocess.run(
        [sys.executable, "-m", "core.ontology", "validate"],
        cwd=SCRIPTS_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--system-dir is required" in result.stderr
