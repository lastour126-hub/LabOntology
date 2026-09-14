"""Host-Agent mission loop for Agent-directed Skill selection."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.commands import main


if __name__ == "__main__":
    # Agent tools consume JSON over pipes; Windows' locale encoding may be GBK.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    commands = {"run", "resume", "status", "context", "act", "reconcile"}
    if sys.argv[1:2] and sys.argv[1] in commands:
        argv = sys.argv[1:]
    else:
        argv = ["run", *sys.argv[1:]]
    raise SystemExit(main(argv))
