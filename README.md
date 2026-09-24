# LabOntology

LabOntology 是面向不同实验场景的通用 Skill，负责组织和跟踪实验任务。它根据实验目标、已有材料和限制条件，从当前可用的实验环境中选择匹配的能力，核对执行前提，并将每一步的调用、结果和任务状态记录在一起。具体实验操作由对应的 Skill 完成；LabOntology 根据任务记录判断下一步，不直接控制仪器。

## 快速开始

运行脚本需要 Python 3。本仓库不附带具体实验 Skill（下文称 Worker）；要执行某类实验任务，还需安装覆盖该任务的 Worker。

### Codex

在 Codex 对话中输入：

```text
$skill-installer 请从 https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill 安装这个 Skill
```

也可以将 Skill 目录放到个人的 `~/.agents/skills/labontology/`，或项目的 `.agents/skills/labontology/`。详见 [Codex Skills 文档](https://learn.chatgpt.com/docs/build-skills)。

### Claude Code

在 Claude Code 中输入：

```text
请将 https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill 安装到 ~/.claude/skills/labontology/；只获取这个 Skill 目录。
```

仅在单个项目中使用时，将指令中的安装位置改为该项目的 `.claude/skills/labontology/`。详见 [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)。

### 其他 Agent

[Cursor](https://prod.cursor.com/help/customization/skills)、[Gemini CLI](https://geminicli.com/docs/cli/skills/) 和 [OpenCode](https://opencode.ai/docs/skills) 均可从 `.agents/skills/` 发现 Skill。在对应 Agent 中输入：

```text
请将 https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill 安装到 ~/.agents/skills/labontology/；只获取这个 Skill 目录。
```

仅在单个项目中使用时，目标目录改为项目下的 `.agents/skills/labontology/`。手动安装时，目标目录应命名为 `labontology`，与 `SKILL.md` 中的名称一致；安装前先确认没有同名目录。安装后新开会话，或使用宿主提供的技能刷新命令。Worker 也要安装在宿主可发现的技能目录下。`scripts/_vendor/` 已包含所需的 PyYAML，正常使用无需运行 `pip install`。

## 使用示例

首次初始化、对话中的用法和六个场景的 Skill 安装方法见 [examples.md](examples.md)。

## 仓库内容

- [SKILL.md](skills/labontology-skill/SKILL.md)：实验任务入口与使用边界。
- [references/](skills/labontology-skill/references/)：本体定义和 [Runtime 协议](skills/labontology-skill/references/runtime-protocol.md)。
- [scripts/](skills/labontology-skill/scripts/)：流程库整理、任务状态与结果记录的实现。

想确认本地脚本可运行，可在仓库根目录执行 `python skills/labontology-skill/scripts/labontology.py --help`。日常实验请求直接在对话中提出即可。
