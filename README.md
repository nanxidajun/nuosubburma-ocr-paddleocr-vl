# Nuosu Bburma OCR with PaddleOCR-VL LoRA Fine-tuning

基于 PaddleOCR-VL 微调的规范彝文 OCR 项目。

This repository is being organized for the PaddleOCR Global Derivative Model Challenge. It focuses on OCR for Nuosu Bburma, also known in Chinese as 规范彝文, with attention to low-resource document recognition, mixed Yi-Han text, old printed materials, and reusable evaluation data.

## Current Status

This repository is under submission preparation.

- The public repository structure has been cleaned and simplified.
- Final evaluation results will be added after the evaluation rerun.
- Model weights are not stored directly in GitHub. A Hugging Face model link will be added after packaging review.
- Dataset release boundaries are still being reviewed. Public samples and evaluation-set access instructions will be added after confirmation.

## Scope

The project targets:

- Nuosu Bburma / 规范彝文 OCR;
- printed Yi text and Yi-Han mixed text;
- selected old-print and region OCR cases;
- a PaddleOCR-VL-1.6 (0.9B) + LoRA fine-tuning workflow;
- evaluation data and documentation for a low-resource writing-system OCR task.

The project does not currently claim endpoint/mobile deployment. Edge deployment is treated as future work.

## Repository Layout

```text
configs/           Training, export, inference, and evaluation configs
data/              Public samples and evaluation-set access notes
demo/              Demo prototype and related assets
docs/              Three core submission documents
evaluation/        Evaluation scripts, rerun outputs, and error analysis
model/             Model card preview and external model links
scripts/           Reproducibility and utility scripts
```

The repository intentionally avoids deep empty folders. Subdirectories will be added only when real files need them.

## Core Documents

- [Competition Submission Map](docs/COMPETITION_SUBMISSION.md)
- [Model and Training](docs/MODEL_AND_TRAINING.md)
- [Evaluation Dataset](docs/EVALUATION_DATASET.md)

## Author

NanxiDajun
