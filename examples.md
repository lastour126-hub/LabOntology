# LabOntology 使用示例

下面是六个可以直接尝试的完整案例。每个案例都从输入开始，经过多个 Skill 处理，最后形成报告、数据表、图或结构文件。六个案例彼此独立，可以任选一个开始。本页使用的实验 Skill 均通过 SCPHub 获取。

## 首次使用

在 Agent 中打开要使用的项目，先安装 LabOntology：

```text
请帮我安装 LabOntology。获取这个 Skill 目录，放到当前项目可识别的技能目录中。
https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill
```

安装完成后，可以手动输入：

```text
请初始化当前项目的 LabOntology。
```

也可以直接开始下面的实验任务，第一次使用时会自动初始化。同一项目完成初始化后，后续任务不用重复操作。

## 选一个实验开始

六个案例分别覆盖小分子分析、先导分子筛选、蛋白结构评估、物理模拟、合成生物学模拟和晶体结构分析。每个案例都会展示 LabOntology 如何保存输入、连接步骤、记录结果，并在中间结果出现问题时保留原因。

为了方便理解，六个案例分别突出一种使用方式。它们彼此独立，不需要按顺序完成；下面的“场景侧重点”是帮助选择案例，不会改变实验本身的执行流程。

| 场景侧重点 | 对应案例 | 主要看什么 |
|---|---|---|
| 实验能力选择 | 小分子结构校验、性质计算与可视化 | 根据输入和目标选择合适的 Skill，并把无效结构挡在后续步骤之前。 |
| 按实验顺序推进 | 先导分子生成、结构筛选与 ADMET 初筛 | 按“生成—校验—优化—初筛”的顺序传递结果，不跳过中间检查。 |
| 实验局部重规划 | 蛋白结构、口袋与可成药性评估 | 结构质量或口袋结果不理想时，保留已完成结果，调整后面的评估并继续完成报告。 |
| 跨长上下文能力 | 阻尼振子频谱分析与方程校验 | 在多步计算中保持参数、方程、模拟数据和验证结果之间的对应关系。 |
| 跨对话能力 | 代谢条件影响合成基因开关 | 让代谢模型、动态模拟和独立复核的结果在后续对话中仍能接着使用。 |
| 经验积累与自我改进 | 晶体结构分析与材料参数整理 | 把单位、常数、计算假设和检查结果留下来，方便后续换数据时继续复用。 |

### 1. 实验能力选择：小分子结构校验、性质计算与可视化

#### 安装 Skill

```text
请安装下面三个 Skill：
- smiles-validation：https://scphub.intern-ai.org.cn/skill/1032
- molecule-visualization：https://scphub.intern-ai.org.cn/skill/918
- admet-prediction：https://scphub.intern-ai.org.cn/skill/739
```

#### 推荐提示词

```text
请检查下面 4 个 SMILES，并完成一次完整的小分子结构分析：

| name | SMILES |
|---|---|
| aspirin | CC(=O)Oc1ccccc1C(=O)O |
| caffeine | Cn1c(=O)c2c(ncn2C)n(C)c1=O |
| ibuprofen | CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O |
| broken_candidate | CC(=O)Oc1ccccc1C(=O |

先使用 smiles-validation 逐条检查结构。无效结构不得进入后续步骤；只对有效结构使用 molecule-visualization 生成二维结构图和分子网格，再使用 admet-prediction 计算基础性质。

请最后生成一份完整报告，至少包括：原始输入、每条结构的校验结果、无效结构的跳过原因、有效结构的性质表、二维结构图、分子网格和生成文件清单。说明哪些结构进入最终报告，不要根据结构推断药效。
```

#### 这个案例中 LabOntology 做什么

它会把每个 SMILES 的校验结果和后续文件对应起来。错误结构会在流程中被标记并跳过，后续只处理通过校验的结构；如果某个结构的图或性质计算失败，可以从该结构重新执行，不需要重复处理全部输入。

### 2. 按实验顺序推进：先导分子生成、结构筛选与 ADMET 初筛

#### 安装 Skill

```text
请安装下面四个 Skill：
- denovo-design：https://scphub.intern-ai.org.cn/skill/798
- smiles-validation：https://scphub.intern-ai.org.cn/skill/1032
- molecular-optimization：https://scphub.intern-ai.org.cn/skill/916
- admet-prediction：https://scphub.intern-ai.org.cn/skill/739
```

#### 推荐提示词

```text
请以阿司匹林作为教学用先导分子，完成一次从候选生成到 ADMET 初筛的完整计算流程。

先导分子 SMILES：CC(=O)Oc1ccccc1C(=O)O

先使用 denovo-design 按 R-group 和 bioisostere 两种思路各生成 4 个候选。然后使用 smiles-validation 逐一检查，只保留完整、可解析、单一分子且不含 `*` 连接点的结构。对通过检查的候选使用 molecular-optimization 做一轮约束优化，目标为 MW<500、LogP<5、QED>0.5；最后使用 admet-prediction 对优化后的结构做口服性质和 ADMET 初筛。

请最终输出：排序后的候选短名单、全部候选的淘汰表、结构校验结果、优化前后性质对比、ADMET 结果和一份总结报告。记录每个候选是如何从生成结果进入下一步的，不要把模型预测写成实验结果或药效结论。
```

#### 这个案例中 LabOntology 做什么

它会区分“生成过的候选”“通过结构检查的候选”“进入优化的候选”和“进入 ADMET 初筛的候选”。这样最终短名单可以追溯到原始生成结果，某个候选被淘汰时也能找到具体原因。

### 3. 实验局部重规划：蛋白结构、口袋与可成药性评估

这个案例需要一个可以读取的蛋白结构文件，例如 `target.pdb`，不需要额外的对接程序。

#### 安装 Skill

```text
请安装下面三个 Skill：
- pocket-detection：https://scphub.intern-ai.org.cn/skill/958
- drug-design：https://scphub.intern-ai.org.cn/skill/804
- molecule-visualization：https://scphub.intern-ai.org.cn/skill/918
```

#### 推荐提示词

```text
我有一个蛋白结构文件 target.pdb。请完成一份完整的蛋白结构与口袋评估报告。

先使用 pocket-detection 检查 PDB 文件，识别候选口袋，保存口袋坐标、评分、结构检查结果和可视化文件。再使用 drug-design 完成结构质量检查、口袋可成药性启发式评估和汇总报告。最后使用 molecule-visualization 生成蛋白结构图、口袋位置图和一个可交互的 3D 查看页面。

最终结果至少包括：输入结构基本信息、候选口袋表、每个口袋的评估依据、图片或 3D 页面、Markdown 或 JSON 汇总报告，以及可以从任一步骤重新执行的命令。若结构质量较差或口袋不适合继续分析，要把原因和影响写进报告，但仍要完成本次计算评估。不要把启发式评分写成结合亲和力，也不要生成没有计算依据的 pose 或实验结论。
```

#### 这个案例中 LabOntology 做什么

它会把蛋白结构检查、口袋识别、可成药性评估和可视化结果连接起来。即使口袋评分不理想，任务也会保留这个结论和判断依据，而不是把失败结果隐藏掉。

### 4. 跨长上下文能力：阻尼振子频谱分析与方程校验

这是一个不需要外部数据的物理模拟案例。输入是明确的模型参数，输出是模拟数据、频谱结果、ODE 结果和一致性报告。

#### 安装 Skill

```text
请安装下面三个 Skill：
- sympy：https://scphub.intern-ai.org.cn/skill/1048
- spectral-analysis：https://scphub.intern-ai.org.cn/skill/1036
- ode-solver：https://scphub.intern-ai.org.cn/skill/931
```

#### 推荐提示词

```text
请使用 LabOntology、sympy、spectral-analysis 和 ode-solver 完成一个可重跑的阻尼振子教学模拟，不调用外部 API，也不要把模拟数据写成实测数据。

参数为：m=0.5 kg，k=200 N/m，c=1 N·s/m，x0=0.01 m，v0=0，采样率 200 Hz，时长 8 s。先根据解析解生成无噪声模拟位移序列，并标注 data_origin=simulated。

第一步使用 sympy 整理 m*x''+c*x'+k*x=0，并推导自然频率、阻尼比和阻尼频率。第二步使用 spectral-analysis，输出采样间隔、FFT 分辨率、主频、功率谱和振幅包络。第三步使用 ode-solver 数值求解方程，在同一时间网格上对齐结果，输出自然频率、阻尼频率、残差和收敛检查。

请保存模拟数据、频谱结果、ODE 结果、图、输入输出关系和重跑命令，最后合成一份一致性报告。报告必须包含方程推导、理论频率、频谱主峰、ODE 结果、残差、误差解释和通过/不通过的检查结论。允许从频谱阶段或 ODE 阶段单独重跑；只有这些结果齐全，才算本次模拟完成。
```

#### 这个案例中 LabOntology 做什么

它会记录理论方程、模拟数据、频谱分析和数值求解之间的关系。频谱主峰和理论频率不一致时，可以查看是参数、采样率还是计算步骤导致的，并从对应步骤重新执行。

### 5. 跨对话能力：代谢条件影响合成基因开关

这是一个教学用的合成生物学模拟，不代表真实细胞实验。它用一个小型代谢模型产生条件参数，再把参数传给基因开关动力学模型。

#### 安装 Skill

```text
请安装下面三个 Skill：
- cobrapy：https://scphub.intern-ai.org.cn/skill/778
- synthetic-biology：https://scphub.intern-ai.org.cn/skill/1049
- ode-solver：https://scphub.intern-ai.org.cn/skill/931
```

#### 推荐提示词

```text
请完成一个代谢条件影响合成基因 toggle switch 的教学模拟。所有结果必须标注为 simulated_toy_model，不代表真实大肠杆菌生理或实验数据；不要调用外部 API。

先使用 cobrapy 构建最小代谢模型，只包含葡萄糖交换、转运、糖酵解生成丙酮酸和 pseudo-biomass 反应。明确写出教学用产率：葡萄糖摄取为 mmol gDW^-1 h^-1，假设 0.1 gDW/mmol glucose；模型中用 1 glucose -> 2 pyruvate、20 pyruvate -> 1 pseudo-growth flux 表达该假设。分别设置碳源充足和碳源受限两个条件，输出 SBML、条件表和 FBA 验证结果。

再使用 synthetic-biology，把两种条件的 pseudo-growth flux 作为 toggle switch 的生长稀释参数 gamma。每个条件从 A 高/B 低和 A 低/B 高两种初始状态开始积分，比较最终状态和轨迹。最后使用 ode-solver 对至少一个条件重新积分，比较两种求解结果和残差。不要预设一定存在双稳态，按计算结果判断。

请记录 cobrapy 到 synthetic-biology 的输入输出关系，保存模型、表格、轨迹、图、JSON、中文总结和从 FBA 或 ODE 阶段单独重跑的方法。最终报告必须同时给出两个碳源条件的 FBA 结果、toggle switch 轨迹、独立 ODE 复核、残差和差异解释。只有 FBA、动态模拟、独立复核和最终总结都生成，才算本次教学实验完成。
```

#### 这个案例中 LabOntology 做什么

它会记录代谢模型输出的参数是怎样传给基因开关模型的，并把两个条件下的轨迹和独立复核结果放在同一条任务链中。模型中的产率、单位和假设也会随结果一起保存，避免把教学参数误当成真实生理参数。

### 6. 经验积累与自我改进：晶体结构分析与材料参数整理

这个案例可以直接使用提示词中的理想化硅晶体参数，不需要额外准备结构文件。

#### 安装 Skill

```text
请安装下面三个 Skill：
- pymatgen：https://scphub.intern-ai.org.cn/skill/974
- physics-databases：https://scphub.intern-ai.org.cn/skill/951
- sympy：https://scphub.intern-ai.org.cn/skill/1048
```

#### 推荐提示词

```text
请做一个教学用晶体结构分析，不调用外部 API。先用 pymatgen 根据下面的硅晶体参数构造结构：

- 晶格常数 a=b=c=5.431 Å
- 晶格角 α=β=γ=90°
- 结构类型：diamond cubic
- 元素：Si

请输出晶胞体积、密度、元素组成、晶体对称性、空间群和结构文件。然后用 physics-databases 或本地权威常数来源核对长度、质量和密度计算中使用的单位换算与常数，再用 sympy 检查密度公式、晶胞中原子数和单位是否一致。

请把结构输入、单位换算、计算结果和检查结论分开保存。最终交付物至少包括 CIF 或 POSCAR、结构分析报告、密度和组成表、对称性与空间群结果、单位审计结果，以及密度公式和原子数检查结果。说明这是根据理想化晶格参数得到的计算结果，不是对真实样品的表征结果。不能只输出一个结构文件而没有分析结论。
```

#### 这个案例中 LabOntology 做什么

它会把晶体结构、物理常数、单位换算、密度计算和公式检查关联起来。以后把理想化参数换成 CIF 文件时，只需替换结构输入，仍然可以沿用后面的分析和验证步骤。

## 一个案例什么时候算完成

每个案例都应同时满足：

- 输入已经检查，并被后续步骤实际使用；
- 案例中列出的 Skill 都已经执行；
- 每一步的输入、输出和验证结果能够对应起来；
- 失败或不理想的结果有明确说明，没有用假结果补齐；
- 最终报告、数据表、图或结构文件已经生成；
- 能够根据任务记录从中间步骤重新执行。

如果只得到了一份方案、只完成了前置检查，或者中途缺少条件而没有最终结果，就不要把这个案例标记为完成。
