"""Load the declarative LabOntology class and relation schema."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CLASSES = ROOT / "references" / "ontology" / "classes.yaml"
RELATIONS = ROOT / "references" / "ontology" / "relations.yaml"


def load_schema() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the configured entity classes and relation specifications."""
    classes_doc = yaml.safe_load(CLASSES.read_text(encoding="utf-8")) or {}
    relations_doc = yaml.safe_load(RELATIONS.read_text(encoding="utf-8")) or {}
    return classes_doc.get("classes", {}), relations_doc.get("relations", {})
