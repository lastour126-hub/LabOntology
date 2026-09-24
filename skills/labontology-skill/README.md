# LabOntology 使用说明

`labontology` 是一个独立的 Skill，内部包含两个模块：

- Creator：发现当前环境中可见的标准 Skill 目录，并维护工作区缓存。
- Runtime：管理任务状态、证据、执行、恢复和审批。

LabOntology 是实验任务和实验流程库维护的统一入口。其他实验 Skill 作为 Worker，由 LabOntology 根据任务选择，不直接响应用户的实验请求。普通写作、表格、图片、演示文稿和一般文件生成不进入 LabOntology，除非它们属于实验任务的一部分。重复失败或用户纠正产生的反馈，可在现有安全边界内用于维护流程图谱。

公开入口保留这些边界，同时简化日常使用；它不会导入历史遗留的外部 Skill。

## 对话中使用

直接用自然语言说明实验目标，例如：

- “准备做样品处理实验，开始前需要检查什么？”
- “这一步所需的材料和设备是否已经就绪？”
- “昨天暂停的实验现在到哪一步了？”

Agent 会在内部选择流程，核对已有规程与任务状态，只询问缺少的信息，并说明已具备的条件、待处理的问题和下一步。未经必要审批，不会启动设备动作。

面向实验人员的回复先说明结果，再说明下一步或唯一缺少的条件。缓存路径、Suite ID 等技术信息仅在维护或排查流程库时出现。

如果用户在对话中描述实验顺序，Agent 会整理出简短的候选流程，请用户确认顺序。确认后的步骤可作为流程证据；同一项目中的其他 Skill 不会因此被自动拼成完整规程。

典型回复：

- “准备条件已检查完成；目前只缺少离心机可用性确认。”
- “我找到昨天暂停的任务，已保留已有结果。是否继续下一步？”
- “这是只读检查，不会改变设备状态。确认后我再执行。”
- “实验流程库需要更新；我会只同步这次任务相关的步骤。”

## 安装与首次使用

将 LabOntology 和实验 Worker Skill 分别作为包含 `SKILL.md` 的目录，放到宿主环境的常规 Skill 位置。用户只需用自然语言描述实验目标。

首次收到实验请求时，LabOntology 会发现可见的标准 Skill 目录，并自动建立工作区缓存。后续请求复用缓存；Worker Skill 新增、变更或移除时会触发同步。用户无需点名调用 LabOntology，也无需提供 Skill 路径。

Worker Skill 的源文件对 LabOntology 来说是只读输入；LabOntology 不会改写这些 Skill，也不会向其中添加配置。

发布包已内嵌 PyYAML 6.0.3，正常使用无需单独安装。

## 工作区图谱与缓存

每个实验工作区使用一个名为 `labontology_workspace_cache` 的缓存，其中的单一图谱包含所有可见的 Worker Skill。Agent 在规划前准备工作区：新增或变更的 Skill 源文件更新同一图谱；表格、样品说明等任务材料则作为任务输入，不会触发流程库缓存重建。

维护人员可以显式查看自动发现结果：

```powershell
python scripts/labontology.py bootstrap
```

默认情况下，`bootstrap` 使用当前目录作为工作区，并发现可见的 Skill 位置。从本目录运行时，当前目录就是工作区；如果需要使用上级项目目录，请显式传入 `--workspace`。从 `.agent/skills`、`.claude/skills` 等宿主目录内运行时，程序可自动定位其所属项目。

维护或排查时，可以同步流程库并定位已有缓存：

```powershell
python scripts/labontology.py sync --skill-root ..\..\..\FduSkills --workspace ..\..\.. --suite-id suite:fdu
python scripts/labontology.py resolve-cache --skill-root ..\..\..\FduSkills --workspace ..\..\.. --suite-id suite:fdu
```

## FDU 只读示例

以下命令均从本目录运行：

```powershell
python scripts/labontology.py sync --skill-root ..\..\..\FduSkills --suite-id suite:fdu --workspace ..\..\..
python scripts/labontology.py inspect --cache-dir ..\..\..\labontology_workspace_cache
python scripts/labontology.py run --cache-dir ..\..\..\labontology_workspace_cache --suite-id suite:fdu --goal "检查实验步骤所需资源是否齐全"
python scripts/labontology.py status --cache-dir ..\..\..\labontology_workspace_cache --mission-id <返回的任务ID>
```

`sync` 返回工作区缓存位置，并确认图谱有效。`inspect` 报告各 Suite、可用能力、图谱规模和源文件是否最新。`run` 创建任务并返回 `mission_id` 及 Runtime 上下文；它本身不会执行实验动作。可用 `--input-artifact <名称>=<路径>` 附加任务表格等输入。`status` 和 `resume` 用于读取或继续保存在 `<cache-dir>/runs` 下的任务记录。

面向模型的 Runtime 协议见 [references/runtime-protocol.md](references/runtime-protocol.md)，其中规定任务状态、Worker 读取门槛、单动作规则、结果回传及失败处理。本 README 主要说明使用、维护和排查方式。

生成的计划、规程文件、提交记录等 Agent 产物保存在 `<cache-dir>/runs/<mission-id>/artifacts` 下。表格等输入文件仅在原位置引用，不会被移动。

所有 Skill 动作都通过同一个 `act` 入口。一次决策可以选择一个文档 Worker、请求用户回答、在获得明确同意后执行低风险只读的 Agent 兜底分析，或在 Runtime 检查后完成任务。选中的 Worker 或兜底分支进入 `waiting_agent`；宿主 Agent 按准备好的 `SKILL.md` 执行 Worker，或进行已获同意的本机分析，再通过 `resume` 回传真实结果。兜底结果标记为 `agent_native`，不会冒充标准 Worker 结果。

如果 Worker 文档声明了可选脚本，宿主可在核对输入输出后显式调用。LabOntology 不会仅因脚本存在就自动启动本地进程。收到用户回答后，`context` 会返回 `replan_required=true`，Agent 必须重新评估并选择 Worker、使用已获同意的兜底方式，或提出下一个明确问题；Runtime 不接受直接完成。若 `match_found=false`，Agent 会说明原因，且只对常规只读任务提出兜底建议。已存在所声明输入材料的 Worker 可能在关键词不匹配时仍作为候选出现，因此决策前仍需核对 Worker 卡片。

Agent 在发出动作前，将用户确认记录在决策评估中。设备相关或高影响动作、缺少输入或证据、指令来源不可用、授权范围不明等情况，仍走 Runtime 的审批路径。高级 `resume`、`reconcile` 和由 Agent 主导的 Runtime 操作可使用 `python scripts/runtime.py`。

## 轻量级自维护

Runtime 反馈以可观察的 JSONL 事件保存，不记录隐藏推理。重复出现条件缺失或执行失败时，可先只读查看维护建议，不改动图谱：

```powershell
python scripts/labontology.py suggest-maintenance --cache-dir <cache-dir>
```

明确检查后，才应用低风险的元数据或关系补丁：

```powershell
python scripts/labontology.py maintain-graph --cache-dir <cache-dir> --patch-file patch.json --reason "补充重复缺失的前置条件"
```

图谱替换时会在 `<cache-dir>/.backup/` 保留一份最近的备份；不维护多版本本体。需要恢复时显式执行：

```powershell
python scripts/labontology.py restore-backup --cache-dir <cache-dir>
```

成功任务还会在 `<cache-dir>/experiences.jsonl` 留下一条简要记录。后续 `context` 最多返回三条相似记录，字段为 `historical_experiences`。它们只供 Agent 参考，不能直接选择 Worker、补足缺失输入、绕过安全检查或修改图谱。失败任务仍记录在 `feedback.jsonl`。
