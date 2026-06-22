# 书页切图流程复用说明

这套流程的目标不是“万能切图”，而是把正式排版书页拆成可复核、可复用的 OCR 输入：

```text
页面图
→ v3 粗分流：一次行图 / region 兜底 / 忽略项 / 特殊页型
→ v4 二次切分：只对 v3 的 region 大块做局部切行
→ 切图前后对照：给人快速检查
→ 成功切图汇总：给 OCR 训练、评估、标注使用
```

## 一键运行

在项目根目录执行：

```bash
python3 crop_pipeline/run.py \
  --input "/path/to/page_images" \
  --output-root "/path/to/output_root"
```

如果新书页文件名不包含 `目录`、`混排`、`封面` 这类线索，建议先使用页型清单：

```bash
python3 crop_pipeline/run.py \
  --input "/path/to/page_images" \
  --output-root "/path/to/output_root" \
  --page-manifest "/path/to/page_manifest.csv"
```

输出目录固定为：

```text
output_root/
  01_v3_routing/
  02_v4_secondary_split/
  03_cut_before_after_review/
  04_successful_crop_summary/
  crop_pipeline_validation.json
  page_manifest_template.csv
  run_summary.md
  README.md
```

其中：

| 文件 | 用途 |
|---|---|
| `README.md` | 本次输出目录说明 |
| `run_summary.md` | 本次运行数量摘要，快速看页型、v3 标签、v4 决策和最终 bucket |
| `crop_pipeline_validation.json` | 切图汇总索引校验结果 |
| `page_manifest_template.csv` | 自动按输入图片生成的页型清单模板，可复制修改后作为下一次 `--page-manifest` 输入 |

## 推荐查看顺序

先看：

```text
03_cut_before_after_review/
```

每页一个文件夹：

| 文件 | 含义 |
|---|---|
| `00_original.*` | 原图 |
| `01_v3_boxes.png` | v3 粗分流框 |
| `02_v3_cut_sheet.png` | v3 一次切图拼接 |
| `03_v4_secondary_boxes.png` | v4 大块二次切分位置图，仅有需要二次切分的页才有 |
| `04_v4_secondary_sheets/` | v4 二次切分拼接图，仅有需要二次切分的页才有 |

确认没大问题后，再看：

```text
04_successful_crop_summary/
```

里面是用于训练、评估、标注的数据入口：

| 目录 | 用途 |
|---|---|
| `01_line_ocr_ready/` | 可直接进入行级 OCR 的图 |
| `03_region_ocr_keep/` | 不建议继续拆行，保留给 region OCR 的区域图 |
| `04_ignore_or_special_reference/` | 手写记号、花纹、页眉页脚等参考项，不要混入正样本 |
| `index.csv` | 全部汇总文件的来源路径、类别和说明 |

## 接入 OCR

行级 OCR 的入口是：

```text
output_root/04_successful_crop_summary/01_line_ocr_ready/
```

如果只想快速试一张切好的行图，可以直接接本地 demo：

```bash
python demo/infer_single_image.py \
  --model /path/to/NuosuBburma-OCR \
  --image "/path/to/output_root/04_successful_crop_summary/01_line_ocr_ready/..."
```

批量处理时建议使用 `04_successful_crop_summary/index.csv` 作为索引，保留 `crop_id`、`page_id`、`source_box`、`part_index` 和 `reading_order`。不要只按文件名排序，否则 v4 二次切分得到的同一父框多行可能被打乱。

## 输入图片要求

推荐输入是整页图片：

```text
.png / .jpg / .jpeg / .tif / .tiff / .webp
```

也支持单个 PDF：

```bash
python3 crop_pipeline/run.py \
  --input "/path/to/book.pdf" \
  --output-root "/path/to/output_root" \
  --pdf-dpi 220 \
  --max-pages 20
```

PDF 会先渲染到：

```text
output_root/00_input_pages/
```

`--max-pages` 默认是 `20`，用于防止误把整本大 PDF 一次性渲染满磁盘；如果需要渲染全部页面，设置 `--max-pages 0`。PDF 输入依赖 Poppler 的 `pdftoppm`。

当前 v3 支持两种页型来源：

1. 推荐：显式页型清单 `--page-manifest`。
2. 兜底：从文件名里读取少量页面类型线索。

页型清单格式：

```csv
file,page_hint,note
page_001.png,body_page,
page_002.png,toc,
page_003.png,mixed_page,
page_004.png,mixed_cover_page,
page_005.png,cover_or_low_quality,
```

可用 `page_hint`：

| page_hint | 含义 | 处理倾向 |
|---|---|---|
| `body_page` | 普通正文页 | 优先切行，过高大块进入 v4 二次切分 |
| `toc` | 目录页 | 目录行进入 line OCR，过高目录块进入 v4 二次切分 |
| `mixed_page` | 正文混排页，例如彝文+注音/汉语 | 混排大块默认保留 region OCR |
| `mixed_cover_page` | 混排封面或标题页 | 文本行可切，装饰/手写/大块单独分流 |
| `cover_or_low_quality` | 封面、低质量页、非正文页 | 特殊页处理，不作为正文行切图目标 |

文件名兜底规则：

| 文件名包含 | 页面类型倾向 |
|---|---|
| `目录` | 目录页 |
| `封面混排` | 混排封面页 |
| `封面` 或 `低质量` | 特殊封面/低质量页 |
| `混排` | 正文混排页 |
| 其他 | 普通正文页 |

如果换新数据，最稳的方式不是改文件名，而是复制 `output_root/page_manifest_template.csv`，人工把少数页面的 `page_hint` 改准，然后重跑并加上 `--page-manifest`。

## 可复用边界

这套流程适合：

1. 正式排版的彝文正文页。
2. 目录页。
3. 彝汉混排或彝文+注音的书页。
4. 有页眉、页脚、脚注、边框的扫描页。

这套流程不承诺直接解决：

1. 极低质量封面。
2. 严重倾斜、弯曲、透视畸变页面。
3. 手写文本。
4. 多栏复杂版式。
5. 整页图文混排且没有稳定文字行的页面。

这些页面应进入特殊页型或 region OCR，而不是强行切行。

## 人工复核最小规则

每批新书页跑完后，只需要先看 `03_cut_before_after_review/`：

```text
第 X 页：
正文行是否大体正确？
大块是否被 v4 二次切开？
注音/脚注/混排区域是否被保留为 region？
花纹/页眉/页脚有没有混入 OCR 正样本？
```

如果只想快速给反馈，可用这个格式：

```text
第 X 页：正文对；第 Y 个大块还没二切；第 Z 个是页脚应忽略。
```

## 复用保障

为了保证流程能复用，当前已经固定：

1. 单一入口脚本：`crop_pipeline/run.py`
2. 固定四级输出目录。
3. 每一步都有 CSV 报告。
4. 给人看的目录和给训练的数据目录分开。
5. 原始 v3/v4 输出保留，不被汇总脚本移动或删除。
6. 支持 `page_manifest.csv` 显式指定页型，避免新书复用时依赖文件名。
7. 每次运行自动写 `run_summary.md`，便于比较不同书、不同参数的输出数量。
8. 每次运行自动写 `page_manifest_template.csv`，下一批书页可以直接复用模板。

## 换一本书时的最小流程

1. 把 PDF 转成整页图片，放入一个新目录。
2. 先不写清单，跑一遍 `crop_pipeline/run.py`。
3. 打开 `output_root/page_manifest_template.csv`，只修正明显错的页型。
4. 用修正后的 CSV 加 `--page-manifest` 重跑一遍。
5. 只看 `03_cut_before_after_review/`，确认正文行、大块二切、region 保留和忽略项是否合理。
6. 用 `04_successful_crop_summary/index.csv` 接训练、评估或人工标注。
7. 如需进入 OCR，优先使用 `01_line_ocr_ready/` 中的行图；不确定是否该拆行的样本保留在 `03_region_ocr_keep/`。

这就是当前的复用闭环：算法负责初筛，页型清单负责把“换书时的不确定性”显式化，人工只检查少量高价值判断。

## 当前核心策略

```text
不要追求所有页面都切成单行。
能稳定切行的正文走 line OCR；
普通正文大块先做 v4 二次切分；
注音配对、脚注、混排注释默认保留 region OCR；
花纹、手写记号、页眉页脚不进入 OCR 正样本。
```
