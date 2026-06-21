# 提交材料映射

本文档把比赛提交需要的材料对应到本仓库中的文件位置。这里保留的是工程和提交索引，不写长篇实验文章。

## 提交状态

| 项目 | 状态 | 位置 |
|---|---|---|
| GitHub 项目 | 已整理待复核 | 当前仓库 |
| 模型权重 | 已上传 Hugging Face | `https://huggingface.co/nanxidajun/NuosuBburma-OCR` |
| 模型卡 | 已上传 Hugging Face | `https://huggingface.co/nanxidajun/NuosuBburma-OCR` |
| 评估集 | 已上传 HF Dataset，仓库保留入口 | `datasets/NuosuBburma_OCR_Evaluation_Set/README.md` |
| 评估脚本和结果 | 已放入仓库 | `scripts/`, `evaluation/NuosuBburma_OCR_Evaluation_Set/` |
| 训练配置和 manifest | 已放入仓库 | `configs/` |
| 演示 | 本地单图 demo | `demo/` |

## 1. 评估集

评估集托管：

- HF Dataset：`https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set`
- GitHub 仓库保留评估集入口说明、评估脚本和提交评估集重跑结果。

HF Dataset 当前包含复跑评估所需的最小文件：

- `annotations.jsonl`
- `images/`

仓库内对应位置：

- `datasets/NuosuBburma_OCR_Evaluation_Set/README.md`
- `scripts/eval_nuosubburma.py`
- `scripts/analyze_submission_eval.py`
- `evaluation/NuosuBburma_OCR_Evaluation_Set/`

## 2. 训练数据构建说明

简版训练记录见：

- [模型与训练](MODEL_AND_TRAINING.md)
- `configs/train_data_manifest_v5_16.json`

本仓库不放长篇写作草稿和本地实验日记。

## 3. 开源项目材料

已包含：

- 训练和导出配置。
- 评估脚本。
- 评估集入口。
- 评估结果。
- 模型权重和模型卡托管在 Hugging Face。
- 单图 demo。

大模型权重不直接提交到 GitHub。评估集使用 HF Dataset 托管，模型权重使用 Hugging Face Model 托管。

## 4. 邮件/提交清单

- GitHub 仓库：`https://github.com/nanxidajun/nuosubburma-ocr-paddleocr-vl`
- 模型托管链接：`https://huggingface.co/nanxidajun/NuosuBburma-OCR`
- HF Dataset / 评估集来源：`https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set`
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
