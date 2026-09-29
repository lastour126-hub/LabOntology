<p align="center">
  <img src="assets/labontology-banner.svg" alt="LabOntology：把实验步骤、依据和结果连起来，让任务随时接得上。" width="100%">
</p>

<h2 align="center">把实验步骤、依据和结果连起来，让任务随时接得上。</h2>

<p align="center">
  <a href="#能做什么">能做什么</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="Examples.md">使用示例</a> ·
  <a href="#仓库内容">仓库内容</a>
</p>

<p align="center">中文 · <a href="README.en.md">English</a></p>

实验任务只需要给出实验目标、已有材料和限制条件。LabOntology 会根据任务目标组织所需能力，安排实验步骤，检查每一步的输入、输出和条件；遇到材料缺失、结果异常或条件变化时，会保留已完成的结果，暂停并调整后续步骤。任务也可以在长对话或之后的对话中继续，而不需要重新整理整个实验过程。

## 能做什么

- 开始前，检查实验条件和可用的 Skill，说明还缺什么。
- 进行中，按确认的顺序安排步骤，记下依据和结果。
- 出了问题，保留已完成的部分，调整后面的安排。
- 下次继续，从任务记录接上，并提醒曾经遗漏的条件。

### 一次任务怎么走

你先说明实验目标。LabOntology 会检查现有条件和 Skill 是否够用，再按顺序安排能做的步骤，并记录每一步的结果。遇到缺少条件或异常时，它会说明原因；条件补齐后，可以从已有记录继续。

## 快速开始

先安装 LabOntology，再按任务安装相应的实验 Skill。运行环境需要 Python 3.11 或更新版本。使用示例中的实验 Skill 均通过 [SCPHub](https://scphub.intern-ai.org.cn/) 获取；[使用示例](Examples.md)中列出了六个完整案例和安装方法。

### Codex

在 Codex 对话中输入：

```text
$skill-installer 请从 https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill 安装这个 Skill
```

手动安装时，可将 Skill 目录放到个人的 `~/.agents/skills/labontology/`，或项目的 `.agents/skills/labontology/`。详见 [Codex Skills 文档](https://learn.chatgpt.com/docs/build-skills)。

### Claude Code

在 Claude Code 中输入：

```text
请将 https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill 安装到 ~/.claude/skills/labontology/；只获取这个 Skill 目录。
```

仅在单个项目中使用时，将安装位置改为该项目的 `.claude/skills/labontology/`。详见 [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)。

### 其他 Agent

[Cursor](https://prod.cursor.com/help/customization/skills)、[Gemini CLI](https://geminicli.com/docs/cli/skills/) 和 [OpenCode](https://opencode.ai/docs/skills) 均可从 `.agents/skills/` 发现 Skill。在对应 Agent 中输入：

```text
请将 https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill 安装到 ~/.agents/skills/labontology/；只获取这个 Skill 目录。
```

仅在单个项目中使用时，目标目录改为项目下的 `.agents/skills/labontology/`。安装前先确认没有同名目录；安装后新开会话，或使用 Agent 提供的技能刷新命令。

实验 Skill 也需安装在 Agent 可发现的技能目录下。环境准备好后，可以说“请初始化当前项目的 LabOntology”，也可以直接提出实验任务，由首次使用自动初始化；同一项目不必重复创建。

## 使用示例

示例包括小分子分析、先导分子筛选、ELISA 数据分析、物理模拟、合成生物学模拟和晶体结构分析。数据写在提示词中，或由 Agent 按给定参数生成；每个案例都附有 Skill 安装方法和任务提示词：[查看使用示例](Examples.md)。

## 使用边界

LabOntology 负责组织任务和记录状态，具体实验操作由相应的 Skill 完成；它不直接控制仪器。缺少必要材料、条件或适用的 Skill 时，会说明当前不能继续的原因。设备相关或影响较大的动作不会自动执行。

## 仓库内容

- [SKILL.md](skills/labontology-skill/SKILL.md)：实验任务入口与使用边界。
- [references/](skills/labontology-skill/references/)：本体定义和 [Runtime 协议](skills/labontology-skill/references/runtime-protocol.md)。
- [scripts/](skills/labontology-skill/scripts/)：流程库整理、任务状态与结果记录的实现。
