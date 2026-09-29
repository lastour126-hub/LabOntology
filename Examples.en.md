# LabOntology Examples

The six examples below are independent and can be run in any order. All required data is included in the prompts or generated from the stated parameters, so no extra files are needed. The experimental Skills used here can be obtained from SCPHub.

## First use

Open the project used for the experiment, then install LabOntology in the Agent environment:

```text
Please install LabOntology. Get this Skill directory and place it in a Skill directory visible to the current project.
https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill
```

After installation, LabOntology can be initialized explicitly:

```text
Please initialize LabOntology for the current project.
```

Any experiment below can also be started directly. The first experiment task initializes LabOntology automatically. Later tasks in the same project do not need to initialize it again.

## Choose an experiment

The examples cover small-molecule analysis, lead screening, ELISA data analysis, physics simulation, synthetic-biology simulation, and crystal-structure analysis.

| Scenario | Example | What it demonstrates |
|---|---|---|
| Selecting experimental capabilities | Small-molecule validation, property calculation, and visualization | The Agent chooses capabilities based on the goal and filters an invalid structure before later calculations. |
| Following an experimental sequence | Lead generation, structure screening, and ADMET triage | Candidate molecules move through generation, validation, optimization, and screening in order. |
| Local replanning | ELISA standard curve and sample concentration analysis | When S2 is outside the curve range, only the affected part is measured again and recalculated. |
| Long-context continuity | Damped-oscillator spectral analysis and equation checking | Parameters and baseline results remain available after several rounds of added conditions. |
| Cross-conversation continuity | Metabolic conditions affecting a synthetic gene switch | A new conversation restores the old task and recalculates only the changed condition. |
| Experience accumulation and self-improvement | Crystal-structure analysis and material-parameter organization | A missed check found during rework becomes a reminder for later structure analyses. |

### 1. Selecting experimental capabilities: small-molecule validation, property calculation, and visualization

#### Install the Skills

```text
Please install these three Skills:
- smiles-validation: https://scphub.intern-ai.org.cn/skill/1032
- molecule-visualization: https://scphub.intern-ai.org.cn/skill/918
- admet-prediction: https://scphub.intern-ai.org.cn/skill/739
```

#### Suggested prompt

```text
Please check the following four SMILES and complete a small-molecule structure analysis:

| name | SMILES |
|---|---|
| aspirin | CC(=O)Oc1ccccc1C(=O)O |
| caffeine | Cn1c(=O)c2c(ncn2C)n(C)c1=O |
| ibuprofen | CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O |
| broken_candidate | CC(=O)Oc1ccccc1C(=O |

First use smiles-validation to check each structure. An invalid structure must not enter later steps. For valid structures only, use molecule-visualization to generate 2D structure images and molecular grids, then use admet-prediction to calculate basic properties.

Please produce a complete report containing at least: the original inputs, validation results for every structure, the reason each invalid structure was skipped, a property table for valid structures, the 2D images, the molecular grid, and a list of generated files. State which structures entered the final report. Do not infer efficacy from the structures.
```

LabOntology connects each SMILES with its validation, visualization, and property results. An invalid structure remains in the record but does not enter later steps. If visualization or property calculation fails for one molecule, the corresponding part can be rerun without discarding the other results.

### 2. Following an experimental sequence: lead generation, structure screening, and ADMET triage

#### Install the Skills

```text
Please install these four Skills:
- denovo-design: https://scphub.intern-ai.org.cn/skill/798
- smiles-validation: https://scphub.intern-ai.org.cn/skill/1032
- molecular-optimization: https://scphub.intern-ai.org.cn/skill/916
- admet-prediction: https://scphub.intern-ai.org.cn/skill/739
```

#### Suggested prompt

```text
Using aspirin as a teaching example, please complete a computational workflow from candidate generation to ADMET triage.

Lead SMILES: CC(=O)Oc1ccccc1C(=O)O

First use denovo-design to generate four candidates with each of two strategies: R-group and bioisostere. Then use smiles-validation to check every candidate and keep only complete, parseable, single-molecule structures without `*` attachment points. For passing candidates, use molecular-optimization for one constrained optimization round with MW<500, LogP<5, and QED>0.5 as targets. Finally use admet-prediction for oral-property and ADMET triage of the optimized structures.

Please output a ranked shortlist, a rejection table for all candidates, validation results, before-and-after optimization properties, ADMET results, and a summary report. Record how each candidate moved from generation to the next step. Do not present model predictions as experimental results or efficacy conclusions.
```

LabOntology links candidate generation, structure checking, optimization, and ADMET triage in order. Every candidate's entry into the next step, rejection point, and rejection reason can be traced. The final shortlist remains linked to the generation results.

### 3. Local replanning: ELISA standard curve and sample concentration analysis

The standard and sample readings are included in the prompts, so no plate-reader file is needed. The first round fits the standard curve and checks sample range. The second round supplies a diluted measurement for the out-of-range sample, and LabOntology reruns only the affected part.

#### Install the Skills

```text
Please install these three Skills:
- immunology-assays: https://scphub.intern-ai.org.cn/skill/867
- physics-fitting: https://scphub.intern-ai.org.cn/skill/952
- sympy: https://scphub.intern-ai.org.cn/skill/1048
```

#### Suggested prompts

First-round prompt:

```text
Please use the following simulated ELISA readings to fit a standard curve and estimate sample concentrations. The data is constructed for this tutorial and does not represent real experimental results. All concentrations are in ng/mL and OD450 is the raw absorbance.

Blank wells: 0.050, 0.052
Standards (concentration; two replicate OD450 readings):
1.56; 0.075, 0.079
3.125; 0.101, 0.106
6.25; 0.164, 0.171
12.5; 0.325, 0.338
25; 0.681, 0.704
50; 1.245, 1.281
100; 1.790, 1.824

Sample S1 is undiluted, with OD450=0.418, 0.432. Sample S2 is undiluted, with OD450=1.955, 1.972. First calculate the blank mean and pass it as blank_od to the immunology-assays method so the blank is not subtracted twice. Fit a 4PL standard curve and calculate replicate means. Then use physics-fitting to check residuals, confidence intervals, and whether each sample is within the standard-curve range. Use sympy to organize the 4PL inverse-concentration formula and check the inversion conditions.

Report the currently valid results first, clearly distinguishing quantifiable and out-of-range samples. Save the raw readings, fitted parameters, residual plot, concentration table, and calculation steps. If S2 is outside the curve range, do not extrapolate its concentration; mark it for remeasurement.
```

Second-round prompt, sent in the same task:

```text
S2 was diluted 1:10 and remeasured. The two replicate OD450 readings are 0.692 and 0.711; the standards and blank remain unchanged. Reuse the standard curve that has already passed checking. Calculate the diluted S2 concentration and the original-sample concentration after multiplying by 10, check whether the remeasurement is within the quantifiable range, and update the final report. Keep the original out-of-range S2 record and the S1 result. Do not refit unchanged standards. Record where this round resumed and which results were reused.
```

LabOntology keeps the raw readings, standard curve, range check, and sample quantification in one task. When S2 is out of range, the task pauses at remeasurement. After the new reading is supplied, it continues from S2 and reuses the completed curve and S1 result.

### 4. Long-context continuity: damped-oscillator spectral analysis and equation checking

This is a multi-round physics teaching simulation. The parameters and later changes are written in the prompts. The Agent generates the simulated signal from those parameters, so no measurement file is needed.

#### Install the Skills

```text
Please install these three Skills:
- sympy: https://scphub.intern-ai.org.cn/skill/1048
- spectral-analysis: https://scphub.intern-ai.org.cn/skill/1036
- ode-solver: https://scphub.intern-ai.org.cn/skill/931
```

First-round prompt:

```text
Please start a teaching simulation of a damped oscillator. Mark all data as simulated and do not call external APIs. Parameters: m=0.5 kg, k=200 N/m, c=1 N·s/m, x0=0.01 m, v0=0, sampling rate 200 Hz, duration 8 s.

Use sympy to organize m*x''+c*x'+k*x=0 and provide the natural frequency, damping ratio, and damped frequency. Generate a noiseless displacement signal from the analytical solution. Use ode-solver for a numerical solution and compare it with the analytical result. Save the parameters, equation, simulated data, and ODE error as a baseline report. Record the task state; sensor conditions will be added later.
```

Second-round prompt in the same long conversation:

```text
Additional sensor conditions: readings are limited to -8 mm to +8 mm, and there are no readings from 3.00 s to 3.20 s. Create a follow-up analysis associated with the baseline task. Using the same parameters, generate observed_signal under these conditions and mark the saturated points and missing interval. Do not overwrite the noiseless baseline. Use spectral-analysis on the affected signal: do not fill the missing interval with zeros; analyze continuous valid segments first, then use linear interpolation as a separate sensitivity comparison. Explain how saturation and the missing interval affect the dominant frequency and amplitude envelope.
```

Third-round prompt:

```text
Please summarize this task by comparing the noiseless baseline with the signal after sensor limits were added. Explain which conclusions are stable and which are affected by missing or saturated data. The report must include the equation derivation, parameters, both signals, both spectral analyses, the ODE comparison, residual plots, error interpretation, and the restart point. Reuse the unchanged ODE baseline and rerun only signal generation and spectral steps affected by the sensor conditions.
```

LabOntology first saves the parameters, noiseless signal, and numerical solution as a baseline. The later sensor limits become new task conditions without overwriting that baseline. The Agent reruns only the affected signal and spectral analyses and compares the old and new results.

### 5. Cross-conversation continuity: metabolic conditions affecting a synthetic gene switch

This is a synthetic-biology teaching simulation and does not represent real cell experiments. All reactions and parameters are supplied in the first prompt. The first conversation creates the baseline; a new conversation in the same project changes one condition and continues the task.

#### Install the Skills

```text
Please install these three Skills:
- cobrapy: https://scphub.intern-ai.org.cn/skill/778
- synthetic-biology: https://scphub.intern-ai.org.cn/skill/1049
- ode-solver: https://scphub.intern-ai.org.cn/skill/931
```

First conversation:

```text
Please complete a teaching simulation of how metabolic conditions affect a synthetic-gene toggle switch. Mark all results as simulated_toy_model; they do not represent real E. coli physiology or experimental data.

Use cobrapy to build a minimal model locally from scratch. Do not load an external model file. Include only these reactions: glucose exchange `EX_glc_e: glc_e <=>` with uptake lower bounds of -10 and -2 and upper bound 0 mmol gDW^-1 h^-1, glucose transport (glc_e -> glc_c), glycolysis (glc_c -> 2 pyr_c), and a pseudo-growth reaction (20 pyr_c -> biomass). Maximize the pseudo-growth reaction. Record reaction equations, flux bounds, units, and model checks, and save the SBML.

Multiply each condition's pseudo-growth flux by the explicit teaching scale 0.1 h^-1/(pseudo-growth flux unit) to obtain the toggle-switch dilution rate gamma. Integrate the following equations for both initial states over 0–50 h and output trajectories and steady states:
dA/dt = 5/(1+B^2) - (0.5+gamma)A
dB/dt = 5/(1+A^2) - (0.5+gamma)B
Initial states: (A,B)=(0.1,3.0) and (3.0,0.1). Use synthetic-biology to build and analyze the switch model, then use ode-solver to independently verify at least one condition and compare the steady states and residuals. Do not assume that bistability must exist.

Save the model, FBA condition table, switch trajectories for both conditions, figures, verification results, and a summary. Record the input and output of every step in LabOntology. Do not download models or call services that require an API key.
```

New conversation in the same project:

```text
Use LabOntology to find this project's previous “metabolic conditions affecting a synthetic-gene switch” task and restore its model, reactions, parameters, and results. Change the glucose uptake upper limit for the carbon-limited condition from 2 to 1 mmol gDW^-1 h^-1, keeping everything else unchanged. If the previous task is complete, create a related follow-up task; if it is still running, continue the original task. Recalculate only the constrained-condition FBA, gamma, and its two ODE trajectories, then compare them with the previous baseline. Keep the original results and update the report without overwriting unchanged parts.
```

In the new conversation, LabOntology restores the model, parameters, and previous results from the project record. Only the constrained condition changed, so only its FBA and two ODE trajectories are recalculated. The original baseline remains available for comparison.

### 6. Experience accumulation and self-improvement: crystal-structure analysis and material-parameter organization

This example uses idealized crystal parameters from the prompts. It first completes a brief analysis, then records a missed check during rework, and finally checks whether the reminder is reused for a germanium analysis. No structure file is needed.

#### Install the Skills

```text
Please install these three Skills:
- pymatgen: https://scphub.intern-ai.org.cn/skill/974
- dimensional-analysis: https://scphub.intern-ai.org.cn/skill/800
- sympy: https://scphub.intern-ai.org.cn/skill/1048
```

First-round prompt:

```text
Please analyze an idealized silicon crystal structure. All input parameters are included here. Do not read an external structure file or query an online materials database.

Use pymatgen to construct conventional cubic diamond-cubic Si: a=b=c=5.431 Å and α=β=γ=90°. The eight fractional coordinates are:
(0,0,0), (0,1/2,1/2), (1/2,0,1/2), (1/2,1/2,0),
(1/4,1/4,1/4), (1/4,3/4,3/4), (3/4,1/4,3/4), (3/4,3/4,1/4).

Output the cell volume, composition, density, crystal symmetry, space group, CIF, and POSCAR. Use pymatgen's built-in atomic weight for Si and Avogadro's constant N_A=6.02214076×10^23 mol^-1. Use dimensional-analysis to check the conversion between Å³, g/mol, and g/cm³, and use sympy to verify rho = n*M/(N_A*V). In the first report, list the results briefly without expanding the atom-count and density substitution steps. State that this is an ideal-structure calculation, not characterization of a real sample.
```

Second-round prompt after checking the result:

```text
The density report did not explicitly list the number of atoms in the conventional cell or explain how that number enters the density formula. Create a related report-revision task in LabOntology, add both items, and recalculate the density. Also record “Before calculating crystal density, check the cell type, number of basis atoms, and volume units” as a reminder for future materials-structure analyses. Keep the existing structure files and all other correct results.
```

Third-round prompt in a new conversation in the same project:

```text
Please start a new germanium crystal-structure analysis. First check the materials-structure reminder recorded by LabOntology, then use it to review the following inputs: conventional cubic diamond-cubic Ge, a=b=c=5.658 Å, α=β=γ=90°, element Ge, and the eight fractional coordinates:
(0,0,0), (0,1/2,1/2), (1/2,0,1/2), (1/2,1/2,0),
(1/4,1/4,1/4), (1/4,3/4,3/4), (3/4,1/4,3/4), (3/4,3/4,1/4).
All structure parameters are included here, so no file upload or online materials database is needed. Use N_A=6.02214076×10^23 mol^-1 and pymatgen's built-in atomic weight for Ge.

Generate CIF and POSCAR, calculate cell volume, atom count, density, composition, and space group, and use dimensional-analysis for units and sympy for the formula. In the report, explicitly state the cell type, atom count, atomic-weight source, volume conversion, and density substitution. Explain which checks came from the previous task. Do not overwrite the silicon results.
```

LabOntology links the first silicon calculation, the missing-check revision, and the later task. The reminder about checking cell atom count and volume units can be retrieved at the start of the germanium analysis. The germanium result is recorded separately and does not overwrite the silicon result.
