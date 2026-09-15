from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

VENDOR_DIR = Path(__file__).resolve().parents[2] / "_vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

import yaml

from .importer import discover_tree, export_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Import and maintain structured LabOntology data from heterogeneous laboratory Skills")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("json", "yaml"), default="json")
    parser.add_argument("--bundle-dir", type=Path, help="write a standardized ontology intake bundle")
    parser.add_argument("--suite-id", default="suite:imported")
    parser.add_argument("--device-knowledge", type=Path)
    parser.add_argument("--workflow", type=Path)
    args = parser.parse_args()
    if args.bundle_dir:
        export_bundle(args.root, args.bundle_dir, args.suite_id, args.device_knowledge, args.workflow)
        print(args.bundle_dir.resolve())
        return 0
    report = discover_tree(args.root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else yaml.safe_dump(report, allow_unicode=True, sort_keys=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
