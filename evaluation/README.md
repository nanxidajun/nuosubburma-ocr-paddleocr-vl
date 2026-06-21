# 评估结果

本目录存放 `NuosuBburma OCR` 在提交评估集上的公开评估结果。

结果看板：

- [NuosuBburma OCR Evaluation Set](NuosuBburma_OCR_Evaluation_Set/README.md)

主结果：

| 指标 | 值 |
|---|---:|
| Samples | 603 |
| Avg NED | 0.036068 |
| Exact match | 67.99% |
| Yi-only exact | 74.96% |
| Han-only exact | 93.99% |
| replacement / LaTeX / long_pred | 0 / 2 / 0 |

公开结果包只保留摘要、图表、分组统计和逐条模型输出。训练日志、运行日志和人工审查中间表不放入公开目录。

重新生成统计：

```bash
python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result evaluation/NuosuBburma_OCR_Evaluation_Set/raw/submission_model_result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```
