# 页面切割流程说明

本项目只有一条页面切割、拼合与结构化流程：使用 Paddle DocLayout 对整页图片或 PDF 生成候选版面块，所有候选块都必须进入统一后处理，再得到识别单元、角色、阅读顺序和位置框；识别后统一由 `page_processing/assemble_pages.py` 做页面文本拼合，再由 `page_processing/structure_pages.py` 导出可复核的页面结构。线上演示是交互入口，本地 `demo/run_page_workflow.py` 是命令行入口。

## 流程

```text
整页图片 / PDF / 页面照片 / 屏幕拍照
-> Paddle DocLayout 候选版面块
-> 统一后处理：去边缘、去重、按视觉行/小区域细分
-> 生成识别单元、角色、阅读顺序和 bbox
-> 文本区域识别
-> 页面文本合并
-> 结构化页面输出
-> 异常检查
-> 可选注音
```

## 本地运行

```bash
python page_processing/run.py \
  --input "/path/to/page_or_pdf" \
  --output-root "outputs/page_cutting_demo"
```

完整演示：

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
| `01_doclayout/` | Paddle DocLayout 候选结果和版面块统计 |
| `02_ocr_units/index.csv` | 后处理后的识别单元索引，记录裁切编号、页面编号、图片路径、角色、角色原因、阅读顺序、父级候选框和识别单元位置 |
| `03_cut_review/` | 人工检查用的候选框、后处理单元和文本块预览 |
| `page_processing_validation.json` | 检查识别单元是否缺图、裁切编号是否重复等基础问题 |
| `run_summary.md` | 本次处理的页数、识别单元数量和分组数量 |

`03_cut_review/*/01_doclayout_boxes.png` 用来看 Paddle 候选框；`03_cut_review/*/02_postprocess_units.png` 用来看真正进入 OCR 的版式理解结果；`03_cut_review/*/03_ocr_units_sheet.png` 用来看单元缩略图。

## 识别单元索引

`02_ocr_units/index.csv` 记录 OCR 识别需要的索引字段：

| 字段 | 说明 |
|---|---|
| `crop_id` | 识别单元唯一编号 |
| `page_id` | 原页面编号 |
| `page_file` | 原页面文件名 |
| `summary_path` | 文本块图片相对路径 |
| `role` | 版式初判后的块类型，如 `body`、`title`、`footnote`、`page_number` |
| `role_reason` | 角色来源，例如 Paddle 标签、页面底部小框、页面上方大行或默认正文 |
| `reading_order` | 页面文本合并时使用的阅读顺序 |
| `bbox` | 识别单元在页面中的位置框 |
| `crop_bbox` | 实际送入 OCR 的裁剪框 |

这里的 `role` 是版式理解的初判，不是 OCR 读字后的最终语义判断。标题、正文和页码先由 Paddle 标签、位置、尺寸、行高、居中程度等几何特征给出；OCR 完成后，`structure_pages.py` 会再用文本形态做轻量复核，例如短数字页码、注音行或明显非正文块。

## 页面文本拼合

`page_processing/assemble_pages.py` 是公开仓库中的唯一主拼合脚本。它会按识别单元的几何位置恢复视觉行，压掉保守判定的重叠重复块，再导出页级文本。

```bash
python page_processing/assemble_pages.py \
  --results outputs/demo_page_workflow/02_ocr_units/ocr_units_results.jsonl \
  --out-dir outputs/demo_page_workflow/03_page_text \
  --image-root outputs/demo_page_workflow/01_page_cutting/02_ocr_units
```

2026-06-30 的小改只发生在这个拼合阶段：复用既有 OCR 单元和 v5.16 OCR 结果，重新组合页级文本。它改善了高度重叠 OCR 单元的近重复、页码混入正文、多行块被强行横拼等问题；它不是切图后处理，也不会改变 `02_ocr_units/index.csv`。在页面评估集上，平均 NED 从 `0.113530` 降到 `0.104330`，漏行页从 `75` 降到 `71`，重复页从 `41` 降到 `39`，错序总数从 `476` 降到 `430`。

## 结构化页面输出

`page_processing/structure_pages.py` 读取 OCR 单元或已经拼好的 `submission_pages.jsonl`，导出轻量结构化结果：

```bash
python page_processing/structure_pages.py \
  --input outputs/demo_page_workflow/02_ocr_units/ocr_units_results.jsonl \
  --out-dir outputs/demo_page_workflow/04_page_structure \
  --input-kind ocr_units
```

输出包括 `structured_pages.jsonl`、`structured_pages.md`、`page_structure_audit.csv` 和 `structure_summary.json`。它保留标题、正文、页码、块角色、位置框和 OCR 状态；对《雪族子史篇》这类彝汉并排页面，还会额外抽取彝文原文行和彝汉对照行。它不改写 OCR 正文，也不替代人工校对。

## 为什么需要页面切割

复杂整页直接识别时，模型可能出现漏行、跨行、换行不稳定、页码/脚注/正文边界混乱等问题。页面切割把整页先变成可检查的识别单元，再用 `assemble_pages.py` 拼合页面文本，便于人工复核和异常定位。

## 《雪族子史篇》整页对比案例

以最新 `758` 条总评估集中的《雪族子史篇》65 页为对象，我们对比了两种识别路径：整页图像直接进入模型识别，以及先用 Paddle DocLayout 生成识别单元、再识别并合并页面文本。这是页面切割方法对照；完整 `758` 条系统总分和 page 子集结果分开报告。

| 识别路径 | 平均归一化编辑距离（Avg NED） | 说明 |
|---|---:|---|
| 页面切割后识别 | `0.047213` | 阅读顺序更稳，彝汉配对更接近人工标注，非文字干扰更少 |
| 直接整页识别 | `0.525967` | 容易出现跨行、错行、彝汉配对拆散和图案误识别 |

表内数值均按当前 65 页 GT 和原始 Avg NED 口径计算。编辑距离下降主要来自三点：第一，页面切割减少阅读顺序错位、跨行和页码混入正文；第二，更小的识别单元让彝汉混排、标点和注释的局部对应关系更稳定；第三，版面检测可以减少图案、边框和噪声等非文字区域被误识别成文字。

该组样本只报告同口径摘要，不重复提交页面材料。复杂整页、手写长段落、多栏和脚注密集页面仍建议人工复核。

## 依赖

页面切割使用 `requirements.txt` 中的：

```text
paddleocr==3.4.0
```

默认候选版面检测模型：

```text
PP-DocLayout_plus-L
```

脚本参数 `--layout-model` 可切换为其他 Paddle DocLayout 模型，例如 `PP-DocLayout`。不管换哪一个模型，候选框都必须进入统一后处理，不能跳过后处理直接作为最终 OCR 单元。

PDF 输入还需要 Poppler：

```bash
brew install poppler
```

## 边界

页面切割不等于自动校对。它只负责把页面转成可识别、可追踪、可复核的识别单元。

严重倾斜、反光、遮挡、弯曲或低清页面仍可能切割不完整；这种情况应查看 `03_cut_review/` 和演示页面的异常提示，再决定是否复拍或复跑。
