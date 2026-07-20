# 脚本

本目录只保留推理、评估和统计需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集逐图运行 OCR 推理，每张图片输出一条预测文本。
- `run_eval.sh`：`paddle.distributed.launch` 的评估封装。
- `build_evaluation_figures.py`：按最终口径计算语料级 CER、逐样本 NED、错误贡献与长尾分布，并生成公开 SVG 图表。
- `analyze_submission_eval.py`：生成 Raw / 去空白 / NFKC 诊断指标、分组明细和人工复核表。
- `smoke_check.sh`：安装后健康检查，检查依赖与样例图，本地有模型时跑一张单图 OCR。

评估依赖：`paddle`、`paddleformers`、`Pillow`、`tqdm`、`python-Levenshtein`。

## 端到端评估流程

评估流程对 `line`、`region` 和整页样本使用统一提示词 `<image>OCR:`，并为每张图片生成一条预测文本。

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

**5. 按最终口径复算并生成公开图表：**

```bash
python scripts/build_evaluation_figures.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --predictions outputs/eval_result.jsonl \
  --model-sha256 910c01816ad1b75d4cf958e7eb33ab730a3f0a2127c1b4606e1900901509161f
```

公开主口径为 NFC 规范化并删除 Unicode 空白后的语料级 CER。`analyze_submission_eval.py` 输出的 Raw、去空白和 NFKC NED 用于诊断，不替代主成绩；最终公开汇总与图表由 `build_evaluation_figures.py` 生成，当前锁定结果见 [evaluation_metrics.json](../docs/evaluation_metrics.json)。

## 相关目录

- 本地单图 OCR 演示：[demo](../demo/)。`demo/infer_single_image.py` 跑单张图片 OCR。

评估脚本中的输出风险字段仅用于审计复核，不会自动改写预测文本。
