# NuosuBburma OCR

`NuosuBburma OCR` 是一个基于 `PaddlePaddle/PaddleOCR-VL-1.6` 微调的规范彝文 OCR 项目。项目目标不是做通用 OCR，而是让模型在规范彝文、彝汉混排、老印刷材料、少量多行区域和有限真实手写场景中稳定输出可用文本。

## 当前状态

- 最终选择模型：`v5.16_synth_capped_rerender`。
- 最终评估集：`NuosuBburma_OCR_Evaluation_Set`，603 条主评分样本。
- 模型权重和模型卡后续走模型托管平台；GitHub 暂不维护 `model/` 目录内容。
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
data/              603 条 clean 评估集
demo/              单图推理 demo 与少量样例图
docs/              项目说明、训练说明、评估集说明
evaluation/        clean603 最终评估结果与统计表
model/             暂时占位，模型卡后续走外部模型托管平台
scripts/           训练、评估、统计、评估集构建工具
```

仓库没有放入本地的大量实验中间产物、长篇写作草稿和分析工作区。

## 核心文档

- [提交材料映射](docs/COMPETITION_SUBMISSION.md)
- [模型与训练](docs/MODEL_AND_TRAINING.md)
- [评估集说明](docs/EVALUATION_DATASET.md)

## 快速评估

安装 PaddleOCR-VL 运行环境并下载合并后的模型导出目录后，可以运行：

```bash
scripts/run_eval.sh /path/to/NuosuBburma-OCR-export data/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl outputs/eval_clean603_result.jsonl
python scripts/analyze_clean603_eval.py \
  --annotations data/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/eval_clean603_result.jsonl \
  --out-dir outputs/eval_clean603_analysis
```

本仓库内已经包含一次最终重跑结果，见 [evaluation/clean603](evaluation/clean603)。

## 作者

NanxiDajun
