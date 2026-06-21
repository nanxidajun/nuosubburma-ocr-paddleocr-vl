# Model and Training

This document records the model route, training-data construction logic, and model-selection method for the Nuosu Bburma OCR project.

Final numerical results will be updated after the evaluation rerun.

## Base Method

| Item | Value |
|---|---|
| Base model | PaddleOCR-VL-1.6 (0.9B) |
| Fine-tuning method | LoRA |
| Task prompt | `<image>OCR:` |
| Main task | Nuosu Bburma / 规范彝文 OCR |
| Mixed text | Yi-Han mixed text supported |
| Hardware | NVIDIA RTX 4090D |
| Deployment status | not endpoint/mobile deployed yet |

## Key Training Parameters

These parameters should be checked against the final frozen training log before submission.

| Parameter | Value |
|---|---:|
| max sequence length | 16384 |
| LoRA rank | 8 |
| per-device batch size | 4 |
| gradient accumulation | 16 |
| epochs | 2 |
| scheduler | cosine |
| learning rate | 5.0e-4 |
| minimum learning rate | 5.0e-5 |
| precision | bf16 |
| sharding | stage2 |

## Training Route

The model route should be explained as a branch decision tree, not as a long chronological experiment diary.

### Stage 1: Single-Book Feasibility

Starting point:

- real lines from `《勒俄特依》`;
- relatively simple layout;
- short poetic lines;
- goal: verify that PaddleOCR-VL LoRA fine-tuning can learn Nuosu Bburma glyphs and output format.

Judgment:

- feasible for the basic OCR task;
- insufficient coverage for fonts, mixed scripts, old-print noise, regions, and handwriting.

### Stage 2: Real Data + Synthetic Coverage + Monitor Sets

Starting point:

- `《勒俄特依》` real lines;
- synthetic data for low-frequency characters, confusable characters, punctuation, old-print degradation, mixed Yi-Han lines, and layout variation;
- monitor sets for output drift and format failures.

Judgment:

- synthetic data is useful only when visual expansion and output-space risk are monitored together;
- monitor sets are diagnostic tools, not final scoring data.

### Stage 3: Reviewed Evaluation and Final Selection

Starting point:

- reviewed evaluation set;
- final evaluation rerun pending;
- model selection based on both recognition accuracy and failure modes.

Judgment:

- the final model should not be selected by a single metric alone;
- selection should consider NED, Yi recognition, Han recognition, output drift, long prediction, and mixed-script behavior.

## Branch Card Format

Each important training branch should be summarized in the same compact format.

| Field | Meaning |
|---|---|
| branch name | internal model/version name |
| parent branch | previous branch or root branch |
| train rows | total training rows |
| data composition | only the important additions or removals |
| NED | rerun result or `TBD` |
| judgment | keep, reject, fallback, or diagnostic only |

Example template:

| Branch | Parent | Train rows | Data composition | NED | Judgment |
|---|---|---:|---|---:|---|
| vX.Y branch name | parent | TBD | real + synthetic + guard data summary | TBD | TBD |

Do not include exact-match columns in the branch card unless the final report specifically needs them.

## Data Construction Principles

- Keep real and synthetic data separable.
- Do not add evaluation answers as training targets.
- Increase visual diversity without blindly increasing text-label diversity.
- Cap high-risk categories that can trigger Latin, formula, or long-tail output drift.
- Track mixed-script behavior separately from pure Yi recognition.
- Treat handwriting and multi-line region OCR as difficult generalization cases, not as solved capabilities.

## Known Limitations

- Handwriting remains the weakest scenario.
- Multi-line region OCR should be evaluated separately from line-level OCR.
- Endpoint/mobile deployment has not been implemented.
- Final metrics must wait for the rerun evaluation.
