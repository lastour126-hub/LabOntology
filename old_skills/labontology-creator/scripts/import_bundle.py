from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow direct execution from the scripts directory without requiring callers
# to set PYTHONPATH manually.
MANAGER_ROOT = Path(__file__).resolve().parents[1]
if str(MANAGER_ROOT) not in sys.path:
    sys.path.insert(0, str(MANAGER_ROOT))

from data_manager.intake import receive_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Update a LabOntology skill knowledge cache")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(receive_bundle(args.bundle, args.workdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
