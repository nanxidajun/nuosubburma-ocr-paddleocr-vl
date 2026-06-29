# 脚本

本目录只保留训练、评估和统计复现需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集运行 OCR 推理。
- `smoke_check.sh`：安装后健康检查；检查依赖和样例图，本地有模型时跑一张单图 OCR。
- `run_eval.sh`：Paddle distributed launch 的评估封装。
- `run_train_lora.sh`：训练命令封装。
- `analyze_submission_eval.py`：计算 NED、分组 NED 和复核表；同时统计 replacement、LaTeX-like、extra Latin、long_pred 等输出风险。

评估/训练依赖包括 `paddle`、`paddleformers`、`Pillow`、`tqdm` 和 `python-Levenshtein`。

安装后可先跑一次健康检查：

```bash
scripts/smoke_check.sh
```

如果模型不在默认目录，可指定：

```bash
MODEL_PATH=/path/to/NuosuBburma-OCR scripts/smoke_check.sh
```

## 运行评估

先下载模型和评估集，默认路径如下：

```text
models/NuosuBburma-OCR
datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl
```

然后运行：

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl
```

生成分组统计和风险审计：

```bash
python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```

`run_eval.sh` 默认使用 `CUDA_VISIBLE_DEVICES=0`。如需指定 GPU：

```bash
CUDA_VISIBLE_DEVICES=1 scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl
```

页面切割流程已单独放到一级目录，见 [页面切割流程](../page_processing/)。

本地 demo 见 [demo](../demo/)。`demo/infer_single_image.py` 用于单张图片 OCR。

`demo/run_page_workflow.py` 用于整页流程：页面切割、OCR、调用 `page_processing/assemble_pages.py` 做页面文本合并、异常审计和可选注音。

OCR 之后的注音添加见 [后处理工具](../postprocess/)。评估脚本中的输出风险字段只用于审计和复核，不会自动改写模型预测文本。
