# 后处理工具

本目录只保留 OCR 之后的轻量文本工具，不负责页面切割，也不改写 OCR 正文。

## 注音

`add_nuosu_pronunciation.py` 使用 `nuosu_unicode.csv` 给规范彝文字添加罗马注音。它会在已有 OCR 文本旁新增字段，便于检字、校对和语料整理。

典型用法：

```bash
python postprocess/add_nuosu_pronunciation.py \
  --input outputs/demo_page_workflow/03_page_text/submission_pages.jsonl \
  --field text \
  --output outputs/demo_page_workflow/03_page_text/submission_pages_pronounced.jsonl
```

脚本会新增：

| 字段 | 说明 |
|---|---|
| `pronunciation` | 按字符顺序生成的注音文本 |
| `inline_pronunciation` | 形如 `ꆈ(nuo)ꌠ(su)` 的内联注音 |

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

## 边界

注音是 OCR 后处理，不参与模型评分，也不会把模型预测文本改成标准答案。需要定位空结果、局部识别失败或异常长输出时，看评估脚本和 demo 生成的异常审计文件。
