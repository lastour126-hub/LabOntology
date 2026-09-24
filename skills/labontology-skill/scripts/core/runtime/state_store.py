from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .feedback import FeedbackStore
from .experience import ExperienceStore
from .models import MissionState


class StateStore:
    def __init__(self, root: Path, mission_id: str):
        self.mission_id = mission_id
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", mission_id)
        self.run_dir = Path(root) / safe_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.feedback = FeedbackStore(self.run_dir.parent)
        self.experiences = ExperienceStore(self.run_dir.parent)

    def save(self, state: MissionState) -> None:
        self.state_path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> MissionState:
        return MissionState.from_dict(json.loads(self.state_path.read_text(encoding="utf-8")))

    def event(self, event: str, payload: dict[str, Any]) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **payload}
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
