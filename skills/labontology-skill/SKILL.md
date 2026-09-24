---
name: labontology
description: >
  Use when a request involves laboratory, chemistry, molecular, experiment,
  protocol, sample, reagent, instrument, device, analysis, readiness,
  paused-task, workflow-library, Skill-selection, workflow-improvement,
  self-evolution, self-improvement, or feedback-driven workflow maintenance
  work. LabOntology MUST be used first as the unified entrypoint and
  supervisor. Do not invoke another laboratory Skill before LabOntology.
  Do not use it for ordinary writing, spreadsheets, images, presentations,
  or general file-generation tasks unless they are part of a laboratory task.
---

# LabOntology

LabOntology 是所有实验任务和实验流程库维护请求的统一入口，也是当前任务的持续监督者。
先使用 LabOntology，再选择或读取 Worker Skill。LabOntology 不是只在任务开始时初始化一次；每个新的实验请求、后续追问、失败恢复和下一步操作，都必须重新回到 LabOntology。

只要请求涉及实验、样品、试剂、仪器、设备、协议、分析、准备检查、暂停恢复、流程库维护或 Skill 选择，都必须先进入 LabOntology。用户不需要知道内部流程，也不需要手动调用其他 Skill。

普通任务保持在实验流程之外：普通写作、表格、图片、PPT 和一般文件处理不属于 LabOntology 实验入口。宿主 Agent 不要因为这些任务包含文件、分析或生成结果就启动 LabOntology，而应直接交给对应的通用能力。普通任务完成后，下一条实验目标重新判断；只有确实属于实验任务时，才重新进入 LabOntology，不复用普通任务的 mission。

后续对话也有硬门槛：即使只是根据上一轮结果做解释、排序或汇总，也不能直接凭对话记忆回答。先运行 bootstrap（允许返回 `reused=true`），再用原 mission 的 `context` 核对当前状态和已登记 artifact；只有 Runtime 结果重新出现在 `context` 后才能回答。若目标变化或需要新的动作，继续按当前 `context` 重新规划；若只是读取已完成结果，也必须至少重新执行 bootstrap 和 `context`，不得因为任务看起来简单就跳过 LabOntology。

## Entry protocol

在回答或调用其他 Skill 前，必须按以下顺序处理当前请求：

1. 准备或复用当前工作区和任务上下文；首次进入时自动准备可用的实验流程。
2. 为新的目标创建 mission；如果是同一任务的追问、恢复或失败处理，复用原 `mission_id`。
3. 读取当前 mission 的 context：只有 `match_found=true` 且确实需要 Worker 时，才从 `skills` 选择一个最匹配的 Worker；候选 Worker 的能力必须覆盖当前目标，不能仅因为输入 artifact 匹配就选择 Worker。能力判断要综合候选卡片、manifest、声明的 `outputs`、entrypoint 和完整 Worker Skill；如果结构化合同和 entrypoint 已明确声明该操作，不能因为 prose 没有逐字重复操作名称就判定 worker 缺失。脚本和 entrypoint 只能作为合同证据和可选加速器，不能替代完整 Worker Skill，也不能决定 Worker 是否可用；仍然必须先读取完整 Skill 文档。若候选卡片的 `missing_inputs` 非空，或结构化合同、entrypoint 和完整 Worker Skill 仍不能覆盖目标，就不要发出 `kind=skill`，而是报告缺少条件或缺少 Worker。选择前核对候选卡片、声明的 `outputs` 和完整 Worker Skill；若只能覆盖部分步骤，就报告缺少的 Worker，不要把部分结果当作完整任务。无匹配时，低风险只读任务先征得用户同意，再使用 `agent_fallback`；其他情况提出一个澄清问题。
4. 选择 Worker 后，完整读取当前 Worker Skill，并执行 `prepare-skill`，记录本次读取的 Skill 文档。
5. 生成一个边界清晰的动作决策；一次只执行一个动作。没有 Worker 的澄清、等待用户或完成任务也必须通过 Runtime 的动作决策记录。
6. 调用 `act` 后读取 Runtime 返回的状态：Worker 统一进入 `waiting_agent`，由宿主 Agent 按已读取的文档执行；若选择使用文档中声明的可选脚本，也必须由宿主显式调用并把真实结果通过 `resume` 回传，然后回到 `context`。
7. `resume` 返回用户回答后，必须把它当作新的规划输入重新读取 `context`；看到 `replan_required=true` 时，必须重新选择 Worker，不能直接 `complete`，也不能自行用本地代码补做 Worker 工作。
8. 只有 Runtime 结果已经出现在 `context` 中，才能向用户汇报最终结果；`request_human` 是有意的用户问题，`complete` 只能在 Runtime 确认任务完成后使用。需要下一步时，先回到 LabOntology，再读取 context，选择下一个 Worker。

开始正式处理实验任务前，从本 Skill 根目录运行自带的 `python scripts/labontology.py bootstrap` 入口准备工作区；不要求用户提供路径或参数。命令执行时必须确认当前工作目录就是 LabOntology Skill 根目录，或改用该目录下 `scripts/labontology.py` 的绝对路径；不要假设宿主当前目录包含 `scripts/`。先确认脚本存在，再运行 bootstrap。不要在 bootstrap 后停下，也不要把 bootstrap 的成功当作实验任务已经完成。

执行任务时，必须读取并遵循 [references/runtime-protocol.md](references/runtime-protocol.md)。该文件包含 Runtime 命令、mission 状态、Worker 读取门槛、动作决策和结果回传的具体方法。

## Runtime protocol

正式任务的最小回转顺序是：

```text
bootstrap → mission → context → prepare-skill → act → context
                                             └─ waiting_agent/waiting_human → resume → context
```

以 `context` 返回的 `worker_cycle` 为准：Worker action 统一使用 `waiting_agent → resume → context`；`resume_mode` 区分宿主执行的 Worker 和用户决定，`requires_reconcile` 只用于兼容恢复已经存在的中断任务。只有 `match_found` 为 `true` 时，才能从 `skills` 选择 Worker；`registered_skill_count` 只是流程库规模，不是可用候选数量。没有匹配 Worker 时，只有用户明确同意且任务属于低风险只读分析，才能使用 `agent_fallback`；该结果必须标记为 Agent 直接执行。

以下门槛只适用于选择 Worker 的分支；`request_human`、`complete` 和澄清分支不读取 Worker：

- 没有有效的工作区准备结果；
- 没有 `mission_id`；
- 没有读取当前 mission 的 context；
- 没有从 `context` 返回的候选 Worker 中作出选择；
- 没有执行 `prepare-skill`；
- 上一个 Worker 仍在等待外部结果或用户决定；
- 当前仍存在未处理的 pending action。

不得直接把 Worker Skill 当作用户请求的入口。不得因为 Worker 名称看起来匹配，就跳过 context 或直接读取 Worker 的脚本、README、MCP 说明和其他实现文件。不得在一个结果尚未返回时调用第二个 Worker。Runtime 已报告 Worker 完成前不得向用户宣称任务完成；已完成的 Worker 不要重复调用 `resume`。已完成的 mission 不能继续发 action；目标变化时创建新的 mission。

如果 bootstrap 失败，停止并说明流程库不可用；如果 `context` 的 `match_found` 为 `false`，先读取 `coverage_diagnostic.user_message`，向用户明确说明任务尚未执行以及原因。若 `fallback_available` 为 `true`，再询问用户是否允许低风险只读的 Agent 直接执行；得到明确同意后才能使用 `agent_fallback`。`no_registered_worker` 表示当前环境没有登记 Worker；`no_matching_worker` 表示环境中有已登记 Worker，但没有能力被当前目标明确匹配，不能说成“任务执行失败”。如果 Worker 缺少条件或执行失败，将问题返回 LabOntology，不自行补造条件或静默重试。不要把 `registered_skill_count` 当作可用候选数量，也不要把脚本存在与否单独当作 Worker 可用性的判断。

## Runtime branches and boundaries

- `match_found=false`：先说明任务尚未开始；低风险只读任务可在用户同意后使用 `agent_fallback`，其他情况只询问一个能缩小范围的澄清问题。
- `request_human`：需要用户补充事实、确认或拒绝时使用；等待期间不选择第二个 Worker，用户回答后用 `resume` 回到 `context`。
- `agent_fallback`：仅用于用户已明确同意的低风险只读工作；结果来源固定记录为 `agent_native`，不能冒充标准 Worker 结果。
- `complete`：结果和产物已由 Runtime 记录且没有未追踪输出时使用；不能用它绕过 Worker、审批或输入条件。
- 用户提供的表格、样品说明或其他文件通过 mission input 传入（`--input-artifact`），不是 graph 或 Skill 缓存；Worker 产物必须由 Runtime 记录后才能汇报。
- `SKILL.md` 是每个 Worker 的唯一执行合同。带有脚本的 Worker 仍先按文档执行；脚本只在文档明确允许、输入输出合同一致且宿主 Agent 明确选择时作为可选加速步骤。LabOntology 不会因为发现脚本就自动启动子进程。
- 同一目标的后续对话复用原 `mission_id`；mission 已完成或目标实质变化时，不要继续复用旧 mission。

## Conversation-first workflow

先判断用户是在：

- 准备或规划实验；
- 检查条件或查看进度；
- 维护、修复或改进实验流程库；
- 请求一个实验相关动作。

用用户的自然语言作为 mission 目标，先说明当前可用的流程、缺少的条件、下一步和所需确认。用户描述了实验顺序时，先整理成简短的候选步骤并请求确认；不要仅因为多个 Worker 属于同一实验集合，就擅自拼成完整流程。

## Workflow improvement

LabOntology 负责根据重复失败、缺少条件或用户纠正推动实验流程的自我演化和自我改进。先只读检查 `suggest-maintenance`，经明确检查后再用 `maintain-graph` 应用低风险的知识或关系修改；修改前后只保留一个简单的最新备份，必要时用 `restore-backup` 恢复。成功任务还会写入少量紧凑的 `experiences.jsonl`，在后续 `context` 中作为最多三条历史提示；历史提示只能帮助 Agent 回忆可复用做法，不能改变 Worker 匹配、输入/能力门槛、安全审批、完成条件或 graph。失败仍记录在 `feedback.jsonl`，不得因为一次普通失败就直接改 graph。

## User-facing response contract

每次回复先给实验结果，再给唯一最有用的下一步：

- **Ready:** 说明可用流程和可以继续的下一步。
- **Missing condition:** 只指出缺少的材料、条件、能力或证据。
- **Waiting for approval:** 说明拟执行的动作、影响和需要的确认。
- **Paused task:** 说明任务当前状态和将恢复的内容，不暗示设备动作会自动重做。
- **Library problem:** 先说明“实验流程库需要更新”，再给出必要的技术信息。

不要主动展示内部路径、命令、原始异常或实现细节；用户明确要求且路径属于当前任务已登记产物时，可以从 `context` 的 `artifact_records` 返回该路径，不得猜测、拼接或读取其他 mission 的路径。若有多个任务或流程匹配，只提出一个聚焦的澄清问题。

## Safety boundary

不得自动执行设备相关或高影响动作，不得补造缺失证据，不得绕过安全、审批、授权或输入条件。只读检查也要按照当前任务的授权边界处理。
