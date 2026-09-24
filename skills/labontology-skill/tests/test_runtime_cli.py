import sys
import json

from core.runtime.commands import load_skill_file


def test_load_skill_file_reads_command_and_outputs(tmp_path):
    path = tmp_path / "skill.yaml"
    path.write_text(
        """id: skill:test\ncommand: [python, -c, 'print(1)']\noutputs:\n  artifact:result: result.txt\n""",
        encoding="utf-8",
    )

    spec = load_skill_file(path)

    assert spec.id == "skill:test"
    assert spec.outputs["artifact:result"] == "result.txt"
