# Competition Submission Map

This document maps the PaddleOCR Global Derivative Model Challenge requirements to the files and links that will be provided by this project.

## Submission Status

| Item | Status | Location |
|---|---|---|
| Public GitHub project | in progress | this repository |
| Model weights | pending | Hugging Face link TBD |
| Model card | pending | `model/` or Hugging Face model page |
| Evaluation dataset | pending rerun/review | `data/`, external dataset link TBD |
| Evaluation scripts and results | pending rerun | `evaluation/` |
| Training data construction report | draft structure | `docs/MODEL_AND_TRAINING.md` |
| Demo | prototype scope pending | `demo/` |

## Required Materials

### 1. Evaluation Set

Expected materials:

- images or document samples;
- annotations;
- task description;
- evaluation script;
- dataset description, including source, scale, category distribution, and difficulty analysis.

Current policy:

- final evaluation results will be added only after rerun;
- synthetic and real sources must be clearly separated;
- public release boundaries will be reviewed before uploading data.

### 2. Training Data Construction Report

The training report will cover:

- real data sources;
- synthetic data strategy;
- annotation guidelines;
- quality-control process;
- key construction scripts;
- relationship between training branches and model selection.

The working document is [Model and Training](MODEL_AND_TRAINING.md).

### 3. Open-Source Project

Expected materials:

- training and evaluation code;
- model documentation;
- demo or prototype;
- reproducible configuration files;
- clear links to model and dataset artifacts.

Large model weights and large datasets will not be committed directly to GitHub.

## Final Email Checklist

To be completed before submission:

- GitHub repository link: TBD
- Hugging Face model link: TBD
- Evaluation dataset link: TBD
- Training data construction report: TBD
- Demo link or local demo instructions: TBD
- GitHub ID: TBD

Suggested email title format:

```text
PaddleOCR衍生模型挑战赛-【材料名称】-【GitHub ID】
```

## Integrity Notes

- The final reported metrics must come from the rerun evaluation.
- Evaluation data should not be used as model training targets.
- Synthetic evaluation samples, if any, must be explicitly labeled and kept below a safe review threshold.
- Known limitations should remain visible in the final submission.
