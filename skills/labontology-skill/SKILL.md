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

LabOntology 是实验任务和实验流程库维护请求的统一入口，也是当前任务的持续监督者。用户只需要描述目标、材料和限制条件，不需要知道内部命令或如何组合能力，也不需要手动调用其他 Skill。

只要请求涉及实验、样品、试剂、仪器、设备、协议、分析、准备检查、暂停恢复、流程库维护或能力选择，都必须先进入 LabOntology。每个新的实验请求、后续追问、失败恢复和下一步操作，都必须重新回到 LabOntology。

普通写作、表格、图片、PPT 和一般文件处理保持在实验流程之外，不属于 LabOntology 实验入口。不要因为普通任务包含文件、分析或生成结果就启动 LabOntology。普通任务结束后，下一条实验目标重新判断。

## Entry protocol

在回答或调用其他能力前，按以下顺序处理当前实验请求：

1. 运行 `bootstrap`，准备或复用当前工作区和流程库。
2. 为新目标创建 `mission`；同一任务的追问、恢复和失败处理复用原 `mission_id`。
3. 读取 `context`。从返回的 `skills` 中选择一个能覆盖当前目标的 Skill。候选卡片只是索引，必须再读取完整 `SKILL.md`；不能仅凭名称或输入文件匹配做决定。要同时核对候选描述、声明的 `outputs`、输入条件和文档内容。
4. 运行 `prepare-skill`，记录本次读取的 Skill 文档和摘要。
5. 生成一个边界清晰的动作决策，一次只发出一个动作。动作可以是 `skill`、`request_human`、`agent_fallback` 或 `complete`。
6. `act` 后读取 Runtime 状态。选择 Skill 后通常进入 `waiting_agent`，宿主 Agent 按已读取的文档执行；文档中声明的脚本只是可选加速步骤，不会自动启动。
7. 宿主把真实结果、失败原因和产物通过 `resume` 返回，然后重新读取 `context`。中断的动作先通过 `reconcile` 处理，再继续规划。
8. 只有结果已经由 Runtime 记录并重新出现在 `context` 中，才能向用户汇报或结束任务。

执行状态由 `SkillExecution` 记录。Skill 是唯一的能力单位；SkillFlow 只表示能力之间的参考关系，不直接执行任务。

开始正式处理实验任务前，从本 Skill 根目录运行自带的 `python scripts/labontology.py bootstrap`。先确认脚本存在；不要假设宿主当前目录已经包含 `scripts/`。bootstrap 成功只代表流程库准备完成，不代表实验已经完成。

执行任务时，必须读取并遵循 [references/runtime-protocol.md](references/runtime-protocol.md)。

## Runtime protocol

最小回转顺序是：

```text
bootstrap → mission → context → prepare-skill → act → execution_cycle
                                             └─ waiting_agent/waiting_human → resume → context
```

`context` 返回的 `candidate_count` 是当前可供检查的候选能力数量，`registered_skill_count` 只是流程库规模。候选卡片的 `match_score` 只是排序依据，不是最终能力判断：如果返回 `selection_note`，必须读取完整 Skill 文档确认；不能因为关键词没有直接命中就认定能力不存在。

如果 `coverage_diagnostic.status` 是 `no_registered_skill`，说明当前流程库没有登记能力，任务尚未开始，应提示用户检查安装或初始化。如果是 `candidate_review`，说明能力已经登记，但关键词不足以自动确认，先读取候选文档，再决定选择、澄清或报告缺少条件。不要把这两种情况说成实验执行失败。

低风险、只读任务在没有合适候选时，只有用户明确同意才能使用 `agent_fallback`，并把结果标记为 `agent_native`。这个分支不能绕过输入检查、安全确认或结果记录。

以下检查只适用于发出 `kind=skill` 的分支：

- 已有有效的 bootstrap、`mission_id` 和当前 `context`；
- 从 `context.skills` 中选择了一个具体 Skill；
- 已经读取并准备了完整 Skill 文档；
- Skill 的输入、输出、限制条件和完整文档覆盖当前动作；
- 另一个动作尚未处于等待状态。

如果输入、能力、文档或证据不足，直接说明缺少的条件；不要猜测、静默重试或用本地代码替代选中的 Skill。用户回答后 `replan_required=true`，必须重新读取 `context`，不能直接 `complete`。

## Conversation-first workflow

用用户的自然语言作为 mission 目标。先确认当前可用能力、缺少的材料、下一步动作和必要确认。用户描述多个实验步骤时，先整理为简短的候选步骤并请求确认，不要因为多个 Skill 之间存在参考关系就擅自拼成完整流程。

即使只是根据上一轮结果做解释、排序或汇总，也不能直接凭对话记忆回答，必须至少重新运行 `bootstrap` 和原 mission 的 `context`。任务已完成时，`context` 是报告已登记结果的依据；目标变化时创建新的 mission。

## Workflow improvement

LabOntology 的自我演化是受检查的流程库维护，不是每次失败后的自动改写：

```text
suggest-maintenance → 人工检查 → maintain-graph → 最新备份
                                           └─ 必要时 restore-backup
```

成功任务会写入少量 `experiences.jsonl`，后续 `context` 最多提供三条历史提示。经验只能帮助回忆有效做法，不能改变 Skill 匹配、输入门槛、安全审批、完成条件或 graph。失败记录在 `feedback.jsonl`，不能因为一次普通失败直接修改 graph。

## User-facing response contract

每次回复先给结果，再给唯一最有用的下一步：

- **Ready:** 说明已经找到的能力和可以继续的动作；
- **Missing condition:** 只指出缺少的材料、条件、能力或证据；
- **Waiting for approval:** 说明拟执行的动作、影响和需要的确认；
- **Paused task:** 说明任务停在哪里以及恢复时需要什么；
- **Library problem:** 先说明实验流程库需要更新，再给出必要信息。

不要主动展示内部路径、命令、原始异常或实现细节。普通任务不输出 LabOntology 内部流程说明。

## Safety boundary

不得自动执行设备相关或高影响动作，不得补造缺失证据，不得绕过安全、审批、授权或输入条件。只读检查也要遵守当前任务的授权边界。
