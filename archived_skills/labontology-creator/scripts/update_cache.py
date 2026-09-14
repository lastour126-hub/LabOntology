from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow direct execution from the scripts directory without requiring callers
# to set PYTHONPATH manually.
MANAGER_ROOT = Path(__file__).resolve().parents[1]
if str(MANAGER_ROOT) not in sys.path:
    sys.path.insert(0, str(MANAGER_ROOT))

from data_manager.intake import MAINTAINABLE_KINDS, maintain_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain a LabOntology skill cache with user-provided knowledge")
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path, help="knowledge file or directory supplied by the user")
    parser.add_argument("--kind", choices=sorted(MAINTAINABLE_KINDS), default="knowledge")
    parser.add_argument("--skill-id", help="associate general knowledge with an existing Skill")
    parser.add_argument("--note", help="why this knowledge was added or updated")
    args = parser.parse_args()
    result = maintain_cache(
        args.cache_dir,
        args.source,
        kind=args.kind,
        skill_id=args.skill_id,
        note=args.note,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
