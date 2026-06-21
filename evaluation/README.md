# 评估结果

本目录存放 `NuosuBburma OCR` 提交评估集的评估产物。

```text
NuosuBburma_OCR_Evaluation_Set/
  submission_model_result.jsonl
  submission_model_eval.log
  summary.md
  summary.json
  by_source.csv
  by_sample_type.csv
  by_script_mix.csv
  by_difficulty.csv
  by_has_digit.csv
  by_scene.csv
  danger_rows.csv
  all_scored_rows.csv
  final_train_v5_16.log
```

主结果：

```text
Avg NED: 0.036068
samples: see summary.json
```

重新生成统计：

```bash
python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result evaluation/NuosuBburma_OCR_Evaluation_Set/submission_model_result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```
