# 页面切割流程说明

本项目只有一条页面切割流程：使用 Paddle 的 `PP-DocLayout` 版面检测模型对整页图片或 PDF 做页面切割，得到 OCR 单元和阅读顺序。Hugging Face Space 是在线交互入口，本地 `demo/run_page_workflow.py` 是命令行入口，二者讲的是同一件事。

## 流程

```text
整页图片 / PDF / 页面照片 / 屏幕拍照
-> PP-DocLayout 页面切割
-> 生成 OCR 单元和 reading_order
-> OCR 单元识别
-> 页面文本合并
-> 异常审计
-> 可选注音
```

## 本地运行

```bash
python page_processing/run.py \
  --input "/path/to/page_or_pdf" \
  --output-root "outputs/page_cutting_demo"
```

完整 demo：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --with-pronunciation
```

## 页面切割输出

```text
outputs/page_cutting_demo/
  00_input_pages/
  01_doclayout/
  02_ocr_units/
  03_cut_review/
  page_processing_validation.json
  run_summary.md
  README.md
```

| 输出 | 用途 |
|---|---|
| `00_input_pages/` | 本次使用的页面图片；单图和 PDF 会先复制或渲染到这里 |
| `01_doclayout/` | `PP-DocLayout` 原始结果和版面块统计 |
| `02_ocr_units/index.csv` | OCR 单元索引，记录 `crop_id`、`page_id`、图片路径和 `reading_order` |
| `03_cut_review/` | 人工检查用的页面检测框和文本块预览 |
| `page_processing_validation.json` | 检查 OCR 单元是否缺图、`crop_id` 是否重复等基础问题 |
| `run_summary.md` | 本次处理的页数、OCR 单元数量和分组数量 |

## OCR 单元索引

`02_ocr_units/index.csv` 是后续 OCR 的桥。核心字段如下：

| 字段 | 说明 |
|---|---|
| `crop_id` | OCR 单元唯一 ID |
| `page_id` | 原页面 ID |
| `page_file` | 原页面文件名 |
| `summary_path` | 文本块图片相对路径 |
| `role` | 版面检测后映射的块类型，如 `body`、`title`、`footnote` |
| `reading_order` | 页面文本合并时使用的阅读顺序 |
| `bbox` | 版面检测框 |
| `crop_bbox` | 加边距后的实际裁剪框 |

## 为什么需要页面切割

复杂整页直接 OCR 时，模型可能出现漏行、跨行、换行不稳定、页码/脚注/正文边界混乱等问题。页面切割把整页先变成可检查的 OCR 单元，再按 `reading_order` 合并页面文本，便于人工复核和异常定位。

## 《雪族子史篇》整页对比案例

以评估集中的《雪族子史篇》全书 65 页整页样本为对象，我们对比了两种识别路径：整页图像直接进入 OCR 模型，以及先用 Paddle 的 `PP-DocLayout` 版面检测模型生成 OCR 单元、再识别并合并页面文本。

| 识别路径 | Avg NED | 说明 |
|---|---:|---|
| 页面切割后识别 | `0.0654` | 阅读顺序更稳，彝汉配对更接近 GT，非文字干扰更少 |
| 直接整页 OCR | `0.5540` | 容易出现跨行、错行、彝汉配对拆散和花纹误识别 |

NED 下降主要来自三点：第一，页面切割减少阅读顺序错位、跨行和页码混入正文；第二，更小的 OCR 单元让彝汉混排、标点和注释的局部对应关系更稳定；第三，版面检测可以减少花纹、边框和噪声等非文字区域被误识别成文字。

该组样本已纳入最终评估集，GitHub 只报告同口径摘要，不重复提交页面材料。

## 依赖

页面切割使用 `requirements.txt` 中的：

```text
paddleocr==3.4.0
```

默认版面检测模型：

```text
PP-DocLayout
```

PDF 输入还需要 Poppler：

```bash
brew install poppler
```

## 边界

页面切割不等于自动校对。它只负责把页面转成可识别、可追踪、可复核的 OCR 单元。严重倾斜、反光、遮挡、弯曲或低清页面仍可能切割不完整；这种情况应查看 `03_cut_review/` 和 demo 的异常提示，再决定是否复拍、复跑或改用直接识别对照。
