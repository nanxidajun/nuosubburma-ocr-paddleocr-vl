# 端到端示例：屏幕页

这个示例使用一张带人工 GT 的屏幕页，展示完整链路：

```text
屏幕页图片
-> crop_pipeline/run.py 切图
-> crop_pipeline/infer_line_crops.py 识别行图
-> postprocess/merge_line_ocr_results.py 合并页面文本
-> postprocess/add_nuosu_pronunciation.py 添加注音
```

## 样例图

这是一张真实屏幕页截图，带人工 GT，用来展示从整页图到可校对文本的完整流程。

![屏幕页样例](screen_page_with_gt.jpg)

人工 GT：[`screen_page_gt.txt`](screen_page_gt.txt)

## 1. 切图

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

## 2. 识别切行图

```bash
python crop_pipeline/infer_line_crops.py \
  --model models/NuosuBburma-OCR \
  --index outputs/screen_page_crop/04_successful_crop_summary/index.csv \
  --summary-root outputs/screen_page_crop/04_successful_crop_summary \
  --output outputs/screen_page_crop/line_ocr_result.jsonl
```

## 3. 合并回一段页面文本

```bash
python postprocess/merge_line_ocr_results.py \
  --results outputs/screen_page_crop/line_ocr_result.jsonl \
  --index outputs/screen_page_crop/04_successful_crop_summary/index.csv \
  --out-jsonl outputs/screen_page_crop/page_ocr_merged.jsonl \
  --out-txt-dir outputs/screen_page_crop/page_text \
  --separator ""
```

如果想保留原切行换行，可以去掉 `--separator ""`。

## 4. 添加注音

```bash
python postprocess/add_nuosu_pronunciation.py \
  --input outputs/screen_page_crop/page_ocr_merged.jsonl \
  --field text \
  --output outputs/screen_page_crop/page_ocr_merged_pronounced.jsonl
```

## 5. 对照 GT

```bash
cat crop_pipeline/examples/screen_page/screen_page_gt.txt
cat outputs/screen_page_crop/page_text/*.txt
```
