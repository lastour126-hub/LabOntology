"""Append-only observable feedback for lightweight workflow maintenance."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


_REASONING_FIELDS = {
    "analysis", "chain_of_thought", "explanation", "free_form_reasoning",
    "rationale", "reason", "reasoning", "thought", "thoughts",
}


def _json_safe(value: Any, *, field_name: str | None = None) -> Any:
    if field_name and field_name.casefold() in _REASONING_FIELDS:
        return None
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).casefold() in _REASONING_FIELDS:
                continue
            safe = _json_safe(item, field_name=str(key))
            if safe is not None:
                result[str(key)] = safe
        return result
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


class FeedbackStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "feedback.jsonl"

    def append(self, event: str, mission_id: str, skill_id: str | None,
               details: dict[str, Any]) -> dict[str, Any]:
        if not event.strip():
            raise ValueError("Feedback event is required")
        if not mission_id.strip():
            raise ValueError("Feedback mission_id is required")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "mission_id": mission_id,
            "skill_id": skill_id,
            "details": _json_safe(details),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def aggregate(self, event: str | None = None,
                  skill_id: str | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event is not None and record.get("event") != event:
                continue
            if skill_id is not None and record.get("skill_id") != skill_id:
                continue
            records.append(record)
        return records


def repeated_problems(feedback: list[dict[str, Any]], threshold: int = 3) -> list[dict[str, Any]]:
    if threshold < 1:
        raise ValueError("Repeated-problem threshold must be positive")
    problem_events = {"missing_precondition", "missing_capability", "skill_failed"}
    counts: dict[tuple[str, str | None], int] = {}
    for record in feedback:
        event = record.get("event")
        if event not in problem_events:
            continue
        key = (str(event), record.get("skill_id"))
        counts[key] = counts.get(key, 0) + 1
    suggestions = []
    targets = {
        "missing_precondition": ["preconditions", "documentation"],
        "missing_capability": ["preconditions", "documentation"],
        "skill_failed": ["failure_modes", "documentation"],
    }
    for (event, skill_id), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0], str(item[0][1]))):
        if count < threshold:
            continue
        suggestions.append({
            "event": event,
            "skill_id": skill_id,
            "count": count,
            "proposed_patch_target": {
                "entity_id": f"skill:{skill_id}" if skill_id else None,
                "fields": targets[event],
            },
        })
    return suggestions
