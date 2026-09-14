"""UTF-8 command adapter for advanced LabOntology Runtime operations."""
from __future__ import annotations

import sys

from core.runtime.commands import main


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    commands = {"run", "resume", "status", "context", "act", "reconcile"}
    argv = sys.argv[1:] if sys.argv[1:2] and sys.argv[1] in commands else ["run", *sys.argv[1:]]
    raise SystemExit(main(argv))
