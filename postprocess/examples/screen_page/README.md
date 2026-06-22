# 后处理示例：合并行结果与添加注音

这个示例只展示 OCR 后处理，不负责切图。

输入是切图后逐行 OCR 的 JSONL，以及切图阶段生成的 `index.csv`。后处理做两件事：

```text
line_ocr_result_sample.jsonl + crop_index_sample.csv
-> merge_line_ocr_results.py 合并为页面文本
-> add_nuosu_pronunciation.py 添加规范彝文注音
```

## 合并行 OCR 结果

```bash
python postprocess/merge_line_ocr_results.py \
  --results postprocess/examples/screen_page/line_ocr_result_sample.jsonl \
  --index postprocess/examples/screen_page/crop_index_sample.csv \
  --out-jsonl outputs/postprocess_demo/merged_page_text.jsonl \
  --out-txt-dir outputs/postprocess_demo/page_text \
  --separator ""
```

如果希望保留切行换行，可以去掉 `--separator ""`。

查看小样：

- 输入行 OCR：[`line_ocr_result_sample.jsonl`](line_ocr_result_sample.jsonl)
- 输入索引：[`crop_index_sample.csv`](crop_index_sample.csv)
- 合并 JSONL：[`merged_page_text_sample.jsonl`](merged_page_text_sample.jsonl)
- 合并文本小样：[`sample_merged_text.txt`](sample_merged_text.txt)

## 添加注音

```bash
python postprocess/add_nuosu_pronunciation.py \
  --input outputs/postprocess_demo/merged_page_text.jsonl \
  --field text \
  --output outputs/postprocess_demo/merged_page_text_pronounced.jsonl
```

查看小样：

- 注音 JSONL：[`pronounced_page_text_sample.jsonl`](pronounced_page_text_sample.jsonl)
- 注音文本小样：[`sample_pronunciation.txt`](sample_pronunciation.txt)

注音使用 [`postprocess/nuosu_unicode.csv`](../../nuosu_unicode.csv)。
