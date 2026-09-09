from __future__ import annotations

import ast
import csv
import json
import re
from pathlib import Path
from typing import Any

import yaml


MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "skill.yaml", "skill.yml", "package.yaml")
DOC_NAMES = ("SKILL.md", "README.md", "README.rst", "README.txt", "manifest.md")
KNOWLEDGE_SUFFIXES = {".json", ".yaml", ".yml", ".csv", ".md", ".rst", ".txt"}
KNOWLEDGE_ROOTS = {"kb", "knowledge", "references", "deviceknowledge", "workflow", "workflows", "devices"}
MAX_KNOWLEDGE_BYTES = 4 * 1024 * 1024

# These values are action identifiers, not Skill names. They are strong
# evidence of the capability a Skill needs because they come from the Skill's
# own action schema or structured knowledge file.
ACTION_CAPABILITIES = {
    "exp_pipetting": "capability:liquid-transfer",
    "exp_add_solid": "capability:solid-addition",
    "exp_filtering_samples": "capability:sample-filtration",
    "exp_high_filtering_samples": "capability:high-throughput-filtration",
    "exp_magnetic_stirrer": "capability:reaction-control",
}


def _evidence(source: str, path: Path, detail: str) -> dict[str, str]:
    return {"source": source, "file": str(path), "detail": detail}


def _document_files(skill_dir: Path) -> list[Path]:
    return sorted(
        path for path in skill_dir.rglob("*")
        if path.is_file() and path.name in DOC_NAMES
    )


def _markdown_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_markdown_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_heading or current_lines:
            sections.append({"heading": current_heading, "text": "\n".join(current_lines), "source": str(path)})

    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            flush()
            current_heading = match.group(1).strip()
            current_lines = []
        elif line.strip():
            current_lines.append(line.strip())
    flush()

    input_hints: list[str] = []
    output_hints: list[str] = []
    execution_order_hints: list[str] = []
    precondition_hints: list[str] = []
    constraint_hints: list[str] = []
    for section in sections:
        heading = section["heading"].lower()
        lines = _markdown_lines(section["text"])
        has_input_heading = bool(re.search(r"输入|input|参数|argument", heading))
        has_output_heading = bool(re.search(r"输出|output|结果", heading))
        if has_input_heading and has_output_heading:
            for line in lines:
                if re.search(r"(?:^[-*]\s*)?输入\s*[:：]", line, re.I):
                    input_hints.append(line)
                elif re.search(r"(?:^[-*]\s*)?输出\s*[:：]", line, re.I):
                    output_hints.append(line)
                else:
                    input_hints.append(line)
                    output_hints.append(line)
        elif has_input_heading:
            input_hints.extend(lines)
        elif has_output_heading:
            output_hints.extend(lines)
        if re.search(r"执行顺序|流程|workflow|sequence|步骤", heading):
            execution_order_hints.extend(lines)
        if re.search(r"前提|条件|precondition|requirement", heading):
            precondition_hints.extend(lines)
        if re.search(r"约束|限制|禁止|注意|constraint|restriction", heading):
            constraint_hints.extend(lines)

    related_files = sorted(set(re.findall(
        r"(?:\.\./|\./)?(?:KB|kb|references|scripts|devices|workflows?)/[A-Za-z0-9_.\-/]+",
        text,
    )))
    related_skill_refs = sorted(set(re.findall(
        r"(?:\.\./)?([A-Za-z0-9][A-Za-z0-9_-]*)/SKILL\.md",
        text,
    )))
    device_evidence = [
        line for line in _markdown_lines(text)
        if re.search(r"设备|设备接口|device\s+api|AddTask|StartTask|GetTaskInfo|Notice|resource", line, re.I)
    ]
    return {
        "path": str(path),
        "sections": sections,
        "input_hints": sorted(set(input_hints)),
        "output_hints": sorted(set(output_hints)),
        "execution_order_hints": sorted(set(execution_order_hints)),
        "precondition_hints": sorted(set(precondition_hints)),
        "constraint_hints": sorted(set(constraint_hints)),
        "related_files": related_files,
        "related_skill_refs": related_skill_refs,
        "device_evidence": sorted(set(device_evidence)),
    }


def _merge_documentation(documents: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "input_hints", "output_hints", "execution_order_hints", "precondition_hints",
        "constraint_hints", "related_files", "related_skill_refs", "device_evidence",
    )
    merged: dict[str, Any] = {
        "files": [item["path"] for item in documents],
        "sections": [section for item in documents for section in item["sections"]],
    }
    for field in fields:
        merged[field] = sorted({value for item in documents for value in item[field]})
    return merged


def _top_level_keys(data: Any) -> list[str]:
    if isinstance(data, dict):
        return sorted(str(key) for key in data)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return sorted({str(key) for item in data[:100] for key in item})
    return []


def _semantic_values(data: Any) -> list[str]:
    values: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            key_text = str(key).lower()
            if key_text in {"schema", "schema_version", "version", "unit_type", "action", "action_type"}:
                if isinstance(value, (str, int, float)):
                    values.add(str(value))
            values.update(_semantic_values(value))
    elif isinstance(data, list):
        for item in data[:100]:
            values.update(_semantic_values(item))
    return sorted(values)


def _knowledge_file_record(path: Path, skill_dir: Path) -> dict[str, Any]:
    relative = path.relative_to(skill_dir).as_posix()
    record: dict[str, Any] = {
        "path": relative,
        "source": str(path),
        "format": path.suffix.lower().lstrip(".") or "text",
        "size_bytes": path.stat().st_size,
        "parse_status": "indexed",
        "top_level_keys": [],
        "semantic_values": [],
        "facts": {},
    }
    if path.stat().st_size > MAX_KNOWLEDGE_BYTES:
        record["parse_status"] = "too_large"
        record["unresolved"] = [f"file exceeds {MAX_KNOWLEDGE_BYTES} byte inspection limit"]
        return record
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            record["top_level_keys"] = _top_level_keys(data)
            record["semantic_values"] = _semantic_values(data)
            record["facts"] = {
                "kind": "array" if isinstance(data, list) else "object" if isinstance(data, dict) else "scalar",
                "item_count": len(data) if isinstance(data, (list, dict)) else 1,
            }
        elif path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
            record["top_level_keys"] = _top_level_keys(data)
            record["semantic_values"] = _semantic_values(data)
            record["facts"] = {
                "kind": "array" if isinstance(data, list) else "object" if isinstance(data, dict) else "scalar",
                "item_count": len(data) if isinstance(data, (list, dict)) else 1,
            }
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            record["columns"] = rows[0] if rows else []
            record["facts"] = {"row_count": max(len(rows) - 1, 0)}
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            record["headings"] = [match.group(1).strip() for match in re.finditer(r"^#{1,6}\s+(.+)$", text, re.M)]
            record["facts"] = {"line_count": len(text.splitlines())}
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, csv.Error) as exc:
        record["parse_status"] = "parse_error"
        record["unresolved"] = [f"{type(exc).__name__}: {exc}"]
    if path.name.lower() == "aliases.json" and isinstance(record.get("facts"), dict):
        record["facts"]["alias_count"] = record["facts"].get("item_count", 0)
    return record


def _knowledge_files(skill_dir: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in KNOWLEDGE_SUFFIXES:
            continue
        relative_parts = path.relative_to(skill_dir).parts
        if not relative_parts or relative_parts[0].lower() not in KNOWLEDGE_ROOTS:
            continue
        if path.name in DOC_NAMES:
            continue
        result.append(_knowledge_file_record(path, skill_dir))
    return result


def _markdown_metadata(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            metadata = yaml.safe_load(parts[1]) or {}
            body = parts[2]
    description = metadata.get("description")
    if not description:
        paragraphs = [line.strip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if paragraphs:
            description = paragraphs[0]
    if description:
        metadata["description"] = description
    return metadata, [_evidence("markdown", path, "description and frontmatter")]


def _python_parameters(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return [], [_evidence("python_ast", path, "syntax error; skipped")]
    parameters: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        names = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        option_name = next((item for item in names if item.startswith("-")), None)
        positional_name = next((item for item in names if not item.startswith("-")), None)
        raw_name = option_name or positional_name
        name = raw_name.lstrip("-").replace("-", "_") if raw_name else None
        if not name:
            continue
        values = {keyword.arg: keyword.value for keyword in node.keywords}
        required = values.get("required")
        default = values.get("default")
        parameter = {
            "name": name,
            "required": required.value if isinstance(required, ast.Constant) else None,
            "default": default.value if isinstance(default, ast.Constant) else None,
        }
        if option_name is None and positional_name is not None:
            parameter["positional"] = True
        parameters.append(parameter)
    return parameters, [_evidence("python_ast", path, "argparse.add_argument")]


def _manifest_data(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    for name in MANIFEST_NAMES:
        candidate = path / name
        if candidate.exists():
            try:
                return yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}, [_evidence("manifest", candidate, "structured metadata")]
            except yaml.YAMLError:
                return {}, [_evidence("manifest", candidate, "invalid YAML; skipped")]
    return {}, []


def _merge_parameters(manifest: dict[str, Any], discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = manifest.get("inputs", manifest.get("parameters", [])) or []
    parameters: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            parameters.append({"name": item, "required": None, "default": None})
        elif isinstance(item, dict) and item.get("name"):
            parameters.append({**item, "name": item["name"], "required": item.get("required"), "default": item.get("default")})
    seen = {item["name"] for item in parameters}
    parameters.extend(item for item in discovered if item["name"] not in seen)
    return parameters


def _normalise_outputs(raw: Any) -> list[dict[str, Any]]:
    """Normalize common output declarations without inferring missing outputs."""
    if not raw:
        return []
    if isinstance(raw, dict):
        normalized: list[dict[str, Any]] = []
        for name, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("name", str(name))
            else:
                item = {"name": str(name)}
                if isinstance(value, str):
                    item["path"] = value
                elif value is not None:
                    item["value"] = value
            normalized.append(item)
        return normalized
    if isinstance(raw, str):
        return [{"name": raw}]
    if isinstance(raw, list):
        normalized = []
        for item in raw:
            if isinstance(item, str):
                normalized.append({"name": item})
            elif isinstance(item, dict) and item.get("name"):
                normalized.append(dict(item))
        return normalized
    return []


def _normalise_references(raw: Any) -> list[str]:
    """Normalize capability/dependency references while preserving only explicit values."""
    if not raw:
        return []
    values = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    references: list[str] = []
    for item in values:
        if isinstance(item, str):
            references.append(item)
        elif isinstance(item, dict):
            value = item.get("id") or item.get("name")
            if value:
                references.append(str(value))
    return references


def _artifact_id_from_path(path: str) -> str:
    filename = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    stem = re.sub(r"[_-]<[^>]+>", "", stem)
    stem = re.sub(r"<[^>]+>", "", stem)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return f"artifact:{stem or 'result'}"


def _output_path_candidates(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pattern = re.compile(
        r"`([^`\r\n]*(?:output[\\/][^`\r\n]+\.(?:json|csv|md|yaml|yml|txt)|"
        r"[A-Za-z0-9_.-]+\.(?:json|csv|md|yaml|yml|txt))[^`\r\n]*)`",
        re.I,
    )
    for document in documents:
        for hint in document.get("output_hints", []):
            for match in pattern.finditer(hint):
                path = match.group(1).strip().rstrip("。，；,;")
                suffix = Path(path.replace("\\", "/")).suffix.lower().lstrip(".")
                candidates.append({
                    "name": _artifact_id_from_path(path),
                    "format": suffix or None,
                    "path": path,
                    "source": "documentation",
                    "confidence": 0.75,
                    "evidence": [hint],
                })
    return candidates


def _python_output_parameters(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    parameters: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        names = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        name = next((item.lstrip("-").replace("-", "_") for item in names if item.startswith("-")), None)
        if not name or not re.search(r"(?:^|_)(?:output|result)(?:_|$)", name, re.I):
            continue
        required = next((keyword.value.value for keyword in node.keywords if keyword.arg == "required" and isinstance(keyword.value, ast.Constant)), None)
        parameter_format = None
        lowered = name.lower()
        if "json" in lowered:
            parameter_format = "json"
        elif "csv" in lowered:
            parameter_format = "csv"
        parameters.append({"parameter": name, "required": required is True, "format": parameter_format})

    source_text = path.read_text(encoding="utf-8", errors="replace").lower()
    if "json.dump" in source_text or "json.dumps" in source_text:
        detected_format = "json"
    elif "to_csv" in source_text or "csv.writer" in source_text:
        detected_format = "csv"
    else:
        detected_format = None
    for item in parameters:
        item["format"] = item["format"] or detected_format
        item["file"] = str(path)
    return parameters


def _output_contract_data(
    manifest: dict[str, Any],
    documents: list[dict[str, Any]],
    skill_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    explicit_outputs = _normalise_outputs(manifest.get("outputs", manifest.get("output", [])))
    if explicit_outputs:
        return explicit_outputs, [{
            "field": "outputs",
            "source": "manifest",
            "detail": "explicit output declaration",
            "confidence": 1.0,
        }]

    documented = _output_path_candidates(documents)
    scripted = [item for path in sorted(skill_dir.rglob("*.py")) for item in _python_output_parameters(path)]
    outputs: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []

    for candidate in documented:
        existing = outputs.get(candidate["name"])
        if existing is None or len(candidate["path"]) < len(existing["path"]):
            outputs[candidate["name"]] = {
                key: value for key, value in candidate.items() if key != "evidence"
            }

    for item in scripted:
        matching = next((candidate for candidate in outputs.values() if candidate.get("format") == item.get("format")), None)
        if matching:
            matching["required"] = item["required"]
            matching["source"] = "script_and_documentation"
            matching["confidence"] = 0.9
            matching["binding"] = {
                "parameter": item["parameter"],
                "flag": "--" + item["parameter"].replace("_", "-"),
            }
            evidence.append({
                "field": "outputs",
                "source": "script_and_documentation",
                "file": item["file"],
                "detail": f"output parameter {item['parameter']!r} matches documented output",
                "confidence": 0.9,
            })
            continue
        name = "artifact:result" if item["parameter"] == "output" else _artifact_id_from_path(item["parameter"])
        suffix = item.get("format") or "json"
        outputs.setdefault(name, {
            "name": name,
            "format": item.get("format"),
            "path": f"output/{name.removeprefix('artifact:')}_<timestamp>.{suffix}",
            "required": item["required"],
            "source": "script",
            "confidence": 0.7,
        })
        evidence.append({
            "field": "outputs",
            "source": "script",
            "file": item["file"],
            "detail": f"output parameter {item['parameter']!r} detected by Python AST",
            "confidence": 0.7,
        })

    if documented and not scripted:
        evidence.append({
            "field": "outputs",
            "source": "documentation",
            "detail": "output path and format extracted from documentation",
            "confidence": 0.75,
        })
    return list(outputs.values()), evidence


def _capability_data(
    manifest: dict[str, Any],
    knowledge_files: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Collect explicit and strong Skill-owned capability evidence.

    Explicit manifest declarations are authoritative. Structured action
    identifiers in the Skill's own knowledge files are high-confidence
    evidence, but still remain reviewable data in the imported bundle.
    Skill names and free-form wording are intentionally not used here.
    """
    capabilities: list[str] = []
    evidence: list[dict[str, Any]] = []

    for capability in _normalise_references(
        manifest.get("required_capabilities", manifest.get("requires_capability", []))
    ):
        if capability in capabilities:
            continue
        capabilities.append(capability)
        evidence.append({
            "capability": capability,
            "source": "manifest",
            "file": "<skill-manifest>",
            "detail": "explicit required_capabilities declaration",
            "confidence": 1.0,
        })

    for record in knowledge_files:
        for value in record.get("semantic_values", []):
            capability = ACTION_CAPABILITIES.get(str(value).lower())
            if not capability or capability in capabilities:
                continue
            capabilities.append(capability)
            evidence.append({
                "capability": capability,
                "source": "knowledge",
                "file": record["path"],
                "detail": f"action identifier {value!r} in structured Skill knowledge",
                "confidence": 0.9,
            })

    return capabilities, evidence


def discover_skill(skill_dir: Path) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    manifest_data, evidence = _manifest_data(skill_dir)
    metadata: dict[str, Any] = {}
    documents = []
    for candidate in _document_files(skill_dir):
        candidate_metadata, doc_evidence = _markdown_metadata(candidate)
        if not metadata:
            metadata = candidate_metadata
        evidence.extend(doc_evidence)
        documents.append(_parse_markdown_document(candidate))
    evidence.append(_evidence("manifest", skill_dir / "<directory>", "skill directory scanned"))
    for name in MANIFEST_NAMES:
        if (skill_dir / name).exists():
            break
    python_parameters: list[dict[str, Any]] = []
    for path in sorted(skill_dir.rglob("*.py")):
        found, python_evidence = _python_parameters(path)
        python_parameters.extend(found)
        evidence.extend(python_evidence)
    skill_id = manifest_data.get("id") or manifest_data.get("skill_id") or metadata.get("name") or skill_dir.name
    description = manifest_data.get("description") or metadata.get("description")
    parameters = _merge_parameters(manifest_data, python_parameters)
    outputs, contract_evidence = _output_contract_data(manifest_data, documents, skill_dir)
    knowledge_files = _knowledge_files(skill_dir)
    required_capabilities, capability_evidence = _capability_data(manifest_data, knowledge_files)
    dependencies = _normalise_references(
        manifest_data.get("dependencies", manifest_data.get("runtime_dependencies", []))
    )
    side_effect_level = manifest_data.get("side_effect_level")
    unresolved: list[str] = []
    if not description:
        unresolved.append("description")
    if not parameters:
        unresolved.append("parameters")
    if not outputs:
        unresolved.append("outputs")
    if side_effect_level is None:
        unresolved.append("side_effect_level")
    return {
        "id": str(skill_id),
        "name": str(manifest_data.get("name") or metadata.get("name") or skill_id),
        "description": description,
        "source_dir": str(skill_dir),
        "parameters": parameters,
        "outputs": outputs,
        "contract_evidence": contract_evidence,
        "required_capabilities": required_capabilities,
        "capability_evidence": capability_evidence,
        "dependencies": dependencies,
        "side_effect_level": side_effect_level,
        "entrypoints": [str(path) for path in sorted(skill_dir.rglob("*.py"))],
        "status": "discovered",
        "validated": False,
        "enabled": False,
        "confidence": round(0.5 + (0.2 if description else 0) + (0.2 if parameters else 0) + (0.1 if manifest_data else 0), 2),
        "unresolved": unresolved,
        "evidence": evidence,
        "documentation": _merge_documentation(documents),
        "knowledge_files": knowledge_files,
        "knowledge_summary": {
            "file_count": len(knowledge_files),
            "formats": sorted({item["format"] for item in knowledge_files}),
        },
    }


def discover_tree(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    candidates: set[Path] = set()
    for directory in (root, *[path for path in root.rglob("*") if path.is_dir()]):
        if any((directory / name).exists() for name in (*MANIFEST_NAMES, *DOC_NAMES)):
            candidates.add(directory)
    # A skill may contain documentation for internal folders (for example
    # graph/, scripts/, or KB/). Once a parent declares the skill, do not
    # rediscover those folders unless they declare their own manifest/entry.
    roots = [path for path in candidates if any((path / name).exists() for name in MANIFEST_NAMES + ("SKILL.md",))]
    candidates = {
        path for path in candidates
        if not any(path != parent and parent in path.parents for parent in roots)
        or any((path / name).exists() for name in MANIFEST_NAMES + ("SKILL.md",))
    }
    return [discover_skill(path) for path in sorted(candidates)]


def _copy_directory(source: Path | None, destination: Path) -> None:
    if not source or not source.exists():
        return
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def export_bundle(
    root: Path,
    output_dir: Path,
    suite_id: str,
    device_knowledge: Path | None = None,
    workflows: Path | None = None,
) -> Path:
    """Write a portable, non-executable bundle for ontology intake."""
    skills = discover_tree(root)
    for skill in skills:
        skill["status"] = "draft"
    bundle = {
        "schema": "labontology.skill-bundle.v1",
        "suite_id": suite_id,
        "skills": skills,
        "device_knowledge": [],
        "workflows": [],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_dir = output_dir / "Knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    for skill in skills:
        source_dir = Path(skill["source_dir"])
        destination = knowledge_dir / skill["id"].split(":", 1)[-1]
        for relative in skill.get("knowledge_files", []):
            source = source_dir / relative["path"]
            if not source.exists():
                continue
            target = destination / relative["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    (output_dir / "DeviceKnowledge").mkdir(exist_ok=True)
    (output_dir / "Workflow").mkdir(exist_ok=True)
    _copy_directory(device_knowledge, output_dir / "DeviceKnowledge")
    _copy_directory(workflows, output_dir / "Workflow")
    (output_dir / "skills.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_dir
