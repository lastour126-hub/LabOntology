# LabOntology 使用示例

本页用六个独立的实验任务说明 LabOntology 的用法。LabOntology 负责选择 Skill、安排步骤和记录任务状态；公开资料查询与具体分析由相应 Skill 完成。案例中的目标和条件已经写在提示词里，不需要准备示例数据文件。所列 Skill 来自 [Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills)、[Agent Almanac](https://github.com/pjt222/agent-almanac/tree/main/skills) 和 [Drug Discovery Agent Skills](https://github.com/K-Dense-AI/drug-discovery-agent-skills/tree/main/skills)。

## 首次使用

在 Agent 中打开实验项目，确认本机有 Python 3.11 或更新版本，并能访问公开网站。先发送：

```text
请帮我安装 LabOntology。只获取下面这个完整的 Skill 目录，放到当前项目可识别的技能目录中，目录名为 labontology。安装后请确认可以使用。
https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill
```

然后选一个场景，发送该场景的“安装 Skill”内容。安装后未识别到 Skill 时，重新开启对话。

实验环境搭好后，可以说“请初始化当前项目的 LabOntology”；也可以直接提交任务，由首次实验请求自动初始化。同一项目不必重复初始化。接下来复制场景中的提问即可。

## 选一个场景开始

下面六个场景彼此独立，分别展示 LabOntology 如何组织多个 Skill、落实既定步骤、处理局部返工，以及在长对话、跨对话和同类实验中保持任务记录可用。每个场景都可单独选用。

安装列表是该场景可能用到的能力，不表示每项都会在每轮对话中执行。在线查询使用可直接访问的公开来源；没有真实测量数据时，只讨论实验方案和判断依据，不给出虚构的实验结果。

### 1. 能力选择：阿司匹林合成后的纯化与鉴定方案

安装 Skill：

```text
请把以下 Skill 的完整目录安装到当前项目，并确认都已可用：
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/database-lookup
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/paper-lookup
https://github.com/pjt222/agent-almanac/tree/main/skills/plan-spectroscopic-analysis
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/analytical-method-validation
```

提问示例：

```text
我准备以水杨酸和乙酸酐合成阿司匹林，需要一套产物纯化与鉴定方案。请先查询原料、产物和可能残留物的公开物性与安全资料，再找可核对来源的实验方法，比较重结晶、洗涤等纯化思路。随后分别考虑薄层色谱、熔点、红外和 HPLC 能回答什么问题，选择能识别未反应水杨酸的检测组合，并列出各项检测需要的对照与判定依据。请把资料来源和待确认的仪器条件分开写；不要把文献中的收率或纯度写成这次实验的结果。
```

LabOntology 先判断需要哪些能力，再组织物性查询、文献核对、纯化方案比较和鉴定方法选择。它会记录各步依据、检测手段的局限和待确认条件；缺少关键仪器信息时，不直接认定某项检测已经可做。

### 2. 按固定顺序推进：APOE 位点的 PCR/Sanger 验证规划

安装 Skill：

```text
请把以下 Skill 的完整目录安装到当前项目，并确认都已可用：
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/database-lookup
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/genomic-coordinates
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/paper-lookup
```

提问示例：

```text
请为 APOE 的 rs7412 位点规划 PCR 扩增后用 Sanger 测序核对的流程。以 GRCh38 为参考，先从公开数据库确认位点、等位基因和序列方向，再核对坐标约定、参考序列及目标位点附近是否有可能影响引物结合的已知变异。最后根据可核实的资料列出扩增区选择、双向测序、阴阳性对照、特异性核查和读段质量检查要点。每一步注明依赖前一步的哪项信息；若参考版本或方向不能确认，就停在该步。这里只规划引物筛选要求，不要凭空给出引物序列，也不要推断任何人的基因型。
```

LabOntology 把任务按“位点检索—坐标核对—引物筛选要求—结果判读条件”的依赖顺序记录。前置参考信息没有核实，后续步骤就保持待完成，避免把未经确认的坐标带入实验方案。

### 3. 局部重规划：检测设备变化后的 HPLC 方法调整

安装 Skill：

```text
请把以下 Skill 的完整目录安装到当前项目，并确认都已可用：
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/database-lookup
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/paper-lookup
https://github.com/pjt222/agent-almanac/tree/main/skills/develop-hplc-method
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/analytical-method-validation
```

第一次提问：

```text
请为茶饮料中的咖啡因与可可碱建立一套 LC-MS/MS 分析方法的初步方案，目标是在同一次分析中区分并定量这两种成分。先核对化合物性质和已有分离方法，再说明样品前处理、空白与标准品、色谱柱及流动相选择、检测器适配条件和定性依据，并列出专属性、线性、重复性等验证项目。没有样品或仪器数据时，只给出候选条件与待确认事项，不要编造色谱图或验证结果。
```

条件变化后继续说：

```text
这次实验无法使用质谱检测器，只有 HPLC-UV。请接着原任务调整方案：先判断已核实的化合物资料、样品前处理和分离依据哪些仍可用，再重新评估两种成分的 UV 响应、茶饮料基质干扰、峰身份确认办法和验证项目。请列出需要补做的对照；不要沿用之前依赖质谱的定性结论。
```

LabOntology 保留仍然适用的资料和判断，只把受检测器变化影响的步骤重新安排。原方案和修改原因都会留在同一任务中，未完成的方法验证不会被标为通过。

### 4. 跨长上下文：酵母发酵实验的条件逐轮收紧

安装 Skill：

```text
请把以下 Skill 的完整目录安装到当前项目，并确认都已可用：
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/paper-lookup
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/hypothesis-generation
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/scientific-critical-thinking
```

第一轮提问：

```text
我想比较温度和初始葡萄糖浓度对酿酒酵母发酵的影响。请根据公开资料提出可检验的假设，规划两因素组合、对照、独立发酵重复和取样时间点，并说明如何避免把同一瓶的多次读数当成独立重复。把发酵速率、生物量与乙醇产量分别对应到可用的测量方法；先保存研究目标、变量和待确认的设备条件，不要假定实验已经做完。
```

后续可分两轮补充：

```text
补充限制：目前只有分光光度计和 pH 计，没有气相色谱或乙醇测定试剂。请沿用前面确定的分组和对照，重新检查哪些指标确实能测，哪些结论需要暂缓。
```

```text
请把现在可执行的分组、取样、记录字段和可测指标整理成一页实验方案，同时单独列出因缺少乙醇测定条件而无法回答的问题。不要把 OD 或 pH 变化直接等同于乙醇产量。
```

LabOntology 在每轮追问前找回已确定的对象、变量、对照和设备限制。后续条件只更新受影响的部分；即使对话很长，也不会把已排除的乙醇测定重新写进可执行方案。

### 5. 跨对话：接续碱性磷酸酶活性测定方案

安装 Skill：

```text
请把以下 Skill 的完整目录安装到当前项目，并确认都已可用：
https://github.com/K-Dense-AI/drug-discovery-agent-skills/tree/main/skills/uniprot-rcsb
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/paper-lookup
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/analytical-method-validation
```

第一个对话：

```text
请为大肠杆菌 PhoA 重组碱性磷酸酶的 pNPP 显色活性测定拟定方案，计划用 405 nm 读数。先核对蛋白身份与可查到的注释，再找可核对的公开方法，整理底物空白、酶空白、阳性对照、时间点、反应线性范围和酶活计算所需字段。未知的蛋白构建体、反应体积和读数方式请单独列出。把方案和待确认条件保存在当前项目；我还没有测量数据。
```

同一项目的新对话：

```text
请接着上次的碱性磷酸酶活性测定任务。现在确认使用微孔板读数，请先找回原来的酶、底物、波长、对照和待确认条件，再检查反应体积、有效光程、校准方式和酶活计算哪些需要调整。只更新方案，不要凭空生成酶活测定结果。
```

LabOntology 通过项目中的任务记录接回已确认的条件，而不是要求重新叙述整套方案。若有多个相近任务，会先核对是哪一个；若原任务已结束，则建立关联的后续任务。

### 6. 经验积累与自我改进：Bradford 测定的稀释倍数核对

安装 Skill：

```text
请把以下 Skill 的完整目录安装到当前项目，并确认都已可用：
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/paper-lookup
https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/analytical-method-validation
```

第一次提问：

```text
请根据公开方法为 Bradford 蛋白测定整理一份实验与结果记录模板。包括试剂和样品缓冲液的适配检查、空白、标准曲线、独立重复、未知样品的连续稀释记录、超出曲线范围时如何重测，以及稀释后浓度和原样浓度各自的报告字段。请标出需要我确认的试剂和仪器条件；现在没有吸光度数据，不要计算样品浓度。
```

如果复核时发现模板遗漏，可以反馈：

```text
我发现刚才的模板没有明确区分“上机测得的稀释后浓度”和“按两次稀释的总倍数回算的原样浓度”，容易导致结果返工。请修正模板，并记录这次遗漏；以后开始同类测定时提醒我先核对每一步稀释方向、总倍数和单位。
```

下一次同类任务可以说：“我要再做一批 Bradford 测定。请先检查实验与结果记录模板，然后告诉我开始前有哪些容易遗漏的条件。”

LabOntology 保存已确认的返工原因，在相似任务开始时作为检查提醒。提醒不等于自动修改 Skill 或替代本次数据核对；当前条件仍需重新确认。
