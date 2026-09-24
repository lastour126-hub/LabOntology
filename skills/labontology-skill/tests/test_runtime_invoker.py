import os
import sys
from pathlib import Path

import pytest

from core.runtime.invoker import OptionalScriptInvoker
from core.runtime.models import SkillSpec


def test_invoker_runs_skill_and_collects_declared_output(tmp_path):
    skill = SkillSpec(
        id="skill:writer",
        optional_command=[sys.executable, "-c", "from pathlib import Path; Path(__import__('os').environ['SKILL_OUTPUT_RESULT']).write_text('ok')"],
        outputs={"artifact:result": "result.txt"},
    )

    run = OptionalScriptInvoker().run(skill, tmp_path)

    assert run.status == "succeeded"
    assert run.outputs["artifact:result"].endswith("result.txt")
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "ok"
    assert (tmp_path / "stdout.log").exists()
    assert (tmp_path / "stderr.log").exists()


def test_invoker_resolves_a_relative_interpreter_from_the_skill_working_directory(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows executable lookup is the compatibility boundary under test")
    working_dir = tmp_path / "skill"
    working_dir.mkdir()
    relative_shell = os.path.relpath(os.environ["ComSpec"], working_dir)
    skill = SkillSpec(
        id="skill:isolated-python",
        optional_command=[relative_shell, "/c", "echo ok > %SKILL_OUTPUT_RESULT%"],
        outputs={"artifact:result": "result.txt"},
        working_dir=str(working_dir),
    )

    run = OptionalScriptInvoker().run(skill, tmp_path / "run")

    assert run.status == "succeeded"
    assert (tmp_path / "run" / "result.txt").read_text(encoding="utf-8").strip() == "ok"


def test_invoker_renders_documented_timestamp_output_templates(tmp_path):
    skill = SkillSpec(
        id="skill:timestamped-writer",
        optional_command=[sys.executable, "-c", "from pathlib import Path; import os; Path(os.environ['SKILL_OUTPUT_RESULT']).write_text('ok')"],
        outputs={"artifact:result": "output/result_<timestamp>.json"},
    )

    run = OptionalScriptInvoker().run(skill, tmp_path / "run")

    output = Path(run.outputs["artifact:result"])
    assert run.status == "succeeded"
    assert "<" not in output.name
    assert output.read_text(encoding="utf-8") == "ok"


def test_invoker_binds_input_and_output_artifacts_to_cli_arguments(tmp_path):
    source = tmp_path / "input.json"
    source.write_text("input", encoding="utf-8")
    skill = SkillSpec(
        id="skill:cli",
        optional_command=[
            sys.executable,
            "-c",
            "import argparse; from pathlib import Path; p=argparse.ArgumentParser(); p.add_argument('--input'); p.add_argument('--output'); a=p.parse_args(); Path(a.output).write_text(Path(a.input).read_text() + '-ok')",
        ],
        outputs={"artifact:result": "result.txt"},
        argument_bindings={
            "inputs": {"artifact:source": {"flag": "--input"}},
            "outputs": {"artifact:result": {"flag": "--output"}},
        },
    )

    run = OptionalScriptInvoker().run(skill, tmp_path / "run", {"artifact:source": str(source)})

    assert run.status == "succeeded"
    assert (tmp_path / "run" / "result.txt").read_text(encoding="utf-8") == "input-ok"


def test_invoker_binds_declared_decision_arguments_to_cli_parameters(tmp_path):
    skill = SkillSpec(
        id="skill:arguments",
        optional_command=[
            sys.executable,
            "-c",
            "import argparse; from pathlib import Path; p=argparse.ArgumentParser(); p.add_argument('--text'); p.add_argument('--test', action='store_true'); p.add_argument('--output'); a=p.parse_args(); Path(a.output).write_text(a.text + ':' + str(a.test))",
        ],
        outputs={"artifact:result": "result.txt"},
        argument_bindings={
            "parameters": {"text": {"flag": "--text"}, "test": {"flag": "--test"}},
            "outputs": {"artifact:result": {"flag": "--output"}},
        },
    )

    run = OptionalScriptInvoker().run(skill, tmp_path / "run", arguments={"text": "verified", "test": True})

    assert run.status == "succeeded"
    assert (tmp_path / "run" / "result.txt").read_text(encoding="utf-8") == "verified:True"


def test_invoker_places_subcommand_before_its_option_arguments(tmp_path):
    skill = SkillSpec(
        id="skill:subcommand",
        optional_command=[
            sys.executable,
            "-c",
            "import argparse, os; from pathlib import Path; p=argparse.ArgumentParser(); s=p.add_subparsers(dest='action', required=True); q=s.add_parser('workqueue'); q.add_argument('--host', required=True); a=p.parse_args(); Path(os.environ['SKILL_OUTPUT_RESULT']).write_text(a.action + ':' + a.host)",
        ],
        outputs={"artifact:result": "result.txt"},
        argument_bindings={
            "parameters": {"host": {"flag": "--host"}, "action": {"positional": True}},
        },
    )

    run = OptionalScriptInvoker().run(skill, tmp_path / "run", arguments={"host": "127.0.0.1", "action": "workqueue"})

    assert run.status == "succeeded"
    assert (tmp_path / "run" / "result.txt").read_text(encoding="utf-8") == "workqueue:127.0.0.1"


def test_invoker_resolves_run_directory_values_for_required_auxiliary_arguments(tmp_path):
    skill = SkillSpec(
        id="skill:aux",
        optional_command=[
            sys.executable,
            "-c",
            "import argparse; from pathlib import Path; p=argparse.ArgumentParser(); p.add_argument('--output'); p.add_argument('--aux-dir'); a=p.parse_args(); Path(a.aux_dir).mkdir(parents=True); Path(a.output).write_text(a.aux_dir)",
        ],
        outputs={"artifact:result": "result.txt"},
        argument_bindings={
            "outputs": {
                "artifact:result": {
                    "flag": "--output",
                    "additional_flags": [{"flag": "--aux-dir", "value": "${RUN_DIR}/auxiliary"}],
                }
            }
        },
    )

    run_dir = tmp_path / "run"
    run = OptionalScriptInvoker().run(skill, run_dir)

    assert run.status == "succeeded"
    assert (run_dir / "auxiliary").is_dir()


def test_invoker_exposes_maintained_skill_knowledge_directory(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    skill = SkillSpec(
        id="skill:knowledge-reader",
        optional_command=[
            sys.executable,
            "-c",
            "from pathlib import Path; import os; Path(os.environ['SKILL_OUTPUT_RESULT']).write_text(os.environ['LABONTOLOGY_SKILL_KNOWLEDGE_DIR'])",
        ],
        outputs={"artifact:result": "result.txt"},
        knowledge_dir=str(knowledge_dir),
    )

    run = OptionalScriptInvoker().run(skill, tmp_path / "run")

    assert run.status == "succeeded"
    assert (tmp_path / "run" / "result.txt").read_text(encoding="utf-8") == str(knowledge_dir)


def test_timeout_is_classified_as_retryable_for_read_only_skill(tmp_path):
    skill = SkillSpec(
        id="skill:slow",
        optional_command=[sys.executable, "-c", "import time; time.sleep(1)"],
        timeout_seconds=0,
        side_effect_level="read_only",
    )

    run = OptionalScriptInvoker().run(skill, tmp_path)

    assert run.status == "timed_out"
    assert run.failure_kind == "timeout"
    assert run.retryable is True


def test_missing_output_is_classified_as_not_retryable(tmp_path):
    skill = SkillSpec(
        id="skill:missing-output",
        optional_command=[sys.executable, "-c", "print('ok')"],
        outputs={"artifact:report": "report.json"},
    )

    run = OptionalScriptInvoker().run(skill, tmp_path)

    assert run.status == "failed"
    assert run.failure_kind == "output_missing"
    assert run.retryable is False
