import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).parents[1]


def test_ontology_tool_requires_an_active_cache_directory():
    result = subprocess.run(
        [sys.executable, "scripts/ontology.py", "validate"],
        cwd=RUNTIME_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--system-dir is required" in result.stderr
