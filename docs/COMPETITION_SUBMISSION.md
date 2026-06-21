# 提交材料映射

本文档把比赛提交需要的材料对应到本仓库中的文件位置。这里保留的是工程和提交索引，不写长篇实验文章。

## 提交状态

| 项目 | 状态 | 位置 |
|---|---|---|
| GitHub 项目 | 已整理待复核 | 当前仓库 |
| 模型权重 | 后续外部托管 | 待补模型托管链接 |
| 模型卡 | 后续外部托管 | 待补模型托管链接 |
| 评估集 | 已放入仓库 | `datasets/NuosuBburma_OCR_Evaluation_Set/` |
| 评估脚本和结果 | 已放入仓库 | `scripts/`, `evaluation/submission_eval/` |
| 训练配置和 manifest | 已放入仓库 | `configs/` |
| 演示 | 本地单图 demo | `demo/` |

## 1. 评估集

已包含：

- 评估图片。
- `annotations.jsonl` 标注。
- 来源、难度、版式和混排类型统计。
- 评估脚本。
- 提交评估集重跑结果。

对应位置：

- `datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl`
- `datasets/NuosuBburma_OCR_Evaluation_Set/images/`
- `datasets/NuosuBburma_OCR_Evaluation_Set/dataset_summary.json`
- `datasets/NuosuBburma_OCR_Evaluation_Set/source_summary.csv`
- `scripts/eval_nuosubburma.py`
- `scripts/analyze_submission_eval.py`

## 2. 训练数据构建说明

简版训练记录见：

- [模型与训练](MODEL_AND_TRAINING.md)
- `configs/train_data_manifest_v5_16.json`

本仓库不放长篇写作草稿和本地实验日记。

## 3. 开源项目材料

已包含：

- 训练和导出配置。
- 评估脚本。
- 评估集。
- 评估结果。
- 模型权重和模型卡走外部模型托管平台。
- 单图 demo。

大模型权重不直接提交到 GitHub。后续可上传到 Hugging Face 或其他模型托管平台，并在提交材料中补充链接。

## 4. 邮件/提交清单

- GitHub 仓库：`https://github.com/nanxidajun/nuosubburma-ocr-paddleocr-vl`
- 模型托管链接：待上传后补充。
- 评估集：`datasets/NuosuBburma_OCR_Evaluation_Set/`
- 训练配置：`configs/`
- 演示说明：`demo/README.md`
- GitHub ID：`nanxidajun`

建议邮件标题格式：

```text
PaddleOCR衍生模型挑战赛-【材料名称】-【GitHub ID】
```

## 完整性说明

- 仓库中的评估指标来自提交评估集重跑。
- 评估数据不作为训练答案。
- 已知限制保留在文档中，不隐藏模型边界。
