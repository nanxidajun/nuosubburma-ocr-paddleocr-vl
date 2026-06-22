# 后处理工具

本目录保存切图后 OCR 的轻量后处理脚本，不依赖模型权重。

## 合并切行识别结果

`merge_line_ocr_results.py` 用于把切图 pipeline 输出的多张行图识别结果，按页面和阅读顺序合并回整页文本。

典型用法：

```bash
python postprocess/merge_line_ocr_results.py \
  --results outputs/line_ocr_result.jsonl \
  --index outputs/crop_pipeline_demo/04_successful_crop_summary/index.csv \
  --out-jsonl outputs/page_ocr_merged.jsonl \
  --out-txt-dir outputs/page_ocr_text
```

说明：

- `--results` 是行图 OCR 结果，支持 JSONL 或 JSON list。
- `--index` 是 `04_successful_crop_summary/index.csv`，用于恢复页面、父框、二次切分行顺序。
- 输出 JSONL 每行是一页，包含 `page_id`、`page_file`、`text` 和原始 `lines`。

## 给识别结果加注音

`add_nuosu_pronunciation.py` 使用 `nuosu_unicode.csv` 给规范彝文字添加罗马注音。

典型用法：

```bash
python postprocess/add_nuosu_pronunciation.py \
  --input outputs/page_ocr_merged.jsonl \
  --field text \
  --output outputs/page_ocr_merged_pronounced.jsonl
```

脚本会为每条记录新增：

- `pronunciation`：按字符顺序生成的注音文本。
- `inline_pronunciation`：形如 `ꆈ(nuo)ꌠ(su)` 的内联注音。

如果输入是纯文本，也可以直接处理：

```bash
python postprocess/add_nuosu_pronunciation.py \
  --input input.txt \
  --output output_pronounced.txt
```

## 字表

`nuosu_unicode.csv` 包含 Unicode Yi Syllables 区的 1165 个规范彝文字：

```csv
codepoint,char,unicode_name,romanization
U+A000,ꀀ,Yi Syllable It,it
```

