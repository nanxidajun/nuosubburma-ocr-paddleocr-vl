# 脚本

本目录只保留推理、评估和统计需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集逐图运行端到端 OCR 推理，每张图片直接进模型输出一条预测文本。
- `run_eval.sh`：`paddle.distributed.launch` 的评估封装。
- `analyze_submission_eval.py`：计算 Raw / 去空白 / 规范化 Avg NED、分组 NED（场景、难度、文字构成）和复核表。
- `smoke_check.sh`：安装后健康检查，检查依赖与样例图，本地有模型时跑一张单图 OCR。

评估依赖：`paddle`、`paddleformers`、`Pillow`、`tqdm`、`python-Levenshtein`。

## 端到端评估流程

最终模型是单模型端到端 OCR：无论 `line`、`region` 还是整页，都以整幅图片直接输入，提示词为 `<image>OCR:`，模型一次输出该图的完整文字，不做页面切割、路由或多路合并。

**1. 下载模型与评估集**（评估集以 Hugging Face 数据集为准）：

```text
models/NuosuBburma-OCR
datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl
```

```bash
hf download nanxidajun/NuosuBburma-OCR --repo-type model \
  --local-dir models/NuosuBburma-OCR
hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

**2. 安装后先做健康检查：**

```bash
scripts/smoke_check.sh
# 模型不在默认目录时：
MODEL_PATH=/path/to/NuosuBburma-OCR scripts/smoke_check.sh
```

**3. 对全部 1,030 张评估图片跑推理：**

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/eval_result.jsonl
# 指定 GPU：CUDA_VISIBLE_DEVICES=1 scripts/run_eval.sh ...
```

**4. 打分并生成分组统计：**

```bash
python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/eval_result.jsonl \
  --out-dir outputs/eval_analysis \
  --title "NuosuBburma OCR: full evaluation set"
```

主口径为 Raw Avg NED；`analyze_submission_eval.py` 会同时输出去空白、规范化 NED 及按场景 / 难度 / 文字构成的分组表，用于定位薄弱项。

## 相关目录

- 本地单图 OCR 演示：[demo](../demo/)。`demo/infer_single_image.py` 跑单张图片 OCR。
- OCR 之后的注音添加：[postprocess](../postprocess/)。评估脚本中的输出风险字段仅用于审计复核，不会自动改写预测文本。
