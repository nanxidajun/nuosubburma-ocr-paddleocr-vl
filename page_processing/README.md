# 页面切割流程

本目录有三个页面处理入口：`run.py` 负责页面切割和版式理解，`assemble_pages.py` 负责把 OCR 单元拼合成页级文本，`structure_pages.py` 负责把 OCR 单元或页级文本导出为结构化页面结果。`run.py` 先用 Paddle DocLayout 生成候选版面块；候选块不会直接送 OCR，必须进入统一后处理：边缘/留白清理、重叠去重、视觉行/小区域细分、角色初判、阅读顺序和位置框导出。

输出会保留 `page_id`、`crop_id`、`role`、`role_reason`、`reading_order`、`bbox` 等字段，供后续 OCR、visual-line 页面文本合并、结构化输出、异常审计和可选注音使用。

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
  01_doclayout/                   Paddle DocLayout 候选框原始结果和版面块统计
  02_ocr_units/                   后处理后的 OCR 单元图片和 index.csv
  03_cut_review/                  每页候选框、后处理单元和文本块预览
  page_processing_validation.json 基础校验报告
  run_summary.md                  本次运行摘要
```

最常看的三个入口：

| 入口 | 用途 |
|---|---|
| `03_cut_review/*/01_doclayout_boxes.png` | 看 Paddle 产出的候选框 |
| `03_cut_review/*/02_postprocess_units.png` | 看统一后处理后的版式理解结果，重点检查 title/body/page_number、行切分和阅读顺序 |
| `02_ocr_units/index.csv` | 下游 OCR 读取的索引，包含图片路径、角色、角色原因、阅读顺序、页面来源、父级版面框和识别单元位置 |

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
-> 统一后处理和版式理解
-> OCR 单元识别
-> 页面文本合并
-> 结构化页面输出
-> 异常审计
-> 可选注音
```

## 单独拼合 OCR 结果

`assemble_pages.py` 是页面文本拼合的唯一主脚本。它使用 OCR 单元的 `bbox` / `reading_order` 做 visual-line 拼合，输出 `submission_pages.*`、`official_submission.*`、`page_audit.csv` 和 `audit_summary.json`。

```bash
python page_processing/assemble_pages.py \
  --results outputs/demo_page_workflow/02_ocr_units/ocr_units_results.jsonl \
  --out-dir outputs/demo_page_workflow/03_page_text \
  --image-root outputs/demo_page_workflow/01_page_cutting/02_ocr_units
```

2026-06-30 的拼合小改只影响 `OCR 单元识别 -> 页面文本合并`：更稳地抑制高度重叠近重复块，避免页码混入正文视觉行，并保留单个多行 OCR 单元的内部换行。它不是切图后处理；漏切、过切和 OCR 单元缺字仍应回到 `run.py` 输出的 `03_cut_review/` 复核。

如果已经跑过页面切割，也可以复用切割结果：

```bash
python demo/run_page_workflow.py \
  --page-root outputs/page_cutting_demo \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow
```

## 单独导出结构化页面

`structure_pages.py` 用于把页面结果拆成更容易审计的结构字段。它保留标题、正文、页码、块角色、位置框、OCR 状态；对彝汉并排页面，还会抽取彝文原文行和彝汉对照行。切割阶段的 `role` 是版式初判，OCR 后结构化阶段会再根据识别文本做轻量复核，例如短数字页码、注音块或明显的非正文文本。

```bash
python page_processing/structure_pages.py \
  --input outputs/demo_page_workflow/02_ocr_units/ocr_units_results.jsonl \
  --out-dir outputs/demo_page_workflow/04_page_structure \
  --input-kind ocr_units
```

主要输出：

| 输出 | 用途 |
|---|---|
| `structured_pages.jsonl` | 每页结构化 JSONL |
| `structured_pages.md` | 便于人工复查的 Markdown |
| `page_structure_audit.csv` | 每页块数、行数、页码和告警 |
| `structure_summary.json` | 页数、块数、角色统计和告警汇总 |

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

页面切割使用 `requirements.txt` 中的 `paddleocr==3.4.0`，默认候选模型名为 `PP-DocLayout_plus-L`。模型只负责提供候选框；本仓库的统一后处理层负责输出最终 OCR 单元、角色、阅读顺序和复核图。

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

页面切割用于降低复杂整页直接 OCR 的漏行、错行和阅读顺序风险，但它不自动修改 OCR 文本。切割后先看 `03_cut_review/*/02_postprocess_units.png` 是否已经跑通版式理解；如果页面严重倾斜、反光、遮挡、弯曲或文字被拍糊，异常审计可能提示复跑或改用另一种识别方式对照。
