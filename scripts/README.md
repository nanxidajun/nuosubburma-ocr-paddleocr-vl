# 脚本

本目录只保留推理、评估和统计需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集运行 OCR 推理。
- `smoke_check.sh`：安装后健康检查；检查依赖和样例图，本地有模型时跑一张单图 OCR。
- `run_eval.sh`：Paddle distributed launch 的评估封装。
- `analyze_submission_eval.py`：计算 NED、分组 NED 和复核表；同时统计 replacement、LaTeX-like、extra Latin、long_pred 等输出风险。
- `split_eval_for_final_routes.py`：把最新评估集拆成直接 OCR 路线和 page workflow 路线。
- `page_workflow_to_eval_result.py`：把页面切割拼合结果转成可打分的评估 JSONL。
- `merge_final_route_results.py`：把直接 OCR 和 page workflow 两路结果合并成最终全量评估 JSONL。

评估依赖包括 `paddle`、`paddleformers`、`Pillow`、`tqdm` 和 `python-Levenshtein`。

安装后可先跑一次健康检查：

```bash
scripts/smoke_check.sh
```

如果模型不在默认目录，可指定：

```bash
MODEL_PATH=/path/to/NuosuBburma-OCR scripts/smoke_check.sh
```

## 运行最终评估

先下载模型和评估集，默认路径如下：

```text
models/NuosuBburma-OCR
datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl
```

最终评估主口径是完整评估集的系统总分。执行时按样本类型走两条路线，最后合并成一个全量结果再打分：

| 路线 | 样本 | 跑法 |
|---|---|---|
| 直接 OCR | `line` / `region` | 样本图直接进模型，输出一条预测文本 |
| 页面 workflow | `page` | 页面切割 -> OCR 单元识别 -> 页面文本拼合，输出一条页级预测文本 |

先拆分评估集：

```bash
python scripts/split_eval_for_final_routes.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --out-dir outputs/final_eval_routes \
  --copy-mode symlink
```

运行 `line` / `region` 直接 OCR：

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  outputs/final_eval_routes/direct/annotations.jsonl \
  outputs/final_eval_routes/direct_result.jsonl
```

`run_eval.sh` 默认使用 `CUDA_VISIBLE_DEVICES=0`。如需指定 GPU：

```bash
CUDA_VISIBLE_DEVICES=1 scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  outputs/final_eval_routes/direct/annotations.jsonl \
  outputs/final_eval_routes/direct_result.jsonl
```

运行 `page` 页面 workflow：

```bash
python demo/run_page_workflow.py \
  --input outputs/final_eval_routes/page/images \
  --model models/NuosuBburma-OCR \
  --output-root outputs/final_eval_routes/page_workflow \
  --device gpu \
  --max-new-tokens 2048 \
  --max-pages 0
```

把拼合后的页级文本转成评估结果：

```bash
python scripts/page_workflow_to_eval_result.py \
  --annotations outputs/final_eval_routes/page/annotations.jsonl \
  --assembled-pages outputs/final_eval_routes/page_workflow/03_page_text/submission_pages.jsonl \
  --output outputs/final_eval_routes/page_workflow_result.jsonl
```

合并两路输出，得到最终系统结果：

```bash
python scripts/merge_final_route_results.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --direct-result outputs/final_eval_routes/direct_result.jsonl \
  --page-result outputs/final_eval_routes/page_workflow_result.jsonl \
  --output outputs/final_eval_routes/final_system_result_1030.jsonl
```

对完整评估集打主分：

```bash
python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/final_eval_routes/final_system_result_1030.jsonl \
  --out-dir outputs/final_eval_routes/final_system_analysis \
  --title "NuosuBburma OCR final system: full evaluation set"
```

需要定位问题时，再分别生成 direct 和 page 分表：

```bash
python scripts/analyze_submission_eval.py \
  --annotations outputs/final_eval_routes/direct/annotations.jsonl \
  --result outputs/final_eval_routes/direct_result.jsonl \
  --out-dir outputs/final_eval_routes/direct_analysis \
  --title "NuosuBburma OCR direct route: line/region"

python scripts/analyze_submission_eval.py \
  --annotations outputs/final_eval_routes/page/annotations.jsonl \
  --result outputs/final_eval_routes/page_workflow_result.jsonl \
  --out-dir outputs/final_eval_routes/page_workflow_analysis \
  --title "NuosuBburma OCR page route: DocLayout + OCR + assembly"
```

这三个分数的关系是：`final_system_analysis` 是主结果；direct 和 page 分表只用于解释哪类输入拉高或拉低总分。

页面切割流程已单独放到一级目录，见 [页面切割流程](../page_processing/)。

本地 demo 见 [demo](../demo/)。`demo/infer_single_image.py` 用于单张图片 OCR。

`demo/run_page_workflow.py` 用于整页流程：页面切割、OCR、调用 `page_processing/assemble_pages.py` 做页面文本合并、异常审计和可选注音。

OCR 之后的注音添加见 [后处理工具](../postprocess/)。评估脚本中的输出风险字段只用于审计和复核，不会自动改写模型预测文本。
