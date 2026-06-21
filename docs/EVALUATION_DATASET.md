# 评估集说明

本文档说明 `NuosuBburma OCR` 仓库中随附的 clean 评估集。

## 目标

评估集用于检查模型是否能够处理真实规范彝文 OCR 场景，而不是只记住某一本书或某一种合成风格。

覆盖范围：

- 纯彝文文本。
- 彝汉混排文本。
- 老印刷材料。
- 单行 OCR。
- 少量 region/page OCR。
- 有限真实手写样本。
- 真实材料中出现的标点、数字和脚注符号。

## 数据包结构

```text
data/NuosuBburma_OCR_Evaluation_Set/
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

规模：

- 主评分样本：603 条。
- 引用图片：603 张。
- 空 GT：0 条。
- 占位符 GT：0 条。
- 来源包括书籍扫描件、真实手写、真实照片和屏幕页面。

## 标注格式

评估集使用 PaddleOCR-VL 的 messages JSONL 格式：

```json
{
  "id": "gen_yu_hua_line_000001",
  "images": ["images/gen_yu_hua_line_000001.png"],
  "messages": [
    {"role": "user", "content": "<image>OCR:"},
    {"role": "assistant", "content": "ground truth text"}
  ],
  "meta": {
    "source_name": "根与花",
    "source_code": "gen_yu_hua",
    "sample_type": "line",
    "script_mix": "yi",
    "difficulty": "easy"
  }
}
```

## 评价指标

主指标：

- NED，归一化编辑距离，越低越好。

辅助诊断：

- Yi-only NED / exact。
- Han-only NED / exact。
- 标点、数字、空格、换行差异。
- Latin/ASCII 漂移。
- LaTeX-like 或公式化幻觉。
- 超长输出。
- replacement collapse。

## 评估集规则

- 评估样本不作为训练目标。
- 样本保留来源、版式、难度和混排类型信息。
- 真实手写作为高难度子场景单独解释。
- 单行 OCR 与 region/page OCR 不混为同一种能力。

## 最终重跑

最终 clean603 评估结果位于：

```text
evaluation/clean603/
```

摘要：

| 指标 | 值 |
|---|---:|
| 样本数 | 603 |
| Avg NED | 0.036068 |
| Exact match | 67.99% |
| Yi-only NED | 0.038309 |
| Yi-only exact | 74.96% |
| Han-only NED | 0.022447 |
| Han-only exact | 93.99% |
| replacement collapse | 0 |
| long prediction failure | 0 |
| LaTeX-like outputs | 2 |
