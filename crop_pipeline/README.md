# 切图 Pipeline

本目录是 `NuosuBburma OCR` 的整页/页面切图入口。用户只需要调用 `run.py`，其余脚本是内部步骤。

支持输入：

- 图片文件夹。
- 单张图片。
- 单个 PDF。

它对应一个实用工作流：

```text
整页图片 / PDF
-> 切成可复核行图
-> 批量 OCR
-> 合并回页面文本
-> 给规范彝文输出添加注音
```

## 一键运行

```bash
python3 crop_pipeline/run.py \
  --input page_images \
  --output-root outputs/crop_pipeline_demo
```

输出目录：

```text
outputs/crop_pipeline_demo/
  01_v3_routing/                    # 页面级粗分流
  02_v4_secondary_split/            # 大块 region 的二次切分
  03_cut_before_after_review/       # 给人看的切图前后对照
  04_successful_crop_summary/       # 给 OCR/标注/训练使用的切图汇总
  crop_pipeline_validation.json     # 切图索引校验结果
  page_manifest_template.csv        # 自动生成的页型清单模板
  run_summary.md                    # 本次运行摘要
```

最常看的两个入口：

- `03_cut_before_after_review/`：检查切图是否合理。
- `04_successful_crop_summary/01_line_ocr_ready/`：可送入 OCR 的行图。

## 屏幕图快速示例

```bash
mkdir -p outputs/screen_page_input
cp demo/sample_images/screen_page.jpg outputs/screen_page_input/

python3 crop_pipeline/run.py \
  --input outputs/screen_page_input \
  --output-root outputs/screen_page_crop
```

再从下面目录中选择行图做 OCR：

```text
outputs/screen_page_crop/04_successful_crop_summary/01_line_ocr_ready/
```

切图示例见 [`examples/screen_page/`](examples/screen_page/)。

## 配套脚本

- `run.py`：把图片文件夹、单张图片或 PDF 切成可复核行图。
- `infer_line_crops.py`：批量识别 `04_successful_crop_summary/01_line_ocr_ready/` 中的行图。

合并切行识别结果、添加彝文注音属于后处理流程，见 [`../postprocess/`](../postprocess/)。

## PDF 输入

PDF 可以直接输入，pipeline 会先把 PDF 渲染到 `00_input_pages/`，再继续切图：

```bash
python3 crop_pipeline/run.py \
  --input book.pdf \
  --output-root outputs/book_crop \
  --pdf-dpi 220 \
  --max-pages 20
```

说明：

- `--max-pages 20` 是默认值，避免误把整本大 PDF 一次性渲染到磁盘。
- 如需渲染全部页面，设置 `--max-pages 0`。
- PDF 输入依赖 Poppler 的 `pdftoppm`。

## 页型清单

新书页文件名不稳定时，建议使用 `--page-manifest`：

```bash
python3 crop_pipeline/run.py \
  --input page_images \
  --output-root outputs/crop_pipeline_demo \
  --page-manifest page_manifest.csv
```

`page_manifest.csv` 格式：

```csv
file,page_hint,note
page_001.png,body_page,
page_002.png,toc,
page_003.png,mixed_page,
```

支持的 `page_hint`：

- `body_page`：普通正文页。
- `toc`：目录页。
- `mixed_page`：正文混排页，例如彝文+注音/汉语。
- `mixed_cover_page`：混排封面或标题页。
- `cover_or_low_quality`：封面、低质量页、非正文页。

## 依赖

切图流程额外依赖：

```bash
pip install opencv-python numpy
```

如果要直接处理 PDF，还需要安装 Poppler：

```bash
brew install poppler
```

完整说明见 [`../docs/CROP_PIPELINE.md`](../docs/CROP_PIPELINE.md)。
