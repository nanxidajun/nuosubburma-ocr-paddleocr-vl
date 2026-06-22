# 切图示例：页面照片

这个示例只展示一键切图 pipeline：

```text
页面照片
-> crop_pipeline/run.py 切图
-> 生成可送入 OCR 的行图
```

切图后的 OCR 结果合并、注音添加属于后处理流程，见 [`postprocess/`](../../../postprocess/)。

## 样例图

这是一张真实页面照片，带人工 GT，用来展示从整页图切成行图的流程。

![页面照片样例](screen_page_with_gt.jpg)

人工 GT：[`screen_page_gt.txt`](screen_page_gt.txt)

## 切图结果预览

下面两张图是直接用本目录样例图跑 `crop_pipeline/run.py` 得到的结果，不是示意图。

检测框预览：

<img src="preview/01_detected_boxes.png" alt="detected boxes" width="420">

切好的行图拼接预览：

<img src="preview/02_cut_sheet.png" alt="cut sheet" width="760">

这次切图生成了 `27` 个汇总文件，`27` 个全部进入 `01_line_ocr_ready/`，校验结果为 `ok: true`。

可查看文件：

- 切图索引：[`preview/crop_index.csv`](preview/crop_index.csv)
- 切图校验：[`preview/crop_pipeline_validation.json`](preview/crop_pipeline_validation.json)

## 运行切图

```bash
mkdir -p outputs/screen_page_input
cp crop_pipeline/examples/screen_page/screen_page_with_gt.jpg outputs/screen_page_input/

python3 crop_pipeline/run.py \
  --input outputs/screen_page_input \
  --output-root outputs/screen_page_crop
```

先看切图是否合理：

```text
outputs/screen_page_crop/03_cut_before_after_review/
```

可进入 OCR 的行图在：

```text
outputs/screen_page_crop/04_successful_crop_summary/01_line_ocr_ready/
```
