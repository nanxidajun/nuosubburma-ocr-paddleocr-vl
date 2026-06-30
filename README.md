# NuosuBburma OCR：真实场景中的规范彝文识别

<p align="center">
  <a href="https://huggingface.co/nanxidajun/NuosuBburma-OCR"><img alt="Hugging Face 模型" src="https://img.shields.io/badge/HuggingFace-%E6%A8%A1%E5%9E%8B-f7c948"></a>
  <a href="https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set"><img alt="Hugging Face 评估集" src="https://img.shields.io/badge/HuggingFace-%E8%AF%84%E4%BC%B0%E9%9B%86-4c9f70"></a>
  <a href="https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Evaluation-Set"><img alt="评估集可视化" src="https://img.shields.io/badge/Space-%E8%AF%84%E4%BC%B0%E9%9B%86%E5%8F%AF%E8%A7%86%E5%8C%96-0f766e"></a>
  <img alt="基座模型" src="https://img.shields.io/badge/Base-PaddleOCR--VL--1.6_0.9B-3465d9">
  <img alt="微调方式" src="https://img.shields.io/badge/Fine_tuning-LoRA-8a5cf6">
</p>

本项目是面向 **PaddleOCR 全球衍生模型挑战赛** 的规范彝文（ꆈꌠꁱꂷ / Nuosu Bburma）OCR 项目，基于 `PaddleOCR-VL-1.6 (0.9B)` + LoRA 构建。

项目目标不是只识别裁好的单行图，而是把旧书扫描、教材工具书页面、手机照片、屏幕拍照、手写拍照样本和彝汉混排资料，转换为可搜索、可校对、可进入语料库的 Unicode 文本。OCR 是第一步：这些结构化文本会成为后续规范彝文 NLP 的基础材料，支撑分词、检索、语料建设、注音校对、语言资源整理和低资源模型训练。

[Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) · [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [评估集可视化](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [线上演示](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo) · [提交说明](docs/COMPETITION_SUBMISSION.md) · [评估集说明](docs/EVALUATION_DATASET.md) · [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)

## 当前口径

| 项目 | 当前状态 |
|---|---|
| 任务 | 规范彝文 OCR，覆盖 `line`、`region`、`page` 输入 |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` |
| 微调方式 | LoRA |
| 最新评估集 | `758` 条真实来源样本，`758` 张图片 |
| 页面级流程 | `PP-DocLayout_plus-L` 页面切割、OCR 单元识别、页面文本合并、结构化输出、可选注音 |
| 数据托管 | 模型权重和完整评估图片托管在 Hugging Face，GitHub 保留代码、配置、文档和结果摘要 |

## 微调前后效果对比

最终评估统一使用 `758` 条真实来源样本，对比 `PaddleOCR-VL-1.6` 未微调基座和 LoRA 微调后的提交模型。

归一化编辑距离（NED）越低越好；Exact 对整页、换行和标点很敏感，因此只作为辅助观察。首页只保留最核心统计，完整逐样本结果和拆分表见 [评估摘要](evaluation/README.md)。

| 指标 | 未微调基座 | LoRA 微调后 | 结论 |
|---|---:|---:|---|
| Avg NED | `0.726733` | `0.052310` | 整体错误量下降约 `93%`，微调是决定性收益。 |
| Exact | `0 / 758` | `445 / 758 (58.7%)` | 在短文本和清晰行图上已经有较高完全匹配率。 |
| Yi-only Avg NED | `1.000000` | `0.054440` | 基座几乎不能稳定输出规范彝文，LoRA 后彝文主干可用。 |
| Han-only Avg NED | `0.209245` | `0.037348` | 混排中的汉字也明显改善。 |
| replacement / LaTeX-like / extra Latin / long prediction | `16 / 105 / 321 / 34` | `0 / 9 / 1 / 1` | 异常输出基本被压住。 |

按拆分结果看，最稳定的是单行图（`470` 条，Avg NED `0.025444`）和旧印刷/扫描资料（`507` 条，Avg NED `0.034428`）。主要短板是整页图（`169` 条，Avg NED `0.105898`）、屏幕拍照/页面上传图（`87` 条，Avg NED `0.117566`）和手写拍照（`53` 条，Avg NED `0.122555`）。因此当前模型已经适合做真实资料整理和人工校对的第一稿；复杂页面和拍照类输入仍建议配合页面切割、结构化输出和人工复核。

## 评审入口

| 评分点 | 本项目证据 | 入口 |
|---|---|---|
| 评估集质量 | `758` 条真实来源样本；`line 470` / `region 119` / `page 169`；空 GT、缺图、重复 ID、合成样本标记均为 `0` | [评估集说明](docs/EVALUATION_DATASET.md)，[质检报告](docs/EVALUATION_QUALITY_REPORT.md)，[标注可视化](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 场景稀缺性 | 覆盖旧书、新印刷资料、教材、工具书、彝汉混排、拉丁注音、手写、场景照片和屏幕拍照资料 | [项目背景](docs/PROJECT_BACKGROUND.md) |
| 任务复杂度 | 支持整页、PDF 和照片输入；先做页面切割，再识别文本区域、恢复阅读顺序、合并页面文本并生成结构化结果 | [页面切割](page_processing/README.md)，[页面级说明](docs/PAGE_PROCESSING.md)，[演示](demo/README.md) |
| 训练数据科学性 | 训练包 `21504` 行；真实材料、训练侧合成样本和视觉变化样本分开记录；缺图、空标签、替换符和公式化片段标签均为 `0` | [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)，[训练包清单](configs/train_data_manifest_v5_16.json) |
| 微调策略 | 三阶段 LoRA 微调；用固定开发诊断集比较分支，不把开发诊断集或最终评估集写回训练包 | [模型与训练](docs/MODEL_AND_TRAINING.md)，[评估摘要](evaluation/README.md) |
| 开源复现 | 提供模型下载、评估集下载、线上演示、本地演示、训练配置、评估脚本、逐样本结果和分组图表 | [model](model/README.md)，[scripts](scripts/README.md)，[evaluation](evaluation/README.md) |

## 真实评估集

评估集只使用真实来源样本，不使用合成样本证明模型效果。完整图片、标注和统计托管在 [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set)。同时提供 [评估集标注可视化 Space](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Evaluation-Set)，可直接查看代表样本图片、canonical GT、来源、场景、粒度和难度分层。

最终评估集为 `758` 条真实来源样本和 `758` 张图片，空 GT、缺图、重复 ID 和合成样本标记均为 `0`。核心分布如下；逐样本明细见 [samples.csv](NuosuBburma_OCR_Evaluation_Set/samples.csv)，质控和汇总统计见 [dataset_summary.json](NuosuBburma_OCR_Evaluation_Set/dataset_summary.json)。

| 维度 | 统计 | 简短结论 |
|---|---|---|
| 输入粒度 | 单行 `470` / 区域 `119` / 整页 `169` | 不只评干净行图，也保留区域和整页压力。 |
| 真实场景 | 旧印刷 `507` / 新印刷 `100` / 屏幕拍照 `87` / 手写拍照 `53` / 真实照片 `11` | 主体是旧印刷资料，同时覆盖拍照和屏幕上传噪声。 |
| 难度 | easy `83` / medium `467` / hard `208` | 中高难样本占多数，避免只报告简单样本。 |
| 文本构成 | 纯彝文 `344` / 混排 `414` | 只做粗分，避免把彝汉、注音、数字和少量特殊样本拆成过细且边界不稳定的类别。 |
| 数字 | 含数字 `177` / 不含数字 `581` | 页码、编号和工具书条目单独进入评估压力。 |

![Evaluation dataset composition](docs/figures/dataset_composition.svg)

## 页面级识别能力

真实规范彝文资料常见输入不是干净单行图，而是旧书整页、PDF、手机照片、屏幕图、脚注、页码、注音和彝汉混排页面。本项目提供可检查的页面级流程：

```text
整页 / PDF / 手机照片 / 屏幕图
-> PP-DocLayout_plus-L 候选版面块
-> 统一后处理生成 OCR 单元、角色、阅读顺序和 bbox
-> OCR 单元识别
-> 阅读顺序恢复
-> 页面文本合并
-> 结构化页面输出
-> 异常审计
-> 可选注音
```

![规范彝文页面级识别能力](docs/figures/ocr_workflow_photo.svg)

《雪族 子史篇》65 页用于页面切割对照实验：

| 识别路径 | Avg NED | 说明 |
|---|---:|---|
| 页面切割后识别 | `0.047213` | 阅读顺序更稳，彝汉配对更接近人工标注，非文字干扰更少 |
| 直接整页识别 | `0.525967` | 容易跨行、错行、拆散彝汉配对，并把图案误识别为文字 |

页面级 demo 里，Paddle DocLayout 只作为候选框生成器；真正进入 OCR 的单元来自统一后处理层。复核版式理解时先看 `01_page_cutting/03_cut_review/*/02_postprocess_units.png` 和 `01_page_cutting/02_ocr_units/index.csv` 中的 `role`、`role_reason`、`reading_order`、`bbox`。

## 训练数据与模型策略

训练集遵循“真实材料定边界、训练侧合成样本补长尾、视觉变化样本补图像状态”的原则。最终训练包为 `v5_16_synth_capped_rerender_official`。

| 项目 | 数量或设置 |
|---|---:|
| 清理后训练行数 | `21504` |
| 继承基础样本 | `12435` |
| 新增视觉变化样本 | `9069` |
| 保持不变的真实样本 | `1861` |
| 原始合成样本 | `10574` |
| 普通视觉变化样本 | `8360` |
| 脚注视觉变化样本 | `60` |
| 多行区域视觉变化样本 | `649` |
| 拉丁注音视觉变化样本 | `0` |
| 缺图 / 空标签 / 替换符标签 | `0 / 0 / 0` |
| 公式化片段标签 / 反斜杠标签 | `0 / 0` |

三阶段调优策略：

| 阶段 | 目标 | 判断方式 |
|---|---|---|
| 第一阶段 | 验证 `PaddleOCR-VL-1.6` + LoRA 能否学习规范彝文字形和基本输出格式 | 单书真实行图可学性 |
| 第二阶段 | 补低频字符、字体变化、旧印刷退化和彝汉混排覆盖 | 分组观察彝文、汉字、数字、混排和异常输出 |
| 第三阶段 | 比较不同训练包分支是否真正更稳 | 固定开发诊断集，只比较输出，不回写训练 |

训练配置和分支结论见 [模型与训练](docs/MODEL_AND_TRAINING.md)，训练数据构建细节见 [训练数据构建报告](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)。

## 快速复现

模型推理和批量评估建议使用 CUDA GPU 环境。CPU 环境可用于依赖检查和部分脚本连通性检查。

```bash
conda create -n paddleocr-vl python=3.11 -y
conda activate paddleocr-vl
python -m pip install -U pip setuptools wheel
python -m pip install paddlepaddle-gpu==3.3.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
python -m pip install -r requirements.txt
```

下载模型和评估集：

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR

hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

安装后自检：

```bash
scripts/smoke_check.sh
```

运行单图演示：

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png \
  --max-image-side 2400 \
  --html-output outputs/demo/mixed_line.html
```

运行整页演示：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --max-image-side 2400 \
  --with-pronunciation
```

批量评估入口见 [scripts/README.md](scripts/README.md)。最终评估对完整 `annotations.jsonl` 计算主分，并同步输出逐样本结果、多维统计表和图表。

## 仓库结构

```text
configs/                         训练/导出配置与训练数据清单
NuosuBburma_OCR_Evaluation_Set/  评估集入口说明；完整图片托管在 Hugging Face 评估集
page_processing/                 页面切割、页面文本合并与结构化输出
demo/                            单图推理、整页演示与样例图
docs/                            提交说明、评估集、训练数据、模型训练和项目背景
evaluation/                      开发诊断结果、分组统计和逐样本输出
model/                           模型托管入口、下载命令和使用边界
postprocess/                     规范彝文注音工具
scripts/                         训练、评估和统计工具
```
