from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import SkillExecution, SkillSpec


def _env_key(artifact_id: str) -> str:
    return "SKILL_OUTPUT_" + re.sub(r"[^A-Za-z0-9]+", "_", artifact_id.split(":", 1)[-1]).upper()


def _render_output_template(value: str) -> str:
    now = datetime.now()
    return (value.replace("<YYYYMMDD_HHMMSS>", now.strftime("%Y%m%d_%H%M%S"))
                 .replace("<YYYYMMDD>", now.strftime("%Y%m%d"))
                 .replace("<timestamp>", now.strftime("%Y%m%d_%H%M%S"))
                 .replace("<time>", now.strftime("%Y%m%d_%H%M%S")))


def _append_binding(command: list[str], binding: object, value: Any, run_dir: Path | None = None) -> None:
    if not isinstance(binding, dict):
        return
    resolved_value = binding.get("value", value)
    flag = binding.get("flag")
    if isinstance(resolved_value, bool):
        if resolved_value and flag:
            command.append(str(flag))
        return
    resolved_value = str(resolved_value)
    if run_dir is not None:
        resolved_value = resolved_value.replace("${RUN_DIR}", str(run_dir))
    if binding.get("positional"):
        command.append(resolved_value)
        return
    if flag:
        command.extend([str(flag), resolved_value])
    for additional in binding.get("additional_flags", []) or []:
        _append_binding(command, additional, value, run_dir)


class SkillInvoker:
    def run(self, skill: SkillSpec, run_dir: Path, inputs: dict[str, str] | None = None,
            arguments: dict[str, Any] | None = None) -> SkillExecution:
        run_dir = run_dir.resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        if skill.knowledge_dir:
            environment["LABONTOLOGY_SKILL_KNOWLEDGE_DIR"] = skill.knowledge_dir
        for artifact_id, path in (inputs or {}).items():
            environment["SKILL_INPUT_" + _env_key(artifact_id).removeprefix("SKILL_OUTPUT_")] = str(path)
        output_paths = {}
        for artifact_id, relative_path in skill.outputs.items():
            rendered = _render_output_template(str(relative_path)).replace("${RUN_DIR}", str(run_dir))
            path = Path(rendered)
            if not path.is_absolute():
                path = run_dir / path
            path.parent.mkdir(parents=True, exist_ok=True)
            environment[_env_key(artifact_id)] = str(path)
            output_paths[artifact_id] = str(path)
        command = list(skill.command) + list(skill.fixed_arguments)
        bindings = skill.argument_bindings if isinstance(skill.argument_bindings, dict) else {}
        for artifact_id, binding in (bindings.get("inputs", {}) or {}).items():
            if artifact_id in (inputs or {}):
                _append_binding(command, binding, str(inputs[artifact_id]), run_dir)
        for parameter, binding in (bindings.get("parameters", {}) or {}).items():
            if parameter in (arguments or {}):
                _append_binding(command, binding, arguments[parameter], run_dir)
        for artifact_id, binding in (bindings.get("outputs", {}) or {}).items():
            if artifact_id in output_paths:
                _append_binding(command, binding, output_paths[artifact_id], run_dir)
        try:
            completed = subprocess.run(
                command,
                cwd=skill.working_dir or str(run_dir),
                env=environment,
                capture_output=True,
                text=True,
                timeout=skill.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            (run_dir / "stdout.log").write_text(str(exc.stdout or ""), encoding="utf-8")
            (run_dir / "stderr.log").write_text(str(exc.stderr or ""), encoding="utf-8")
            return SkillExecution(
                f"run:{skill.id}", skill.id, "timed_out", error=str(exc),
                failure_kind="timeout", retryable=skill.side_effect_level == "read_only",
            )
        except OSError as exc:
            return SkillExecution(
                f"run:{skill.id}", skill.id, "failed", error=str(exc),
                failure_kind="launch_error", retryable=skill.side_effect_level == "read_only",
            )
        (run_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            return SkillExecution(
                f"run:{skill.id}", skill.id, "failed", return_code=completed.returncode,
                error=completed.stderr, failure_kind="process_exit",
            )
        missing = [path for path in output_paths.values() if not Path(path).exists()]
        if missing:
            return SkillExecution(
                f"run:{skill.id}", skill.id, "failed", return_code=completed.returncode,
                error=f"Missing outputs: {missing}", failure_kind="output_missing",
            )
        return SkillExecution(f"run:{skill.id}", skill.id, "succeeded", outputs=output_paths, return_code=completed.returncode)
