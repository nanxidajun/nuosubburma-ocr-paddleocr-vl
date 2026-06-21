# 数据

本目录存放 `NuosuBburma OCR` 的 真实数据评估集。

```text
NuosuBburma_OCR_Evaluation_Set/
  images/
  annotations.jsonl
  samples.csv
  source_summary.csv
  dataset_summary.json
  digit_summary.csv
  excluded_samples.csv
  review.html
  README.md
```

当前主评分评估集包含 603 条样本和 603 张被引用图片。

JSONL 使用 PaddleOCR-VL messages 格式：

```json
{
  "id": "sample_id",
  "images": ["images/sample.png"],
  "messages": [
    {"role": "user", "content": "<image>OCR:"},
    {"role": "assistant", "content": "ground truth text"}
  ],
  "meta": {}
}
```

书籍样本来自扫描件裁切；真实手写、屏幕页面和真实照片为用户采集样本。
