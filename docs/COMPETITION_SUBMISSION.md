# 提交材料总览

本文档整理 `规范彝文 OCR / NuosuBburma OCR` 的公开提交材料、复现入口和核验边界。完整技术细节分别放在 [项目背景与任务定义](PROJECT_BACKGROUND.md)、[评估集说明](EVALUATION_DATASET.md)、[评估集质检报告](EVALUATION_QUALITY_REPORT.md)、[训练数据构建报告](TRAINING_DATA_CONSTRUCTION_REPORT.md) 和 [模型与训练说明](MODEL_AND_TRAINING.md)。

## 一句话概括

`规范彝文 OCR / NuosuBburma OCR` 是一个基于 `PaddleOCR-VL-1.6 (0.9B)` + LoRA 微调的 OCR 项目，目标是把真实规范彝文资料从图片层转成可复制、可检索、可继续用于教学和语料建设的 Unicode 文本。

项目选择的是低资源民族文字 OCR 场景：规范彝文公开 OCR 数据和可复用模型都很少，真实资料又大量存在于旧书扫描、教材、手写稿、页面照片和彝汉混排文本中。

## 项目内容摘要

| 方向 | 项目说明 | 位置 |
|---|---|---|
| 真实评估 | `603` 条真实来源样本，`603` 张图片；覆盖新印刷、旧印刷、手写、页面照片和实拍场景；全部样本纳入正式评估，合成样本不进入主结果 | [评估集说明](EVALUATION_DATASET.md)，[评估集质检报告](EVALUATION_QUALITY_REPORT.md)，`evaluation/` |
| 低资源场景 | 规范彝文 OCR 缺少公开基准与可直接复用模型；现有通用 OCR 基本不能直接识别规范彝文；资料数字化、教学检字和后续 NLP 语料建设都有真实需求 | [项目背景与任务定义](PROJECT_BACKGROUND.md) |
| 任务难点 | 1165 个规范彝文字符、形近字多；真实资料包含 page / region / line、旧印刷噪声、手写、彝汉混排、数字、脚注和少量拉丁注音 | [项目背景与任务定义](PROJECT_BACKGROUND.md)，[评估集说明](EVALUATION_DATASET.md) |
| 训练数据 | 真实锚点 + 合成覆盖 + monitor 诊断；合成数据用于补低频字、形近字、旧印刷退化和输出边界，不进入最终真实评估；训练 manifest 记录数据构成和清理原则 | [训练数据构建报告](TRAINING_DATA_CONSTRUCTION_REPORT.md)，[模型与训练说明](MODEL_AND_TRAINING.md)，`configs/train_data_manifest_v5_16.json` |
| 模型策略 | 使用 PaddleOCR-VL-1.6 LoRA 微调；分阶段控制视觉覆盖和输出空间漂移；第三阶段用人工复核真实样本检查普遍错误模式，选模同时看彝文、汉字、数字和 LaTeX/ASCII/长输出风险 | [模型与训练说明](MODEL_AND_TRAINING.md)，`model/README.md` |
| 开源材料 | GitHub 提供配置、脚本、评估结果、模型入口和本地 demo；HF Model 托管模型权重；HF Dataset 托管最小评估集 | 本仓库，HF Model，HF Dataset |

## 提交材料清单

| 材料 | 状态 | 链接或位置 |
|---|---|---|
| GitHub 开源项目 | 已公开 | `https://github.com/nanxidajun/nuosubburma-ocr-paddleocr-vl` |
| Hugging Face 模型 | 已公开 | `https://huggingface.co/nanxidajun/NuosuBburma-OCR` |
| Hugging Face 模型卡 | 已公开 | `https://huggingface.co/nanxidajun/NuosuBburma-OCR` |
| HF Dataset 评估集 | 已公开 | `https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set` |
| 模型入口说明 | 已放入仓库 | `model/README.md` |
| 项目背景与任务定义 | 已放入仓库 | `docs/PROJECT_BACKGROUND.md` |
| 评估集 GitHub 入口 | 已放入仓库 | `NuosuBburma_OCR_Evaluation_Set/README.md` |
| 评估集说明 | 已放入仓库 | `docs/EVALUATION_DATASET.md` |
| 评估集质检报告 | 已放入仓库 | `docs/EVALUATION_QUALITY_REPORT.md` |
| 训练数据构建报告 | 已放入仓库 | `docs/TRAINING_DATA_CONSTRUCTION_REPORT.md` |
| 模型与训练说明 | 已放入仓库 | `docs/MODEL_AND_TRAINING.md` |
| 训练配置与 manifest | 已放入仓库 | `configs/` |
| 评估脚本 | 已放入仓库 | `scripts/eval_nuosubburma.py`，`scripts/analyze_submission_eval.py`，`scripts/run_eval.sh` |
| 提交评估结果 | 已放入仓库 | `evaluation/` |
| Demo | 本地单图 demo | `demo/README.md`，`demo/infer_single_image.py` |

## 主要结果

最终提交模型在 `NuosuBburma OCR Evaluation Set` 的 `603` 条真实样本上评估，结果如下：

![Evaluation snapshot](figures/evaluation_snapshot.svg)

| 指标 | 结果 |
|---|---:|
| 样本数 | 603 |
| Avg NED | 0.036068 |
| WS Avg NED | 0.034219 |
| NFKC+WS Avg NED | 0.033964 |
| Yi-only Avg NED | 0.038309 |
| Han-only Avg NED | 0.022447 |
| Digit-only Avg NED | 0.139918 |
| replacement / LaTeX / extra Latin / long_pred | 0 / 2 / 0 / 0 |
| ASCII-letter rows | 18 / 18，预测含 Latin 的 18 条 GT 本身也含 Latin 注音 |

这些结果对应的原始文件在：

```text
evaluation/README.md
evaluation/summary.md
evaluation/summary.json
evaluation/charts/
evaluation/tables/
evaluation/raw/submission_model_result.jsonl
```

## 复现入口

下载模型：

```bash
# 国内网络较慢时，取消下一行注释使用 HF 镜像：
# export HF_ENDPOINT=https://hf-mirror.com

hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

下载评估集：

```bash
# 国内网络较慢时，取消下一行注释使用 HF 镜像：
# export HF_ENDPOINT=https://hf-mirror.com

hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

运行评估：

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl

python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```

## 核验说明

| 核验问题 | 回答 |
|---|---|
| 评估集是否真实 | 是。主评估集为真实来源样本，不使用合成样本作为主评分材料 |
| 合成数据是否进入评估 | 否。合成数据只用于训练补覆盖和 monitor 诊断 |
| GT 是否完全由模型生成 | 否。中间模型只用于预标注草稿，最终需要人工核对 |
| 是否把最终评估集喂回训练 | 否。训练数据构建保留 denylist 和 overlap 清理，最终提交模型固定后在 603 条 clean set 上评估 |
| 训练数据是否有构建报告 | 有。见 `docs/TRAINING_DATA_CONSTRUCTION_REPORT.md` |
| 评估集是否有质检说明 | 有。见 `docs/EVALUATION_QUALITY_REPORT.md` |
| 结果是否可复查 | 可以。仓库保留评估脚本、逐样本结果、汇总统计和危险输出统计 |
| 权重是否公开 | 是。模型权重托管在 Hugging Face Model |

## 能力边界

- 本模型支持整页、区域和行图输入。
- 当前最稳定的使用方式通常是 line / region OCR。
- 复杂整页文档在版面较密、手写、多栏、脚注、注音块或图文混排较强时，建议配合版面分析、切图流程或人工复核。
- 手写已有一定泛化能力，但仍明显弱于印刷体。
- 本版本尚未进行专门的端侧/移动端优化。
