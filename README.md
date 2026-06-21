# NuosuBburma OCR

`NuosuBburma OCR` 是一个基于 `PaddlePaddle/PaddleOCR-VL-1.6` 微调的规范彝文 OCR 项目。项目目标不是做通用 OCR，而是让模型在规范彝文、彝汉混排、老印刷材料、少量多行区域和有限真实手写场景中稳定输出可用文本。

## 当前状态

- 当前提交模型：`NuosuBburma OCR`，基于 PaddleOCR-VL LoRA 微调，模型托管在 Hugging Face。
- 提交评估集：`NuosuBburma OCR Evaluation Set`，真实数据评估集，完整数据托管在 Hugging Face Dataset。
- GitHub 不维护大模型权重；`model/` 目录只保留模型托管入口和下载说明。
- 本仓库已经放入可复跑评估所需的数据、脚本、配置和结果表。

## 项目范围

- 规范彝文单行 OCR。
- 彝文与汉语混排 OCR。
- 老印刷、书籍扫描件裁切行。
- 少量 region/page 场景。
- 有限真实手写和屏幕页面样本。
- PaddleOCR-VL-1.6 + LoRA 微调流程。

当前不声明移动端或端侧部署能力，端侧部署作为后续工作。

## 仓库结构

```text
configs/           训练/导出配置与训练数据 manifest 快照
datasets/          NuosuBburma OCR 真实数据提交评估集
demo/              单图推理 demo 与少量样例图
docs/              项目说明、训练说明、评估集说明
evaluation/        提交评估集重跑结果与统计表
model/             模型托管入口、下载命令和使用边界说明
scripts/           训练、评估、统计工具
```

仓库没有放入本地的大量实验中间产物、长篇写作草稿和分析工作区。

## 核心文档

- [提交材料映射](docs/COMPETITION_SUBMISSION.md)
- [模型入口](model/README.md)
- [模型与训练](docs/MODEL_AND_TRAINING.md)
- [评估集说明](docs/EVALUATION_DATASET.md)

## 快速评估

安装 PaddleOCR-VL 运行环境并下载合并后的模型导出目录与评估集后，可以运行：

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR

hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set

scripts/run_eval.sh models/NuosuBburma-OCR datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl
python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```

本仓库内已经包含一次提交评估集重跑结果，见 [evaluation/NuosuBburma_OCR_Evaluation_Set](evaluation/NuosuBburma_OCR_Evaluation_Set)。

## 外部链接

- Hugging Face 模型：<https://huggingface.co/nanxidajun/NuosuBburma-OCR>
- Hugging Face 评估集：<https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set>

## 作者

NanxiDajun
