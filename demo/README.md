# Demo

本目录提供本地 demo。Hugging Face Space 是线上入口；没有配置 Space GPU 时，模型推理、页面切割和批量评估以本地脚本为准。

本地 demo 分两类，按输入复杂度选择：

| 场景 | 使用脚本 | 输出 |
|---|---|---|
| 行图、区域图、标牌、简单页面 | `infer_single_image.py` | OCR 文本，可选 HTML 复核页 |
| 整页、PDF、页面照片、屏幕拍照 | `run_page_workflow.py` | 页面切割、OCR 单元、页面文本、异常审计、HTML 复核页 |

## 先安装依赖

在仓库根目录执行：

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 顶部写有推荐环境和 PaddlePaddle 安装命令。模型推理建议使用 CUDA GPU 环境。

## 先下载模型

在仓库根目录执行：

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

国内网络较慢时，可先设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

安装和下载完成后，可先跑一次健康检查：

```bash
scripts/smoke_check.sh
```

## 单张图片识别

默认样例：

```bash
python demo/infer_single_image.py \
  --max-image-side 2400 \
  --html-output outputs/demo/mixed_line.html
```

这条命令默认使用：

```text
模型目录：models/NuosuBburma-OCR
样例图片：demo/sample_images/mixed_line.png
提示词：<image>OCR:
设备：gpu
长边限制：2400
```

换自己的图片：

```bash
python demo/infer_single_image.py \
  --image /path/to/your_image.jpg \
  --max-image-side 2400
```

如果模型放在其他位置：

```bash
python demo/infer_single_image.py \
  --model /path/to/NuosuBburma-OCR \
  --image /path/to/your_image.jpg \
  --max-image-side 2400
```

保存文本结果：

```bash
python demo/infer_single_image.py \
  --image demo/sample_images/mixed_line.png \
  --max-image-side 2400 \
  --output outputs/demo/mixed_line.txt
```

生成本地 HTML 预览：

```bash
python demo/infer_single_image.py \
  --image demo/sample_images/mixed_line.png \
  --max-image-side 2400 \
  --html-output outputs/demo/mixed_line.html
```

HTML 会把图片和识别文本放在同一个页面里，便于人工复核。它只是 demo 预览，不替代正式评估结果。

`--max-image-side` 用来限制大图长边，默认 `2400`。超规格图片会先等比例压缩再进入 OCR，避免单张图过大导致推理变慢或显存压力过高；如果确实要保留原图，可设为 `0`。

## 整页图片识别

整页、页面照片、拍屏或 PDF 建议走页面切割后识别：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --max-image-side 2400 \
  --with-pronunciation
```

这条命令会按同一条流程执行：

```text
整页图片 / PDF
-> 页面切割，生成 OCR 单元和阅读顺序
-> OCR 单元识别
-> 页面文本合并
-> 异常审计
-> 可选注音
```

整页 demo 的 `--max-image-side` 会传给页面切割步骤。超规格页面会先等比例压缩，再用 `PP-DocLayout` 做页面切割。

主要输出：

| 输出 | 说明 |
|---|---|
| `outputs/demo_page_workflow/01_page_cutting/` | 页面切割输出和索引 |
| `outputs/demo_page_workflow/02_ocr_units/ocr_units_results.jsonl` | OCR 单元识别结果 |
| `outputs/demo_page_workflow/03_page_text/submission_pages.jsonl` | 页面文本结果 |
| `outputs/demo_page_workflow/03_page_text/submission_pages.md` | 便于人工阅读的页面文本 |
| `outputs/demo_page_workflow/03_page_text/submission_pages.html` | 本地 HTML 复核页，展示异常摘要、页面文本和 OCR 单元小图 |
| `outputs/demo_page_workflow/03_page_text/audit_summary.json` | 空结果、异常状态、重复页等自动审计摘要 |
| `outputs/demo_page_workflow/03_page_text/page_audit.csv` | 逐页审计表 |
| `outputs/demo_page_workflow/03_page_text/submission_pages_pronounced.jsonl` | 使用 `--with-pronunciation` 时生成的注音结果 |

如果已经有页面切割输出或 OCR 结果，可以复用中间结果：

```bash
python demo/run_page_workflow.py \
  --page-root outputs/demo_page_workflow/01_page_cutting \
  --ocr-results outputs/demo_page_workflow/02_ocr_units/ocr_units_results.jsonl \
  --output-root outputs/demo_page_workflow \
  --with-pronunciation
```

完整页面切割说明见 [页面切割流程](../page_processing/)。

## 注音和异常审计

注音是 OCR 后处理，不改写 OCR 正文。单张图片 demo 只输出 OCR 正文；整页 demo 可用 `--with-pronunciation` 给页面文本添加注音字段。

整页 demo 会额外生成异常审计文件和 HTML 摘要，用于提示空结果、局部识别失败、替换符、重复页和是否需要复核。审计结果只用于定位风险，不自动修改 OCR 文本。

## 三步快速检查

1. 下载模型。

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

2. 跑单图，打开 `outputs/demo/mixed_line.html`。

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png \
  --max-image-side 2400 \
  --html-output outputs/demo/mixed_line.html
```

3. 跑整页，打开 `outputs/demo_page_workflow/03_page_text/submission_pages.html`。

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --max-image-side 2400 \
  --with-pronunciation
```

## 样例图

样例图只用于 demo 体验；正式指标以评估集为准。

| 文件 | 用途 |
|---|---|
| `sample_images/mixed_line.png` | 彝汉混排行图，默认 demo 图片 |
| `sample_images/handwriting_region.jpg` | 手写或区域样例 |
| `sample_images/sign_photo.jpg` | 实拍标牌样例 |
| `sample_images/screen_page.jpg` | 整页/拍屏样例，用于页面切割后识别 |

## 与其他脚本的区别

| 入口 | 用途 |
|---|---|
| `scripts/smoke_check.sh` | 安装后健康检查：依赖、样例图、模型目录是否可用 |
| `demo/infer_single_image.py` | 本地单张图片 OCR 体验 |
| `demo/run_page_workflow.py` | 本地整页 OCR 流程复现 |
| `scripts/run_eval.sh` | 冻结评估集上的批量评估 |
