# 页面切割流程

本目录只有一个页面切割入口：`run.py`。它使用 Paddle 的 `PP-DocLayout` 版面检测模型对整页图片或 PDF 做页面切割，生成可送入 OCR 的文本块，并保留 `page_id`、`crop_id`、`reading_order` 等字段，供后续 OCR、页面文本合并、异常审计和可选注音使用。

## 一键运行

```bash
python page_processing/run.py \
  --input demo/sample_images/screen_page.jpg \
  --output-root outputs/page_cutting_demo
```

支持输入：

| 输入 | 说明 |
|---|---|
| 单张图片 | 适合页面照片、屏幕拍照、扫描页 |
| 图片文件夹 | 适合一批书页或评估样本 |
| PDF | 先渲染为页面图片，再进入同一条页面切割流程 |

## 输出

```text
outputs/page_cutting_demo/
  00_input_pages/                 输入页面副本，超大图会按参数压缩
  01_doclayout/                   PP-DocLayout 原始结果和版面块统计
  02_ocr_units/                   可送入 OCR 的文本块图片和 index.csv
  03_cut_review/                  每页原图、检测框和文本块预览
  page_processing_validation.json 基础校验报告
  run_summary.md                  本次运行摘要
```

最常看的两个入口：

| 入口 | 用途 |
|---|---|
| `03_cut_review/` | 人工检查页面切割是否合理 |
| `02_ocr_units/index.csv` | 下游 OCR 读取的索引，包含图片路径、阅读顺序和页面来源 |

## 接本地 OCR demo

整页、页面照片、拍屏或 PDF 建议直接跑完整 demo：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --with-pronunciation
```

这条命令会按同一条流程完成：

```text
页面切割
-> OCR 单元识别
-> 页面文本合并
-> 异常审计
-> 可选注音
```

如果已经跑过页面切割，也可以复用切割结果：

```bash
python demo/run_page_workflow.py \
  --page-root outputs/page_cutting_demo \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow
```

## PDF 输入

```bash
python page_processing/run.py \
  --input book.pdf \
  --output-root outputs/book_page_cutting \
  --pdf-dpi 220 \
  --max-pages 20
```

说明：

| 参数 | 作用 |
|---|---|
| `--pdf-dpi 220` | PDF 渲染清晰度 |
| `--max-pages 20` | 默认最多渲染 20 页，避免误把大 PDF 一次性写满磁盘 |
| `--max-pages 0` | 渲染全部页面 |
| `--max-image-side 2400` | 超大图片压缩到长边不超过 2400，提高处理速度 |

PDF 输入需要本机安装 Poppler：

```bash
brew install poppler
```

## 依赖

页面切割使用 `requirements.txt` 中的 `paddleocr==3.4.0`，默认模型名为 `PP-DocLayout`。

```bash
python -m pip install -r requirements.txt
```

如需指定设备或模型：

```bash
python page_processing/run.py \
  --input demo/sample_images/screen_page.jpg \
  --output-root outputs/page_cutting_demo \
  --device gpu \
  --layout-model PP-DocLayout
```

## 边界

页面切割用于降低复杂整页直接 OCR 的漏行、错行和阅读顺序风险，但它不自动修改 OCR 文本。切割后仍建议查看 `03_cut_review/`；如果页面严重倾斜、反光、遮挡、弯曲或文字被拍糊，异常审计可能提示复跑或改用另一种识别方式对照。
