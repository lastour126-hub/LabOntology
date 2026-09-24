"""Small, local store for reusable successful mission experience.

Experience is deliberately separate from the ontology graph.  It is an
advisory hint for the host Agent, not a source of execution authority.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import MissionState


MAX_RECORDS = 200
MAX_RESULTS = 3
MAX_SUMMARY_CHARS = 1000
MAX_CONSTRAINT_CHARS = 300


def _terms(value: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9]+", value.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", value):
        terms.add(run)
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return terms


def _clean_list(values: Any, limit: int) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    result = {str(value).strip() for value in values if str(value).strip()}
    return sorted(result)[:limit]


class ExperienceStore:
    """Append-only JSONL experience store with bounded, simple compaction."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.path = self.root / "experiences.jsonl"
        self.backup_dir = self.root / ".backup"

    def record_success(
        self,
        *,
        goal: str,
        skill_ids: list[str],
        summary: str,
        constraints: list[str] | None = None,
        artifact_types: list[str] | None = None,
        mission_id: str | None = None,
    ) -> dict[str, Any]:
        goal = str(goal).strip()
        summary = str(summary).strip()
        if not goal:
            raise ValueError("Experience goal is required")
        if not summary:
            raise ValueError("Experience summary is required")
        existing = self._read()
        if mission_id:
            for record in existing:
                if record.get("mission_id") == mission_id:
                    return record
        record: dict[str, Any] = {
            "experience_id": f"experience:{uuid.uuid4().hex}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "succeeded",
            "goal": goal[:MAX_SUMMARY_CHARS],
            "skills": _clean_list(skill_ids, 20),
            "summary": summary[:MAX_SUMMARY_CHARS],
            "constraints": [str(item).strip()[:MAX_CONSTRAINT_CHARS]
                            for item in _clean_list(constraints, 10)],
            "artifact_types": _clean_list(artifact_types, 10),
        }
        if mission_id:
            record["mission_id"] = str(mission_id)
        existing.append(record)
        self._write(existing)
        return record

    def record_mission(self, state: MissionState) -> dict[str, Any]:
        skill_ids = sorted({str(item.get("skill_id"))
                            for item in state.skill_executions.values()
                            if isinstance(item, dict) and item.get("skill_id")})
        summaries = [str(item.get("summary", "")).strip()
                     for item in state.observations
                     if isinstance(item, dict)
                     and item.get("status") in {"succeeded", "reconciled_succeeded"}
                     and str(item.get("summary", "")).strip()]
        if not summaries:
            summaries = [str(item.get("summary", "")).strip()
                         for item in state.observations
                         if isinstance(item, dict) and str(item.get("summary", "")).strip()]
        summary = summaries[-1] if summaries else state.goal
        artifact_types = sorted({Path(str(value)).suffix.lstrip(".")
                                 for value in state.artifacts.values()
                                 if Path(str(value)).suffix})
        return self.record_success(
            goal=state.goal,
            skill_ids=skill_ids,
            summary=summary,
            constraints=state.constraints,
            artifact_types=artifact_types,
            mission_id=state.mission_id,
        )

    def search(self, goal: str, *, skill_ids: list[str] | None = None,
               limit: int = MAX_RESULTS) -> list[dict[str, Any]]:
        query_terms = _terms(goal)
        query_skills = set(_clean_list(skill_ids, 100))
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        for record in self._read():
            if record.get("status") != "succeeded":
                continue
            record_terms = _terms(f"{record.get('goal', '')} {record.get('summary', '')}")
            score = len(query_terms & record_terms)
            score += 2 * len(query_skills & set(record.get("skills", [])))
            if score:
                ranked.append((score, str(record.get("created_at", "")), record))
        ranked.sort(key=lambda item: item[1], reverse=True)
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [self._compact(record) for _, _, record in ranked[:max(0, min(limit, MAX_RESULTS))]]

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("status") == "succeeded":
                records.append(value)
        return records[-MAX_RECORDS:]

    def _write(self, records: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        needs_compaction = len(records) > MAX_RECORDS
        if needs_compaction:
            records = records[-MAX_RECORDS:]
        if self.path.is_file() and needs_compaction:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.path, self.backup_dir / "experiences.jsonl")
        temporary = self.path.with_suffix(".jsonl.tmp")
        temporary.write_text(
            "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for record in records),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _compact(record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: record.get(key, default)
            for key, default in (
                ("experience_id", None),
                ("created_at", None),
                ("status", "succeeded"),
                ("goal", ""),
                ("skills", []),
                ("summary", ""),
                ("constraints", []),
                ("artifact_types", []),
            )
        }
