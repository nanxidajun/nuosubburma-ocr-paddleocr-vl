# 评估结果

本目录存放 `NuosuBburma OCR` 的 clean603 评估产物。

```text
clean603/
  v516_clean603_result.jsonl
  v516_clean603_eval.log
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
samples: 603
```

重新生成统计：

```bash
python scripts/analyze_clean603_eval.py \
  --annotations data/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result evaluation/clean603/v516_clean603_result.jsonl \
  --out-dir outputs/clean603_analysis
```
