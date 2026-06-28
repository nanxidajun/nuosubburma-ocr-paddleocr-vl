# NuosuBburma OCR：自然场景中的规范彝文 OCR

<p align="center">
  <a href="https://huggingface.co/nanxidajun/NuosuBburma-OCR"><img alt="Hugging Face 模型" src="https://img.shields.io/badge/HuggingFace-%E6%A8%A1%E5%9E%8B-f7c948"></a>
  <a href="https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set"><img alt="Hugging Face 评估集" src="https://img.shields.io/badge/HuggingFace-%E8%AF%84%E4%BC%B0%E9%9B%86-4c9f70"></a>
  <img alt="Base model" src="https://img.shields.io/badge/Base-PaddleOCR--VL--1.6_0.9B-3465d9">
  <img alt="Fine tuning" src="https://img.shields.io/badge/Fine_tuning-LoRA-8a5cf6">
</p>

本项目是面向 **PaddleOCR 全球衍生模型挑战赛** 的规范彝文（ꆈꌠꁱꂷ / Nuosu Bburma）OCR 衍生模型。赛事鼓励开发者基于 PaddleOCR-VL 选择长尾 OCR 场景、自定义任务方向并开源可复现成果；本项目选择的任务是 **自然场景中的规范彝文 OCR**。

这里的“自然场景”包括旧书扫描、教材工具书页面、场景实拍、屏幕实拍、手写照片等等。规范彝文已有稳定书写体系，也有大量真实资料，但作为低资源少数民族语言，许多内容仍停留在图片和纸页里，不能搜索，不能复制，也很难进入后续NLP语料建设。

因此，项目把重心放在一条从真实复杂资料到可用文本的链路上：先把整页图片处理成可识别的 OCR 单元，再完成 OCR、合并输出文本和按需注音。最终目标是产出可检索、可校对、可进入语料库的 Unicode 文本，而不止是在几张样例图上“看起来会读”。这也是本项目作为衍生模型的赛事定位：补充 PaddleOCR-VL 在低资源民族文字场景中的真实评估、训练数据和复现入口。

[Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) · [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [Hugging Face Space Demo](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo) · [提交说明](docs/COMPETITION_SUBMISSION.md) · [评估集说明](docs/EVALUATION_DATASET.md) · [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)

Hugging Face Space 是线上交互入口；没有配置 Space GPU 时，完整模型推理、页面切割复现和批量评估以本地 demo 与脚本为准。

## 赛事评审入口

本仓库按官方评分表的六个维度组织材料：评估集质量、场景稀缺性、任务复杂度、训练数据集构建科学性、模型微调策略与创新、技术文档与开源贡献。下面的入口不是普通目录导航，而是给评委快速核验每一项得分依据。

| 评分维度 | 本项目证据 | 快速入口 |
|---|---|---|
| 评估集质量 | `603` 条真实主评估样本，`line 515 / region 84 / page 4`，覆盖新印刷、旧印刷、规范手写、实拍/屏幕；合成样本不进入主评估 | [评估集说明](docs/EVALUATION_DATASET.md)，[质检报告](docs/EVALUATION_QUALITY_REPORT.md) |
| 场景稀缺性 | 长尾低资源民族文字 OCR，面向旧书、教材、工具书、彝汉混排、注音、手写和实拍资料数字化 | [项目背景](docs/PROJECT_BACKGROUND.md) |
| 任务复杂度 | 从整页、PDF、照片开始，先切割并保留阅读顺序，再识别 OCR 单元，最后合并页面文本并按需生成注音；demo 使用普通样例图展示这条工程流程 | [页面切割](page_processing/README.md)，[demo](demo/README.md) |
| 训练数据科学性 | 训练包 `21504` 行，真实样本打底，合成样本只补覆盖面，并用输出约束防止结果跑偏；缺图、空标签、替换符、LaTeX-like 标签均为 `0` | [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)，[manifest](configs/train_data_manifest_v5_16.json) |
| 微调策略与创新 | 在 PaddleOCR-VL 上做 LoRA 微调；同一标签换字体和退化方式重渲染，重点检查形近字、多余 Latin、公式化片段和异常长输出风险；v5.16 胜出，v5.17 未晋级 | [模型与训练](docs/MODEL_AND_TRAINING.md)，[评估结果](evaluation/README.md) |
| 开源与复现 | Hugging Face 模型、Hugging Face 评估集、Hugging Face Space 交互入口、本地命令行 demo、训练配置、评估脚本、逐样本输出和分组图表 | [demo](demo/README.md)，[scripts](scripts/README.md)，[model](model/README.md) |

当前提交模型在 `603` 条主评估样本上取得 Avg NED `0.036068`，Yi-only Avg NED `0.038309`，Han-only Avg NED `0.022447`；replacement / LaTeX / extra Latin / long_pred 为 `0 / 2 / 0 / 0`。这组结果的价值不在于把所有场景都说成已经解决，而在于按比赛评分逻辑把稳定场景、困难场景和仍需复核的边界分开呈现：清晰 line/region 是当前可靠入口，复杂整页和规范手写则作为更高难度的真实扩展继续报告。

## 交付内容

| 交付 | 内容 | 入口 |
|---|---|---|
| 模型 | 基于 `PaddleOCR-VL-1.6 (0.9B)` 的 LoRA 微调模型，固定提示词为 `<image>OCR:` | [model](model/README.md)，[Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) |
| 真实评估集 | 真实来源样本，按视觉场景、输入粒度、文字混合和难度分层统计；主评估不使用合成样本 | [评估集说明](docs/EVALUATION_DATASET.md)，[质检报告](docs/EVALUATION_QUALITY_REPORT.md)，[Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 自然场景 OCR 流程 | 从整页、PDF、照片开始，切出 OCR 单元，按阅读顺序合并页面文本，并按需补充注音输出 | [页面切割流程](page_processing/README.md)，[demo](demo/README.md)，[后处理工具](postprocess/README.md) |
| 训练数据构建 | 真实样本打底，受控合成补覆盖，配合输出检查、训练/评估隔离和 manifest | [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)，[configs](configs/) |
| 复现工具 | Hugging Face Space 交互入口、单图 demo、整页 demo、评估脚本、训练脚本、模型/评估集下载说明 | [demo](demo/README.md)，[scripts](scripts/README.md)，[提交说明](docs/COMPETITION_SUBMISSION.md) |

## 自然场景 OCR 流程

真实规范彝文资料常同时包含书页、照片、脚注、注音、页码、彝汉混排、手写和旧印刷噪声。对这类资料来说，OCR 不能止步于“识别一行字”，还要把页面重新变成可读、可查、可校对的文本。因此项目按以下链路处理：

![规范彝文 OCR workflow](docs/figures/ocr_workflow_photo.svg)

| 子任务 | 当前实现 | 作用 |
|---|---|---|
| 整页/PDF/照片输入 | [页面切割入口脚本](page_processing/run.py) | 读取真实书页、PDF、手机拍照或拍屏 |
| 页面切割 | [页面切割流程](page_processing/README.md) | 使用 Paddle 的 `PP-DocLayout` 生成 OCR 单元，降低整页直接 OCR 的漏行和错行风险 |
| 阅读顺序记录 | `page_id`、`crop_id`、`reading_order` | 支持把 OCR 单元识别结果合并为页面文本 |
| 彝文/彝汉混排 OCR | `<image>OCR:` | 输出规范彝文、汉字、数字、标点和可见 Latin 注音 |
| 页面文本合并 | 页面切割流程输出的 `reading_order` 和页面元数据 | 按几何位置、块角色或 reading order 生成可校对页面文本 |
| 输出风险审计 | [analyze_submission_eval.py](scripts/analyze_submission_eval.py) / 整页 audit | 统计 replacement、LaTeX-like、extra Latin、long_pred、空页和重复页等风险，用于复核而非自动改写 |
| 注音/语料化输出 | [add_nuosu_pronunciation.py](postprocess/add_nuosu_pronunciation.py) | 服务教学、检字、人工校对和语料库建设 |
| 整页 demo | [run_page_workflow.py](demo/run_page_workflow.py) | 用普通样例图跑通页面切割、OCR 单元识别、页面文本合并、异常审计和可选注音 |

### 整页切割对比实验

评估集中的《雪族子史篇》全书 65 页整页样本用于对比两种路径：整页图像直接进入 OCR 模型，以及先用 Paddle 的 `PP-DocLayout` 生成 OCR 单元后再识别并合并页面文本。

![《雪族子史篇》页面切割对比](docs/figures/xuezu_page_cutting_case.svg)

| 识别路径 | Avg NED | 主要差异 |
|---|---:|---|
| 页面切割后识别 | `0.0654` | 阅读顺序更稳，彝汉配对更接近 GT，非文字干扰更少 |
| 直接整页 OCR | `0.5540` | 容易出现跨行、错行、彝汉配对拆散和花纹误识别 |

这个实验说明页面切割对复杂整页 OCR 的价值：先处理版式，再识别文字，比把整页直接送入 OCR 模型更稳定。详细说明见 [页面切割流程](docs/PAGE_PROCESSING.md)。

## 评估与训练

最终结果按 `NuosuBburma OCR Evaluation Set` 统一统计，PaddleOCR-VL Base 和当前提交模型使用同一评估集、同一脚本、同一指标。这样做的重点是让结果可复查，避免只给一个无法追溯的分数。结果表见 [提交说明](docs/COMPETITION_SUBMISSION.md)；评估集分布和质检见 [评估集说明](docs/EVALUATION_DATASET.md) 与 [质检报告](docs/EVALUATION_QUALITY_REPORT.md)。

训练侧用真实样本打底，用受控合成补齐覆盖，并持续检查模型是否多出 Latin、公式化片段或异常长输出。低资源文字的难点在于两头都要守住：既要补齐罕见字符和视觉变化，又不能把合成数据的习惯带进真实输出；详细构建过程见 [训练数据构建报告](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)，模型设置和分支选择见 [模型与训练说明](docs/MODEL_AND_TRAINING.md)。

## 复现

### 1. 准备环境

完整模型推理和批量评估建议使用 CUDA GPU 环境。CPU 环境可用于依赖检查和部分脚本连通性检查，不作为完整评估推荐路径。

```bash
conda create -n paddleocr-vl python=3.11 -y
conda activate paddleocr-vl
python -m pip install -U pip setuptools wheel
```

安装 PaddlePaddle GPU 版：

```bash
python -m pip install paddlepaddle-gpu==3.3.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
```

安装本项目依赖：

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 已包含 Hugging Face CLI；安装完成后即可使用 `hf download`。

如果国内网络较慢，可先设置 Hugging Face 镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 2. 下载模型和评估集

下载模型：

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

下载评估集：

```bash
hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

### 3. 安装后自检

```bash
scripts/smoke_check.sh
```

这一步会检查 Python 依赖、样例图和模型目录；如果模型已经下载，会继续跑一张单图 OCR。

### 4. 运行 demo

运行单图 demo：

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png \
  --max-image-side 2400 \
  --html-output outputs/demo/mixed_line.html
```

运行整页 demo：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --max-image-side 2400 \
  --with-pronunciation
```

### 5. 运行评估

运行评估：

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl

python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```

## 仓库结构

```text
configs/                         训练/导出配置与训练数据 manifest
NuosuBburma_OCR_Evaluation_Set/  评估集入口说明，完整数据托管在 Hugging Face 评估集仓库
page_processing/                 PP-DocLayout 页面切割入口
demo/                            单图推理、整页 demo 与样例图
docs/                            提交说明、评估集、训练数据、模型训练和项目背景
evaluation/                      开发诊断结果、分组统计和逐样本输出
model/                           模型托管入口、下载命令和使用边界说明
postprocess/                     规范彝文注音工具
scripts/                         训练、评估和统计工具
```
