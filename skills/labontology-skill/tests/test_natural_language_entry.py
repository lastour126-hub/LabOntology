from pathlib import Path


def test_skill_routes_natural_language_tasks_without_exposing_commands():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.lower().split())

    assert "## Conversation-first workflow" in skill
    assert "## Entry protocol" in skill
    assert "## Safety boundary" in skill
    assert "不需要手动调用其他 skill" in normalized
    assert "准备或规划实验" in skill
    assert "检查条件或查看进度" in skill
    assert "维护、修复或改进实验流程库" in skill
    assert "请求一个实验相关动作" in skill


def test_skill_requires_runtime_reentry_before_answering_any_follow_up():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "每个新的实验请求、后续追问、失败恢复和下一步操作，都必须重新回到 labontology" in normalized
    assert "即使只是根据上一轮结果做解释、排序或汇总，也不能直接凭对话记忆回答" in normalized
    assert "必须至少重新执行 bootstrap 和 `context`" in normalized


def test_readme_explains_conversation_first_use():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "## Use it in conversation" in readme
    assert "The Agent selects the workflow internally" in readme


def test_skill_requires_automatic_workspace_preparation():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "首次进入时自动准备可用的实验流程" in skill
    assert "python scripts/labontology.py bootstrap" in skill
    assert "bootstrap → mission → context → prepare-skill → act → context" in skill
    assert "waiting_agent" in skill
    assert "waiting_agent" in skill
    assert "reconcile" in skill
    assert "resume" in skill
    assert "完整读取当前 Worker Skill" in skill
    assert "先回到 LabOntology" in skill
    assert "resolve-cache" not in skill


def test_skill_contains_an_enforceable_runtime_protocol_and_state_gates():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "## Runtime protocol" in skill
    assert "references/runtime-protocol.md" in skill
    assert "mission" in normalized
    assert "context" in normalized
    assert "prepare-skill" in normalized
    assert "act" in normalized
    assert "resume" in normalized
    assert "没有 `mission_id`" in skill
    assert "没有执行 `prepare-skill`" in skill
    assert "不读取 worker" in normalized
    assert "runtime 结果已经出现在 `context` 中" in normalized
    assert "已完成的 worker 不要重复调用 `resume`" in normalized
    assert "worker_cycle" in normalized
    assert "requires_reconcile" in normalized
    assert "resume_mode" in normalized


def test_runtime_protocol_reference_contains_operational_details():
    reference = (Path(__file__).resolve().parents[1] / "references" / "runtime-protocol.md")
    assert reference.is_file()
    text = reference.read_text(encoding="utf-8")
    normalized = " ".join(text.casefold().split())

    assert "bootstrap" in normalized
    assert "run" in normalized
    assert "context" in normalized
    assert "prepare-skill" in normalized
    assert "act" in normalized
    assert "resume" in normalized
    assert "one worker" in normalized
    assert "action-id" in normalized
    assert "worker_cycle.requires_resume" in normalized
    assert "worker_cycle" in normalized
    assert "requires_reconcile" in normalized
    assert "match_found" in normalized
    assert "registered_skill_count" in normalized
    assert "does not execute a subprocess" in normalized


def test_readme_keeps_runtime_protocol_in_the_reference_file():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "references/runtime-protocol.md" in readme
    assert "run → context → prepare-skill" not in readme


def test_skill_keeps_workspace_graph_details_out_of_the_entrypoint():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "SkillSuite" not in skill
    assert "ontology.jsonl" not in skill
    assert "source-index.json" not in skill


def test_skill_defines_laboratory_language_for_common_user_states():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "## User-facing response contract" in skill
    assert "**Ready:**" in skill
    assert "**Missing condition:**" in skill
    assert "**Waiting for approval:**" in skill
    assert "**Paused task:**" in skill
    assert "不要主动展示内部路径、命令、原始异常或实现细节；用户明确要求且路径属于当前任务已登记产物时" in skill


def test_skill_makes_the_labontology_script_working_directory_explicit():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "不要假设宿主当前目录包含 `scripts/`" in skill


def test_labontology_is_first_entrypoint_for_laboratory_and_maintenance_requests():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.lower().split())

    assert "must be used first" in normalized
    assert "实验任务和实验流程库维护请求" in normalized
    assert "workflow-library" in normalized
    assert "workflow-improvement" in normalized
    assert "self-evolution" in normalized
    assert "自我演化" in skill
    assert "unified entrypoint" in normalized
    assert "do not invoke another laboratory skill before labontology" in normalized
    assert "不得直接把 worker skill 当作用户请求的入口" in normalized


def test_entry_explicitly_keeps_general_artifact_tasks_outside_labontology():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "普通写作、表格、图片、ppt 和一般文件处理" in normalized
    assert "不属于 labontology 实验入口" in normalized
    assert "不要因为这些任务包含文件、分析或生成结果就启动 labontology" in normalized
    assert "下一条实验目标重新判断" in normalized


def test_entry_instructions_make_self_evolution_a_labontology_responsibility():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.lower().split())

    assert "labontology 是所有实验任务和实验流程库维护请求的统一入口" in normalized
    assert "根据重复失败、缺少条件或用户纠正推动实验流程的自我演化和自我改进" in skill
    assert "先使用 labontology，再选择或读取 worker skill" in normalized


def test_entry_documents_non_worker_runtime_branches_and_mission_reuse():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "match_found=false" in normalized
    assert "request_human" in normalized
    assert "complete" in normalized
    assert "复用原 `mission_id`" in skill
    assert "input-artifact" in normalized
    assert "suggest-maintenance" in normalized


def test_entry_requires_worker_contract_coverage_before_selection():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "候选 worker 的能力必须覆盖当前目标" in normalized
    assert "不能仅因为输入 artifact 匹配就选择 worker" in normalized
    assert "声明的 `outputs`" in normalized
    assert "`missing_inputs` 非空" in normalized


def test_entry_allows_structured_worker_contract_to_complete_sparse_skill_prose():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "manifest、声明的 `outputs`、entrypoint 和完整 worker skill" in normalized
    assert "不能因为 prose 没有逐字重复操作名称就判定 worker 缺失" in normalized
    assert "仍然必须先读取完整 skill 文档" in normalized


def test_entry_interprets_aligned_command_and_output_names_as_contract_evidence():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "entrypoint" in normalized
    assert "完整 worker skill" in normalized


def test_runtime_reference_documents_all_resume_modes_and_artifact_boundaries():
    reference = (Path(__file__).resolve().parents[1] / "references" / "runtime-protocol.md")
    normalized = " ".join(reference.read_text(encoding="utf-8").casefold().split())

    assert '"kind": "request_human"' in normalized
    assert '"kind": "complete"' in normalized
    assert "--answer" in normalized
    assert "--input-artifact" in normalized
    assert "artifact_dir" in normalized
    assert "suggest-maintenance" in normalized
    assert "maintain-graph" in normalized
    assert "restore-backup" in normalized


def test_readme_shows_user_facing_experiment_language():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "Responses are written for experiment users" in readme
    assert "实验流程库需要更新" in readme


def test_skill_entry_does_not_expose_implementation_details():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8").casefold()

    forbidden = (
        "resolve-cache", "sync --skill-root", "--workspace", "--suite-id", "--cache-dir",
        "skillsuite", "ontology.jsonl", "source-index.json", "cache-manifest.json",
        ".backup/", "pytest", "hook", "plugin", "artifact_dir", "<cache-dir>",
    )
    assert not any(value in skill for value in forbidden)
